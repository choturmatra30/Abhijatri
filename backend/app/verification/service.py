"""The Verified Member application (Features/Verified user sign-up form.md, sections 3 to 10).

A case starts as a ``draft`` and is filled one step at a time; every step is saved on the server, so a
dropped connection loses nothing. Submission runs the automatic checks (10.1), sets risk flags (10.2) and
puts the case in the existing staff queue. Staff decisions stay in ``app.admin.cases``.

Steps: ``eligibility``, ``personal``, ``phone``, ``document``, ``student`` (only when the occupation is
Student, or for a student update), ``selfie`` and ``emergency`` (optional). A renewal (5) redoes only the
document and the selfie; a student update (Step 5 "add later") only the student step.
"""

import contextlib
import hashlib
import hmac
import json
import re
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crypto, fieldcrypt
from app.admin import audit, tasks
from app.auth.sessions import Principal
from app.config import get_settings
from app.errors import ApiError
from app.models import (
    Appeal,
    EmergencyContactDefault,
    Institution,
    ModerationTask,
    OneTimeCode,
    PhoneNumber,
    User,
    Verification,
    VerificationAttributes,
    VerificationBan,
    VerificationCase,
    VerificationEvidence,
)
from app.notify import events
from app.sms import get_sms
from app.storage import (
    QUARANTINE_BUCKET,
    QUARANTINE_MAX_BYTES,
    QUARANTINE_TYPES,
    SEALED_BUCKET,
    StorageClient,
)
from app.verification import geo, images

STEPS = ("eligibility", "personal", "phone", "document", "student", "selfie", "emergency")
EDITABLE_STATES = ("draft", "needs_clarification")
OPEN_STATES = ("draft", "submitted", "in_review", "needs_clarification", "escalated")
DOC_LABEL = "abhijatri:identity-document:v1"
PHONE_LABEL = "abhijatri:phone:v1"
EMAIL_LABEL = "abhijatri:academic-email:v1"
OTP_LABEL = "abhijatri:one-time-code:v1"
GESTURES = (
    ("hold-up-three-fingers", "তিনটি আঙুল তুলে ধরুন", "Hold up three fingers"),
    ("turn-head-left", "মাথা বাঁ দিকে ঘোরান", "Turn your head to the left"),
    ("turn-head-right", "মাথা ডান দিকে ঘোরান", "Turn your head to the right"),
    ("touch-left-ear", "বাঁ হাতে বাঁ কান ছুঁয়ে থাকুন", "Touch your left ear with your left hand"),
    ("thumbs-up", "বুড়ো আঙুল উঁচিয়ে দেখান", "Show a thumbs up"),
    ("hand-on-chin", "থুতনিতে হাত রাখুন", "Rest your hand on your chin"),
)
LIVENESS_VALID = timedelta(minutes=20)
ACADEMIC_SUFFIXES = (".ac.bd", ".edu.bd")
REJECTION_COOLDOWNS = (timedelta(days=7), timedelta(days=30))  # first and second rejection (10.3)
BAN_DAYS = 90
NOT_COUNTED_REJECTIONS = ("use-new-form",)  # asking someone to reapply on the new form is no strike


def _now() -> datetime:
    return datetime.now(UTC)


def _dhaka_today() -> date:
    return _now().astimezone(get_settings().display_tz).date()


def _invalid(field: str, code: str) -> ApiError:
    return ApiError("VALIDATION_FAILED", field_errors=[{"field": field, "code": code}])


def _aad(case: VerificationCase, name: str) -> str:
    return f"verification_case:{case.id}:{name}"


# ======================================================================================
# hashing and normalisation
# ======================================================================================


def normalise_phone(raw: str) -> str:
    """Bangladeshi mobile in E.164: +8801[3-9]XXXXXXXX (operator prefixes 013 to 019)."""
    digits = re.sub(r"[\s\-()]", "", raw or "")
    if digits.startswith("+"):
        digits = digits[1:]
    if digits.startswith("880"):
        digits = digits[3:]
    elif digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"1[3-9]\d{8}", digits):
        raise _invalid("phone", "INVALID_FORMAT")
    return "+880" + digits


def normalise_any_phone(raw: str) -> str:
    """Emergency contacts may be international: digits with an optional leading +, 7 to 15 digits."""
    value = re.sub(r"[\s\-()]", "", raw or "")
    if not re.fullmatch(r"\+?\d{7,15}", value):
        raise _invalid("emergency_phone", "INVALID_FORMAT")
    try:
        return normalise_phone(value)
    except ApiError:
        return value if value.startswith("+") else value


def normalise_document(doc_type: str, raw: str) -> str:
    value = re.sub(r"[\s\-/]", "", (raw or "").upper())
    if doc_type == "NID":
        if not re.fullmatch(r"\d{10}|\d{13}|\d{17}", value):
            raise _invalid("doc_number", "INVALID_FORMAT")
    elif doc_type == "PASSPORT":
        if not re.fullmatch(r"[A-Z]{1,2}\d{6,9}", value):
            raise _invalid("doc_number", "INVALID_FORMAT")
    elif doc_type == "DRIVING_LICENCE":
        if not re.fullmatch(r"[A-Z0-9]{5,20}", value):
            raise _invalid("doc_number", "INVALID_FORMAT")
    else:
        raise _invalid("doc_type", "INVALID_VALUE")
    return value


def _keyed(label: str, value: str) -> bytes:
    return crypto.digest(label, crypto.current_key_id(), value)


def _candidates(label: str, value: str) -> list[bytes]:
    return [d for _, d in crypto.candidate_digests(label, value)]


def doc_hash(doc_type: str, number: str) -> bytes:
    return _keyed(DOC_LABEL, f"{doc_type}:{number}")


def phone_hash(e164: str) -> bytes:
    return _keyed(PHONE_LABEL, e164)


def _code_hash(code_id: uuid.UUID, code: str) -> bytes:
    return _keyed(OTP_LABEL, f"{code_id}:{code}")


# ======================================================================================
# case access, bans and cooldowns
# ======================================================================================


def is_verified(session: Session, user_id: uuid.UUID) -> bool:
    from app.admin.cases import is_verified_member

    return is_verified_member(session, user_id)


def active_verification(session: Session, user_id: uuid.UUID) -> Verification | None:
    now = _now()
    return session.scalar(
        select(Verification)
        .where(
            Verification.user_id == user_id,
            Verification.verification_type == "VERIFIED_MEMBER",
            Verification.status == "APPROVED",
            Verification.revoked_at.is_(None),
            (Verification.expires_at.is_(None)) | (Verification.expires_at > now),
        )
        .order_by(Verification.decided_at.desc().nulls_last())
        .limit(1)
    )


def last_verification(session: Session, user_id: uuid.UUID) -> Verification | None:
    return session.scalar(
        select(Verification)
        .where(Verification.user_id == user_id, Verification.verification_type == "VERIFIED_MEMBER", Verification.status == "APPROVED")
        .order_by(Verification.decided_at.desc().nulls_last())
        .limit(1)
    )


def active_ban(session: Session, *, user_id: uuid.UUID | None = None, doc: bytes | None = None, phone: bytes | None = None) -> VerificationBan | None:
    now = _now()
    conditions = []
    if user_id is not None:
        conditions.append(VerificationBan.user_id == user_id)
    if doc is not None:
        conditions.append(VerificationBan.doc_hash == doc)
    if phone is not None:
        conditions.append(VerificationBan.phone_hash == phone)
    if not conditions:
        return None
    return session.scalar(
        select(VerificationBan)
        .where(or_(*conditions), VerificationBan.lifted_at.is_(None), or_(VerificationBan.until.is_(None), VerificationBan.until > now))
        .limit(1)
    )


def counted_rejections(session: Session, user_id: uuid.UUID) -> list[VerificationCase]:
    """Rejections that count toward the cooldown ladder; an overturned appeal removes one."""
    overturned = select(Appeal.verification_case_id).where(Appeal.state == "overturned", Appeal.verification_case_id.is_not(None))
    return list(
        session.scalars(
            select(VerificationCase)
            .where(
                VerificationCase.applicant_user_id == user_id,
                VerificationCase.state == "rejected",
                or_(VerificationCase.decision_reason.is_(None), VerificationCase.decision_reason.not_in(NOT_COUNTED_REJECTIONS)),
                VerificationCase.id.not_in(overturned),
            )
            .order_by(VerificationCase.decided_at.desc())
        )
    )


def cooldown_until(session: Session, user_id: uuid.UUID) -> datetime | None:
    rejections = counted_rejections(session, user_id)
    if not rejections or rejections[0].decided_at is None:
        return None
    count = len(rejections)
    if count > len(REJECTION_COOLDOWNS):
        return None  # the third rejection is a ban, enforced through verification_bans
    until = rejections[0].decided_at + REJECTION_COOLDOWNS[count - 1]
    return until if until > _now() else None


def _own_case(session: Session, principal: Principal, case_id: uuid.UUID) -> VerificationCase:
    case = session.scalar(select(VerificationCase).where(VerificationCase.id == case_id).with_for_update())
    if case is None or case.applicant_user_id != principal.user.id:
        raise ApiError("NOT_FOUND")
    return case


def required_steps(case: VerificationCase) -> tuple[str, ...]:
    if case.purpose == "renewal":
        return ("eligibility", "document", "selfie")
    if case.purpose == "student_update":
        return ("eligibility", "student")
    steps = ["eligibility", "personal", "phone", "document", "selfie"]
    if case.occupation == "STUDENT":
        steps.insert(4, "student")
    return tuple(steps)


def _editable(case: VerificationCase, step: str) -> None:
    if case.state == "draft":
        if step not in required_steps(case) and step != "emergency":
            raise ApiError("TRANSITION_NOT_ALLOWED")
        return
    if case.state == "needs_clarification" and step in (case.clarification_steps or []):
        return
    raise ApiError("TRANSITION_NOT_ALLOWED")


# ======================================================================================
# open a case
# ======================================================================================


def open_case(session: Session, principal: Principal, *, purpose: str = "initial") -> VerificationCase:
    from app.admin.cases import ensure_not_restricted

    settings = get_settings()
    user = principal.user
    if user.email_verified_at is None:
        raise ApiError("EMAIL_NOT_VERIFIED")  # VF-01
    ensure_not_restricted(session, user.id)
    if active_ban(session, user_id=user.id):
        raise ApiError("VERIFICATION_BANNED")
    verified = active_verification(session, user.id)
    if purpose == "initial" and verified is not None:
        raise ApiError("ALREADY_VERIFIED")
    if purpose in ("renewal", "student_update"):
        previous = last_verification(session, user.id)
        if previous is None or previous.revoked_at is not None:
            raise ApiError("VERIFICATION_REQUIRED")
        if purpose == "renewal" and previous.expires_at and previous.expires_at - _now() > timedelta(days=30):
            raise ApiError("TRANSITION_NOT_ALLOWED")  # renewal opens 30 days before it is due
    if purpose == "initial":
        until = cooldown_until(session, user.id)
        if until is not None:
            raise ApiError("VERIFICATION_COOLDOWN", headers={"Retry-After": str(int((until - _now()).total_seconds()))})
    started_today = session.scalar(
        select(func.count()).select_from(VerificationCase).where(VerificationCase.applicant_user_id == user.id, VerificationCase.created_at > _now() - timedelta(days=1))
    ) or 0
    if started_today >= settings.verification_drafts_per_day:
        raise ApiError("RATE_LIMITED", headers={"Retry-After": "3600"})
    now = _now()
    case = VerificationCase(
        applicant_user_id=user.id, state="draft", purpose=purpose, draft_expires_at=now + timedelta(days=settings.verification_draft_days)
    )
    try:
        with session.begin_nested():
            session.add(case)
            session.flush()
    except IntegrityError as error:
        raise ApiError("VERIFICATION_ALREADY_OPEN") from error
    if purpose in ("renewal", "student_update"):
        _copy_from_last_approved(session, case)
    audit.record(session, actor=principal, action="verification.draft_started", target_type="verification_case", target_id=case.id, metadata={"purpose": purpose})
    return case


def _copy_from_last_approved(session: Session, case: VerificationCase) -> None:
    """A renewal or student update keeps the already-checked personal details and phone."""
    previous = session.scalar(
        select(VerificationCase)
        .where(VerificationCase.applicant_user_id == case.applicant_user_id, VerificationCase.state == "approved")
        .order_by(VerificationCase.decided_at.desc())
        .limit(1)
    )
    if previous is None:
        return
    for name in ("legal_name_enc", "legal_name_bn_enc", "dob_enc"):
        blob = getattr(previous, name)
        if blob is not None:
            with contextlib.suppress(fieldcrypt.SealError):
                setattr(case, name, fieldcrypt.seal(fieldcrypt.open_bytes(blob, aad=_aad(previous, name)), aad=_aad(case, name)))
    for name in ("birth_year", "gender_claimed", "home_district", "current_area", "occupation", "phone_id", "doc_type", "doc_last4", "doc_hash", "doc_expiry"):
        setattr(case, name, getattr(previous, name))
    if case.purpose == "student_update":
        case.occupation = "STUDENT"
        case.is_student_claim = True


# ======================================================================================
# steps
# ======================================================================================


def save_eligibility(session: Session, principal: Principal, case: VerificationCase, body: dict[str, Any]) -> None:
    if body.get("age_confirmed") is not True:
        raise _invalid("age_confirmed", "REQUIRED")
    if body.get("consent") is not True:
        raise _invalid("consent", "REQUIRED")
    now = _now()
    case.age_confirmed_at = case.age_confirmed_at or now
    case.consent_at = case.consent_at or now


def _age_on(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def save_personal(session: Session, principal: Principal, case: VerificationCase, body: dict[str, Any]) -> None:
    errors: list[dict[str, str]] = []
    name_en = str(body.get("legal_name_en") or "").strip()
    if not (2 <= len(name_en) <= 100) or not re.fullmatch(r"[A-Za-z][A-Za-z .\-']*", name_en):
        errors.append({"field": "legal_name_en", "code": "INVALID_FORMAT"})
    name_bn = str(body.get("legal_name_bn") or "").strip()
    if name_bn and (len(name_bn) > 100 or not re.fullmatch(r"[ঀ-৿ .\-]+", name_bn)):
        errors.append({"field": "legal_name_bn", "code": "INVALID_FORMAT"})
    dob: date | None = None
    try:
        dob = date.fromisoformat(str(body.get("date_of_birth") or ""))
    except ValueError:
        errors.append({"field": "date_of_birth", "code": "INVALID_FORMAT"})
    if dob is not None:
        age = _age_on(dob, _dhaka_today())
        if age < 18:
            errors.append({"field": "date_of_birth", "code": "UNDER_18"})  # VF-02: refused here, before any image
        elif age > 100:
            errors.append({"field": "date_of_birth", "code": "TOO_OLD"})
    gender = body.get("gender")
    if gender not in ("FEMALE", "MALE", "THIRD"):
        errors.append({"field": "gender", "code": "INVALID_VALUE"})
    district = body.get("home_district")
    if district not in geo.DISTRICT_TO_DIVISION:
        errors.append({"field": "home_district", "code": "INVALID_VALUE"})
    area = str(body.get("current_area") or "").strip()
    if len(area) > 60:
        errors.append({"field": "current_area", "code": "TOO_LONG"})
    occupation = body.get("occupation")
    if occupation not in ("STUDENT", "EMPLOYED", "SELF_EMPLOYED", "NOT_WORKING", "OTHER"):
        errors.append({"field": "occupation", "code": "INVALID_VALUE"})
    if errors:
        raise ApiError("VALIDATION_FAILED", field_errors=errors)
    assert dob is not None
    case.legal_name_enc = fieldcrypt.seal(name_en, aad=_aad(case, "legal_name_enc"))
    case.legal_name_bn_enc = fieldcrypt.seal(name_bn, aad=_aad(case, "legal_name_bn_enc")) if name_bn else None
    case.dob_enc = fieldcrypt.seal(dob.isoformat(), aad=_aad(case, "dob_enc"))
    case.birth_year = dob.year
    case.gender_claimed = str(gender)
    case.home_district = str(district)
    case.current_area = area or None
    case.occupation = str(occupation)
    case.is_student_claim = occupation == "STUDENT"
    if not case.is_student_claim:
        case.institution_id = case.institution_other = case.study_end_month = None
        case.institution_email_verified = False


def save_document(session: Session, principal: Principal, case: VerificationCase, body: dict[str, Any]) -> None:
    doc_type = str(body.get("doc_type") or "")
    number = normalise_document(doc_type, str(body.get("doc_number") or ""))
    expiry: date | None = None
    if body.get("doc_expiry"):
        try:
            expiry = date.fromisoformat(str(body["doc_expiry"]))
        except ValueError as error:
            raise _invalid("doc_expiry", "INVALID_FORMAT") from error
    if doc_type in ("PASSPORT", "DRIVING_LICENCE"):
        if expiry is None:
            raise _invalid("doc_expiry", "REQUIRED")
        if expiry <= _dhaka_today():
            raise _invalid("doc_expiry", "EXPIRED")
    hashed = doc_hash(doc_type, number)
    candidates = _candidates(DOC_LABEL, f"{doc_type}:{number}")
    banned = session.scalar(
        select(VerificationBan.id).where(
            VerificationBan.doc_hash.in_(candidates), VerificationBan.lifted_at.is_(None), or_(VerificationBan.until.is_(None), VerificationBan.until > _now())
        )
    )
    linked = session.scalar(
        select(VerificationCase.id).where(
            VerificationCase.doc_hash.in_(candidates), VerificationCase.state == "approved", VerificationCase.applicant_user_id != case.applicant_user_id
        )
    )
    if banned or linked:
        audit.record(session, actor=principal, action="verification.duplicate_blocked", target_type="verification_case", target_id=case.id, metadata={"what": "document"})
        raise ApiError("DOCUMENT_ALREADY_LINKED")  # VF-03: never says which account
    if case.doc_type and case.doc_type != doc_type:
        # a different kind of document: its photos no longer apply
        for item in session.scalars(select(VerificationEvidence).where(VerificationEvidence.case_id == case.id, VerificationEvidence.kind.in_(("DOC_FRONT", "DOC_BACK")), VerificationEvidence.status == "uploaded")):
            item.status, item.deleted_at = "deleted", _now()
    case.doc_type = doc_type
    case.doc_number_enc = fieldcrypt.seal(number, aad=_aad(case, "doc_number_enc"))
    case.doc_last4 = number[-4:]
    case.doc_hash = hashed
    case.doc_expiry = expiry


def save_student(session: Session, principal: Principal, case: VerificationCase, body: dict[str, Any]) -> None:
    if case.occupation != "STUDENT" and case.purpose != "student_update":
        raise ApiError("TRANSITION_NOT_ALLOWED")
    institution_id = body.get("institution_id")
    other = str(body.get("institution_other") or "").strip()
    if institution_id:
        try:
            parsed = uuid.UUID(str(institution_id))
        except ValueError as error:
            raise _invalid("institution_id", "INVALID_UUID") from error
        if session.get(Institution, parsed) is None:
            raise _invalid("institution_id", "INVALID_VALUE")
        case.institution_id, case.institution_other = parsed, None
    elif 3 <= len(other) <= 120:
        case.institution_id, case.institution_other = None, other
    else:
        raise _invalid("institution_id", "REQUIRED")
    match = re.fullmatch(r"(\d{4})-(\d{2})", str(body.get("study_end") or ""))
    if not match:
        raise _invalid("study_end", "INVALID_FORMAT")
    end = date(int(match.group(1)), int(match.group(2)), 1)
    today = _dhaka_today()
    if end < today.replace(day=1) or end > date(today.year + 6, today.month, 1):
        raise _invalid("study_end", "OUT_OF_RANGE")
    case.study_end_month = end
    case.is_student_claim = True


def save_emergency(session: Session, principal: Principal, case: VerificationCase, body: dict[str, Any]) -> None:
    if body.get("skip") is True:
        return
    name = str(body.get("name") or "").strip()
    relationship = str(body.get("relationship") or "").strip()
    if not (2 <= len(name) <= 80):
        raise _invalid("emergency_name", "INVALID_FORMAT")
    if not (2 <= len(relationship) <= 40):
        raise _invalid("emergency_relationship", "INVALID_FORMAT")
    phone = normalise_any_phone(str(body.get("phone") or ""))
    own = session.get(PhoneNumber, case.phone_id) if case.phone_id else None
    if own is not None and phone.startswith("+880") and phone_hash(phone) == own.phone_hash:
        raise _invalid("emergency_phone", "SAME_AS_OWN")
    value = json.dumps({"name": name, "relationship": relationship, "phone": phone}, ensure_ascii=False)
    sealed = fieldcrypt.seal(value, aad=f"emergency_default:{principal.user.id}")
    row = session.get(EmergencyContactDefault, principal.user.id)
    if row is None:
        session.add(EmergencyContactDefault(user_id=principal.user.id, sealed=sealed, updated_at=_now()))
    else:
        row.sealed, row.updated_at = sealed, _now()


SAVERS = {
    "eligibility": save_eligibility,
    "personal": save_personal,
    "document": save_document,
    "student": save_student,
    "emergency": save_emergency,
}


def save_step(session: Session, principal: Principal, case_id: uuid.UUID, step: str, body: dict[str, Any]) -> VerificationCase:
    if step not in SAVERS:
        raise ApiError("NOT_FOUND") if step not in STEPS else ApiError("TRANSITION_NOT_ALLOWED")
    fieldcrypt.require_configured()
    case = _own_case(session, principal, case_id)
    _editable(case, step)
    SAVERS[step](session, principal, case, body)
    case.updated_at = _now()
    audit.record(session, actor=principal, action="verification.step_saved", target_type="verification_case", target_id=case.id, metadata={"step": step})
    return case


# ======================================================================================
# one-time codes (phone and academic email)
# ======================================================================================


def _issue_code(
    session: Session, principal: Principal, case: VerificationCase, *, channel: str, purpose: str, target: str, target_hash: bytes
) -> tuple[OneTimeCode, str]:
    settings = get_settings()
    now = _now()
    last = session.scalar(
        select(OneTimeCode).where(OneTimeCode.user_id == principal.user.id, OneTimeCode.purpose == purpose).order_by(OneTimeCode.created_at.desc()).limit(1)
    )
    if last is not None and (now - last.created_at).total_seconds() < settings.otp_resend_seconds:
        wait = settings.otp_resend_seconds - int((now - last.created_at).total_seconds())
        raise ApiError("RATE_LIMITED", headers={"Retry-After": str(max(wait, 1))})
    per_target = session.scalar(
        select(func.count()).select_from(OneTimeCode).where(OneTimeCode.target_hash == target_hash, OneTimeCode.created_at > now - timedelta(hours=1))
    ) or 0
    per_account = session.scalar(
        select(func.count()).select_from(OneTimeCode).where(OneTimeCode.user_id == principal.user.id, OneTimeCode.channel == channel, OneTimeCode.created_at > now - timedelta(days=1))
    ) or 0
    if per_target >= settings.otp_codes_per_target_per_hour:
        raise ApiError("RATE_LIMITED", headers={"Retry-After": "3600"})
    if per_account >= settings.otp_codes_per_account_per_day:
        raise ApiError("RATE_LIMITED", headers={"Retry-After": "86400"})
    code = f"{secrets.randbelow(1_000_000):06d}"
    row = OneTimeCode(
        id=uuid.uuid4(), user_id=principal.user.id, case_id=case.id, channel=channel, purpose=purpose, target_hash=target_hash,
        target_enc=fieldcrypt.seal(target, aad=f"otp:{principal.user.id}:{purpose}"), code_hash=b"", expires_at=now + timedelta(seconds=settings.otp_ttl_seconds),
    )
    row.code_hash = _code_hash(row.id, code)
    session.add(row)
    session.flush()
    return row, code


def _check_code(session: Session, principal: Principal, case: VerificationCase, purpose: str, code: str) -> tuple[OneTimeCode, str]:
    settings = get_settings()
    row = session.scalar(
        select(OneTimeCode)
        .where(OneTimeCode.user_id == principal.user.id, OneTimeCode.case_id == case.id, OneTimeCode.purpose == purpose, OneTimeCode.consumed_at.is_(None))
        .order_by(OneTimeCode.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if row is None:
        raise ApiError("CODE_EXPIRED")
    if row.expires_at <= _now():
        raise ApiError("CODE_EXPIRED")
    if row.attempts >= settings.otp_attempts_per_code:
        raise ApiError("CODE_ATTEMPTS_EXCEEDED")
    if not re.fullmatch(r"\d{6}", code or "") or not hmac.compare_digest(_code_hash(row.id, code), row.code_hash):
        row.attempts += 1
        session.commit()  # the failed attempt counts even though the request fails
        raise ApiError("CODE_ATTEMPTS_EXCEEDED" if row.attempts >= settings.otp_attempts_per_code else "CODE_INVALID")
    row.consumed_at = _now()
    target = fieldcrypt.open_text(row.target_enc, aad=f"otp:{principal.user.id}:{purpose}") or ""
    return row, target


def _phone_taken(session: Session, user_id: uuid.UUID, hashes: list[bytes]) -> bool:
    other = session.scalar(
        select(PhoneNumber.id).where(PhoneNumber.phone_hash.in_(hashes), PhoneNumber.verified_at.is_not(None), PhoneNumber.user_id != user_id)
    )
    banned = session.scalar(
        select(VerificationBan.id).where(
            VerificationBan.phone_hash.in_(hashes), VerificationBan.lifted_at.is_(None), or_(VerificationBan.until.is_(None), VerificationBan.until > _now())
        )
    )
    return bool(other or banned)


def send_phone_code(session: Session, principal: Principal, case_id: uuid.UUID, raw_phone: str) -> dict[str, Any]:
    fieldcrypt.require_configured()
    case = _own_case(session, principal, case_id)
    _editable(case, "phone")
    e164 = normalise_phone(raw_phone)
    if _phone_taken(session, principal.user.id, _candidates(PHONE_LABEL, e164)):
        audit.record(session, actor=principal, action="verification.duplicate_blocked", target_type="verification_case", target_id=case.id, metadata={"what": "phone"})
        raise ApiError("PHONE_ALREADY_LINKED")  # VF-03
    row, code = _issue_code(session, principal, case, channel="sms", purpose="phone", target=e164, target_hash=phone_hash(e164))
    get_sms().send(e164, f"Abhijatri: your code is {code}. It is valid for 5 minutes. / অভিযাত্রী কোড {code} (৫ মিনিট)।")
    audit.record(session, actor=principal, action="verification.phone_code_sent", target_type="verification_case", target_id=case.id, metadata={"last4": e164[-4:]})
    settings = get_settings()
    return {"sent_to": f"•••• {e164[-4:]}", "expires_in": settings.otp_ttl_seconds, "resend_after": settings.otp_resend_seconds}


def verify_phone_code(session: Session, principal: Principal, case_id: uuid.UUID, code: str) -> VerificationCase:
    case = _own_case(session, principal, case_id)
    _editable(case, "phone")
    _, e164 = _check_code(session, principal, case, "phone", code)
    hashed = phone_hash(e164)
    if _phone_taken(session, principal.user.id, _candidates(PHONE_LABEL, e164)):
        raise ApiError("PHONE_ALREADY_LINKED")
    row = session.scalar(select(PhoneNumber).where(PhoneNumber.user_id == principal.user.id, PhoneNumber.phone_hash == hashed))
    now = _now()
    if row is None:
        row = PhoneNumber(user_id=principal.user.id, phone_hash=hashed, phone_enc=fieldcrypt.seal(e164, aad=f"phone:{principal.user.id}"), last4=e164[-4:])
        session.add(row)
    row.verified_at = now
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError as error:
        raise ApiError("PHONE_ALREADY_LINKED") from error
    case.phone_id, case.updated_at = row.id, now
    audit.record(session, actor=principal, action="verification.phone_verified", target_type="verification_case", target_id=case.id, metadata={"last4": row.last4})
    return case


def _academic_domain_ok(session: Session, domain: str) -> bool:
    if domain.endswith(ACADEMIC_SUFFIXES):
        return True
    return session.scalar(select(Institution.id).where(Institution.email_domain == domain, Institution.active.is_(True))) is not None


def send_student_email_code(session: Session, principal: Principal, case_id: uuid.UUID, email: str) -> dict[str, Any]:
    from app.auth.mail import deliver
    from app.notify.providers import Email

    fieldcrypt.require_configured()
    case = _own_case(session, principal, case_id)
    _editable(case, "student")
    address = (email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]{1,64}@[a-z0-9.\-]{3,120}", address):
        raise _invalid("email", "INVALID_FORMAT")
    if not _academic_domain_ok(session, address.split("@", 1)[1]):
        raise _invalid("email", "NOT_ACADEMIC")
    row, code = _issue_code(session, principal, case, channel="email", purpose="student_email", target=address, target_hash=_keyed(EMAIL_LABEL, address))
    deliver(
        Email(
            to=address,
            subject="Abhijatri student email code / শিক্ষার্থী ইমেইল কোড",
            text=f"Your code is {code}. It is valid for 5 minutes.\nআপনার কোড {code}। ৫ মিনিট বৈধ।",
            html=f"<p>Your code is <strong>{code}</strong>. It is valid for 5 minutes.</p><p>আপনার কোড <strong>{code}</strong>। ৫ মিনিট বৈধ।</p>",
            idempotency_key=f"student-email-{row.id}",
        )
    )
    settings = get_settings()
    return {"sent_to": address, "expires_in": settings.otp_ttl_seconds, "resend_after": settings.otp_resend_seconds}


def verify_student_email_code(session: Session, principal: Principal, case_id: uuid.UUID, code: str) -> VerificationCase:
    case = _own_case(session, principal, case_id)
    _editable(case, "student")
    _check_code(session, principal, case, "student_email", code)
    case.institution_email_verified, case.updated_at = True, _now()
    audit.record(session, actor=principal, action="verification.student_email_verified", target_type="verification_case", target_id=case.id)
    return case


# ======================================================================================
# liveness and evidence
# ======================================================================================


def issue_liveness(session: Session, principal: Principal, case_id: uuid.UUID) -> dict[str, Any]:
    case = _own_case(session, principal, case_id)
    _editable(case, "selfie")
    gesture = secrets.choice(GESTURES)
    case.liveness_code = f"{secrets.randbelow(10_000):04d}"
    case.liveness_gesture = gesture[0]
    case.liveness_issued_at = _now()
    audit.record(session, actor=principal, action="verification.liveness_issued", target_type="verification_case", target_id=case.id)
    challenge = liveness_view(case)
    assert challenge is not None
    return challenge


def liveness_view(case: VerificationCase) -> dict[str, Any] | None:
    if not case.liveness_code or not case.liveness_issued_at:
        return None
    labels = next((g for g in GESTURES if g[0] == case.liveness_gesture), None)
    return {
        "code": case.liveness_code,
        "gesture": case.liveness_gesture,
        "gesture_bn": labels[1] if labels else None,
        "gesture_en": labels[2] if labels else None,
        "issued_at": case.liveness_issued_at.isoformat(),
        "valid_until": (case.liveness_issued_at + LIVENESS_VALID).isoformat(),
    }


def _step_for_kind(kind: str) -> str:
    return {"DOC_FRONT": "document", "DOC_BACK": "document", "SELFIE": "selfie", "STUDENT_CARD": "student"}[kind]


def request_evidence(session: Session, storage: StorageClient, principal: Principal, case_id: uuid.UUID, *, kind: str, content_type: str, size_bytes: int) -> dict[str, Any]:
    settings = get_settings()
    fieldcrypt.require_configured()
    case = _own_case(session, principal, case_id)
    if kind not in ("DOC_FRONT", "DOC_BACK", "SELFIE", "STUDENT_CARD"):
        raise _invalid("kind", "INVALID_VALUE")
    _editable(case, _step_for_kind(kind))
    if case.purpose == "initial" and case.birth_year is None:
        raise ApiError("STEPS_INCOMPLETE")  # VF-02: nothing is uploaded before the age check passed
    if content_type not in QUARANTINE_TYPES:
        raise _invalid("content_type", "INVALID_VALUE")
    if not 0 < size_bytes <= QUARANTINE_MAX_BYTES:
        raise _invalid("size_bytes", "TOO_LARGE")
    if kind == "DOC_BACK" and case.doc_type not in ("NID", "DRIVING_LICENCE"):
        raise _invalid("kind", "NOT_NEEDED")
    if kind in ("DOC_FRONT", "DOC_BACK") and not case.doc_type:
        raise ApiError("STEPS_INCOMPLETE")
    if kind == "STUDENT_CARD" and not case.is_student_claim:
        raise _invalid("kind", "NOT_NEEDED")
    challenge = None
    if kind == "SELFIE":
        if not case.liveness_issued_at or _now() - case.liveness_issued_at > LIVENESS_VALID:
            raise ApiError("LIVENESS_REQUIRED")  # VF-04: no selfie without a challenge issued for this case
        challenge = f"{case.liveness_code}|{case.liveness_gesture}"
    uploads = session.scalar(select(func.count()).select_from(VerificationEvidence).where(VerificationEvidence.case_id == case.id)) or 0
    if uploads >= settings.verification_uploads_per_case:
        raise ApiError("RATE_LIMITED", headers={"Retry-After": "86400"})
    evidence = VerificationEvidence(
        id=uuid.uuid4(), case_id=case.id, kind=kind, content_type=content_type, uploaded_by=principal.user.id, challenge=challenge,
    )
    evidence.object_key = f"{case.id}/{evidence.id}"
    session.add(evidence)
    session.flush()
    upload_url = storage.signed_upload_url(evidence.object_key, bucket=QUARANTINE_BUCKET)
    audit.record(session, actor=principal, action="evidence.upload_requested", target_type="verification_case", target_id=case.id, metadata={"evidence_id": str(evidence.id), "kind": kind})
    return {"evidence_id": str(evidence.id), "upload_url": upload_url, "content_type": content_type, "max_bytes": QUARANTINE_MAX_BYTES, "kind": kind}


def _reused(session: Session, evidence: VerificationEvidence, applicant_id: uuid.UUID, sha: bytes, phash: bytes) -> bool:
    exact = session.scalar(
        select(VerificationEvidence.id)
        .join(VerificationCase, VerificationCase.id == VerificationEvidence.case_id)
        .where(VerificationEvidence.sha256 == sha, VerificationEvidence.id != evidence.id, VerificationCase.applicant_user_id != applicant_id)
    )
    if exact:
        return True
    others = session.scalars(
        select(VerificationEvidence.phash)
        .join(VerificationCase, VerificationCase.id == VerificationEvidence.case_id)
        .where(
            VerificationEvidence.phash.is_not(None), VerificationEvidence.kind == evidence.kind, VerificationEvidence.id != evidence.id,
            VerificationCase.applicant_user_id != applicant_id,
        )
        .order_by(VerificationEvidence.created_at.desc())
        .limit(5000)
    )
    return any(other is not None and images.hamming(other, phash) <= 4 for other in others)


def complete_evidence(session: Session, storage: StorageClient, principal: Principal, case_id: uuid.UUID, evidence_id: uuid.UUID) -> VerificationEvidence:
    import io

    case = _own_case(session, principal, case_id)
    evidence = session.get(VerificationEvidence, evidence_id)
    if evidence is None or evidence.case_id != case.id or evidence.status == "deleted":
        raise ApiError("NOT_FOUND")
    if evidence.status == "uploaded":
        return evidence
    _editable(case, _step_for_kind(evidence.kind))
    if not storage.exists(evidence.object_key, bucket=QUARANTINE_BUCKET):
        raise _invalid("evidence", "NOT_UPLOADED")
    buffer = io.BytesIO()
    try:
        storage.download(evidence.object_key, buffer, QUARANTINE_BUCKET, QUARANTINE_MAX_BYTES)
    except ValueError as error:
        storage.delete([evidence.object_key], bucket=QUARANTINE_BUCKET)
        evidence.status, evidence.deleted_at = "deleted", _now()
        session.commit()
        raise _invalid("file", "TOO_LARGE") from error
    raw = buffer.getvalue()
    try:
        cleaned = images.clean(raw)
    except images.ImageRejected as rejected:
        storage.delete([evidence.object_key], bucket=QUARANTINE_BUCKET)
        evidence.status, evidence.deleted_at = "deleted", _now()
        session.commit()
        raise _invalid("file", rejected.code) from rejected
    sha = hashlib.sha256(raw).digest()
    flags = list(cleaned.flags)
    if _reused(session, evidence, case.applicant_user_id, sha, cleaned.phash):
        flags.append("image_reused")
    sealed_key = f"{case.id}/{evidence.id}.sealed"
    storage.upload(sealed_key, fieldcrypt.seal(cleaned.jpeg, aad=f"evidence:{evidence.id}"), "application/octet-stream", SEALED_BUCKET)
    storage.delete([evidence.object_key], bucket=QUARANTINE_BUCKET)  # the original never stays (9.2)
    # one current image per kind: an earlier one of the same kind is replaced
    for old in session.scalars(
        select(VerificationEvidence).where(
            VerificationEvidence.case_id == case.id, VerificationEvidence.kind == evidence.kind, VerificationEvidence.status == "uploaded", VerificationEvidence.id != evidence.id
        )
    ):
        if old.sealed_key:
            storage.delete([old.sealed_key], bucket=SEALED_BUCKET)
        old.status, old.deleted_at = "deleted", _now()
    if evidence.kind == "SELFIE" and evidence.challenge != f"{case.liveness_code}|{case.liveness_gesture}":
        flags.append("liveness_changed")
    evidence.status, evidence.sha256, evidence.phash, evidence.sealed_key, evidence.flags = "uploaded", sha, cleaned.phash, sealed_key, flags
    evidence.content_type = "image/jpeg"
    case.updated_at = _now()
    audit.record(session, actor=principal, action="evidence.uploaded", target_type="verification_case", target_id=case.id, metadata={"evidence_id": str(evidence.id), "kind": evidence.kind, "flags": flags})
    return evidence


# ======================================================================================
# completeness, submit, respond, withdraw
# ======================================================================================


def _current_evidence(session: Session, case: VerificationCase) -> dict[str, VerificationEvidence]:
    rows = session.scalars(
        select(VerificationEvidence).where(VerificationEvidence.case_id == case.id, VerificationEvidence.status == "uploaded").order_by(VerificationEvidence.created_at)
    )
    return {row.kind: row for row in rows}


def step_status(session: Session, case: VerificationCase) -> dict[str, bool]:
    evidence = _current_evidence(session, case)
    phone = session.get(PhoneNumber, case.phone_id) if case.phone_id else None
    doc_ok = bool(case.doc_type and case.doc_hash and "DOC_FRONT" in evidence)
    if case.doc_type in ("NID", "DRIVING_LICENCE"):
        doc_ok = doc_ok and "DOC_BACK" in evidence
    if case.doc_type in ("PASSPORT", "DRIVING_LICENCE"):
        doc_ok = doc_ok and case.doc_expiry is not None
    selfie = evidence.get("SELFIE")
    return {
        "eligibility": bool(case.age_confirmed_at and case.consent_at),
        "personal": bool(case.legal_name_enc and case.dob_enc and case.birth_year and case.gender_claimed and case.home_district and case.occupation),
        "phone": bool(phone and phone.verified_at),
        "document": doc_ok,
        "student": bool((case.institution_id or case.institution_other) and case.study_end_month and "STUDENT_CARD" in evidence),
        "selfie": bool(selfie and selfie.challenge),
        "emergency": True,
    }


def _risk_flags(session: Session, case: VerificationCase, user: User, network: bytes | None) -> list[str]:
    flags: set[str] = set()
    for item in _current_evidence(session, case).values():
        flags.update(item.flags or [])
    if user.created_at and _now() - user.created_at < timedelta(hours=24):
        flags.add("new_account")
    if case.doc_hash:
        other = session.scalar(
            select(VerificationCase.id).where(
                VerificationCase.doc_hash == case.doc_hash, VerificationCase.applicant_user_id != case.applicant_user_id, VerificationCase.state != "draft"
            )
        )
        if other:
            flags.add("document_reused")
    if network is not None:
        burst = session.scalar(
            select(func.count()).select_from(VerificationCase).where(VerificationCase.network_hash == network, VerificationCase.submitted_at > _now() - timedelta(days=1))
        ) or 0
        if burst >= 2:
            flags.add("burst_network")
    return sorted(flags)


def submit(
    session: Session, principal: Principal, case_id: uuid.UUID, *, declaration: bool, network: bytes | None,
) -> VerificationCase:
    settings = get_settings()
    case = _own_case(session, principal, case_id)
    if case.state != "draft":
        raise ApiError("TRANSITION_NOT_ALLOWED")
    if not declaration:
        raise _invalid("declaration", "REQUIRED")
    if principal.user.email_verified_at is None:
        raise ApiError("EMAIL_NOT_VERIFIED")
    if active_ban(session, user_id=principal.user.id):
        raise ApiError("VERIFICATION_BANNED")
    status = step_status(session, case)
    missing = [step for step in required_steps(case) if not status[step]]
    if missing:
        raise ApiError("STEPS_INCOMPLETE", field_errors=[{"field": step, "code": "INCOMPLETE"} for step in missing])
    today = session.scalar(
        select(func.count()).select_from(VerificationCase).where(VerificationCase.applicant_user_id == principal.user.id, VerificationCase.submitted_at > _now() - timedelta(days=1))
    ) or 0
    if today >= settings.verification_submissions_per_day:
        raise ApiError("RATE_LIMITED", headers={"Retry-After": "86400"})
    if case.doc_hash is not None:
        linked = session.scalar(
            select(VerificationCase.id).where(
                VerificationCase.doc_hash == case.doc_hash, VerificationCase.state == "approved", VerificationCase.applicant_user_id != case.applicant_user_id
            )
        )
        if linked or active_ban(session, doc=case.doc_hash):
            raise ApiError("DOCUMENT_ALREADY_LINKED")
    now = _now()
    case.risk_flags = _risk_flags(session, case, principal.user, network)
    case.network_hash = network
    case.declaration_at, case.submitted_at, case.draft_expires_at, case.updated_at = now, now, None, now
    case.version += 1
    if case.risk_flags:
        # any flag needs a superadmin decision (6.2 "second approval", 10.2)
        case.state = "escalated"
        tasks.ensure_task(session, "verification", case.id, priority=1, required_role="superadmin")
        for task in session.scalars(select(ModerationTask).where(ModerationTask.subject_id == case.id, ModerationTask.status == "open")):
            task.escalated = True
    else:
        case.state = "submitted"
        tasks.ensure_task(session, "verification", case.id)
    audit.record(session, actor=principal, action="verification.submitted", target_type="verification_case", target_id=case.id, metadata={"risk_flags": case.risk_flags, "purpose": case.purpose})
    events.emit(
        session, "verification.submitted", case.id,
        {"case_id": str(case.id), "applicant_id": str(principal.user.id)}, aggregate_type="verification", staff_roles=("moderator", "superadmin"), exclude=principal.user.id,
    )
    return case


def respond(session: Session, principal: Principal, case_id: uuid.UUID) -> VerificationCase:
    case = _own_case(session, principal, case_id)
    if case.state != "needs_clarification":
        raise ApiError("TRANSITION_NOT_ALLOWED")
    status = step_status(session, case)
    missing = [step for step in (case.clarification_steps or []) if not status.get(step, True)]
    if missing:
        raise ApiError("STEPS_INCOMPLETE", field_errors=[{"field": step, "code": "INCOMPLETE"} for step in missing])
    case.state, case.version, case.updated_at, case.clarification_due_at = "submitted", case.version + 1, _now(), None
    tasks.ensure_task(session, "verification", case.id, required_role="superadmin" if case.risk_flags else "moderator")
    audit.record(session, actor=principal, action="verification.responded", target_type="verification_case", target_id=case.id, metadata={"steps": case.clarification_steps or []})
    events.emit(session, "verification.state_changed", case.id, {"case_id": str(case.id), "state": "submitted", "applicant_id": str(case.applicant_user_id)}, aggregate_type="verification")
    return case


def withdraw(session: Session, storage: StorageClient, principal: Principal, case_id: uuid.UUID) -> VerificationCase:
    case = _own_case(session, principal, case_id)
    if case.state not in OPEN_STATES:
        raise ApiError("TRANSITION_NOT_ALLOWED")
    was_draft = case.state == "draft"
    case.state, case.version, case.updated_at = "withdrawn", case.version + 1, _now()
    # a discarded draft is erased at once; a withdrawn application waits 30 days like a rejection (9.5)
    case.purge_after = _now() if was_draft else _now() + timedelta(days=30)
    tasks.cancel_open_tasks(session, case.id)
    audit.record(session, actor=principal, action="verification.withdrawn", target_type="verification_case", target_id=case.id, metadata={"from_draft": was_draft})
    if not was_draft:
        events.emit(session, "verification.state_changed", case.id, {"case_id": str(case.id), "state": "withdrawn", "applicant_id": str(case.applicant_user_id)}, aggregate_type="verification")
    return case


# ======================================================================================
# views
# ======================================================================================


def _open(case: VerificationCase, name: str) -> str | None:
    try:
        return fieldcrypt.open_text(getattr(case, name), aad=_aad(case, name))
    except fieldcrypt.SealError:
        return None


def institutions(session: Session, query: str | None) -> list[dict[str, Any]]:
    statement = select(Institution).where(Institution.active.is_(True)).order_by(Institution.name_en).limit(30)
    if query:
        like = f"%{query.strip()}%"
        statement = statement.where(or_(Institution.name_en.ilike(like), Institution.name_bn.ilike(like)))
    return [{"id": str(i.id), "name_en": i.name_en, "name_bn": i.name_bn, "kind": i.kind} for i in session.scalars(statement)]


def own_view(session: Session, case: VerificationCase) -> dict[str, Any]:
    """Everything the applicant entered, back to them (section 7: the person sees all of their own data)."""
    from app import reasons

    phone = session.get(PhoneNumber, case.phone_id) if case.phone_id else None
    institution = session.get(Institution, case.institution_id) if case.institution_id else None
    evidence = _current_evidence(session, case)
    status = step_status(session, case)
    label = None
    if case.state == "rejected" and case.decision_reason:
        found = next((r for r in reasons.GROUPS["verification_reject"][1] if r.code == case.decision_reason), None)
        label = {"code": case.decision_reason, "bn": found.bn if found else case.decision_reason, "en": found.en if found else case.decision_reason}
    elif case.state == "needs_clarification" and case.decision_reason:
        found = next((r for r in reasons.GROUPS["verification_clarify"][1] if r.code == case.decision_reason), None)
        label = {"code": case.decision_reason, "bn": found.bn if found else case.decision_reason, "en": found.en if found else case.decision_reason}
    return {
        "id": str(case.id),
        "state": case.state,
        "purpose": case.purpose,
        "version": case.version,
        "required_steps": list(required_steps(case)),
        "steps": status,
        "personal": {
            "legal_name_en": _open(case, "legal_name_enc"),
            "legal_name_bn": _open(case, "legal_name_bn_enc"),
            "date_of_birth": _open(case, "dob_enc"),
            "gender": case.gender_claimed,
            "home_district": case.home_district,
            "home_division": geo.division_of(case.home_district),
            "current_area": case.current_area,
            "occupation": case.occupation,
        },
        "phone": {"last4": phone.last4, "verified": phone.verified_at is not None} if phone else None,
        "document": {"doc_type": case.doc_type, "last4": case.doc_last4, "expiry": case.doc_expiry.isoformat() if case.doc_expiry else None} if case.doc_type else None,
        "student": {
            "institution_id": str(case.institution_id) if case.institution_id else None,
            "institution_name": institution.name_en if institution else case.institution_other,
            "study_end": case.study_end_month.strftime("%Y-%m") if case.study_end_month else None,
            "email_verified": case.institution_email_verified,
        } if case.is_student_claim else None,
        "liveness": liveness_view(case) if case.state in EDITABLE_STATES else None,
        "evidence": {kind: {"id": str(item.id), "created_at": item.created_at.isoformat()} for kind, item in evidence.items()},
        "clarification_steps": case.clarification_steps or [],
        "decision_reason": label,
        "decision_note": case.decision_note if case.state == "needs_clarification" else None,  # the moderator's question
        "clarification_due_at": case.clarification_due_at.isoformat() if case.clarification_due_at else None,
        "draft_expires_at": case.draft_expires_at.isoformat() if case.draft_expires_at else None,
        "submitted_at": case.submitted_at.isoformat() if case.submitted_at else None,
        "decided_at": case.decided_at.isoformat() if case.decided_at else None,
        "created_at": case.created_at.isoformat(),
    }


def mine(session: Session, principal: Principal) -> dict[str, Any]:
    user_id = principal.user.id
    latest = session.scalar(select(VerificationCase).where(VerificationCase.applicant_user_id == user_id).order_by(VerificationCase.created_at.desc()).limit(1))
    verification = last_verification(session, user_id)
    attributes = session.get(VerificationAttributes, user_id)
    now = _now()
    state = None
    if verification is not None:
        if verification.revoked_at is not None:
            state = "revoked"
        elif verification.expires_at is not None and verification.expires_at <= now:
            state = "lapsed"
        elif verification.expires_at is not None and verification.expires_at - now <= timedelta(days=30):
            state = "renewal_due"
        else:
            state = "active"
    ban = active_ban(session, user_id=user_id)
    contact = session.get(EmergencyContactDefault, user_id)
    emergency = None
    if contact is not None:
        try:
            emergency = json.loads(fieldcrypt.open_text(contact.sealed, aad=f"emergency_default:{user_id}") or "{}")
        except (fieldcrypt.SealError, ValueError):
            emergency = None
    return {
        "verified_member": state in ("active", "renewal_due"),
        "verification": {
            "state": state,
            "decided_at": verification.decided_at.isoformat() if verification and verification.decided_at else None,
            "renewal_due_at": verification.expires_at.isoformat() if verification and verification.expires_at else None,
        } if verification else None,
        "attributes": {
            "gender": attributes.gender,
            "birth_year": attributes.birth_year,
            "is_student": attributes.is_student,
            "student_until": attributes.student_until.isoformat() if attributes.student_until else None,
            "home_district": attributes.home_district,
        } if attributes else None,
        "emergency_contact": emergency,
        "email_verified": principal.user.email_verified_at is not None,
        "cooldown_until": (cooldown_until(session, user_id) or None) and cooldown_until(session, user_id).isoformat(),  # type: ignore[union-attr]
        "banned_until": (ban.until.isoformat() if ban.until else "permanent") if ban else None,
        "case": own_view(session, latest) if latest else None,
    }
