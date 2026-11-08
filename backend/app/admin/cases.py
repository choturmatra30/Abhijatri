"""Verification cases, enforcement and sanctions, and appeals (Moderation spec 6.2 to 6.5, 7.1 to 7.4).

Each workflow has an explicit transition table below; anything not listed is refused with 422. Every
change re-checks state, version and (for staff) the claim lease, writes an audit event and an outbox
event, and is committed once by the route. Times are server UTC; appeal deadlines are the end of the
30th day in the display time zone (Asia/Dhaka).
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin import audit, tasks
from app.auth.sessions import Principal
from app.errors import ApiError
from app.models import (
    Appeal,
    EnforcementCase,
    Institution,
    ModerationActionRecord,
    ModerationDecision,
    ModerationTask,
    PhoneNumber,
    Review,
    ReviewStatus,
    Sanction,
    User,
    UserRole,
    Verification,
    VerificationAttributes,
    VerificationBan,
    VerificationCase,
    VerificationEvidence,
)
from app.notify import events
from app.services import ReviewError, appeal_deadline, moderate_review, set_hidden_rating_kept
from app.storage import StorageClient

APPROVED_EVIDENCE_HOURS = 24  # Security 3.7: evidence is erased within 24 hours of a decision
REJECTED_CASE_DAYS = 30  # spec 10: rejected verification cases are kept 30 days
EMERGENCY_FOLLOW_UP_HOURS = 24
MAX_EVIDENCE = 3

# ---- transition tables (spec 7) ----

# (from, to) -> who may request it
VERIFICATION_TRANSITIONS: dict[tuple[str, str], frozenset[str]] = {
    # staff (the applicant's own moves live in app.verification.service: submit, respond, withdraw)
    ("submitted", "in_review"): frozenset({"moderator", "superadmin"}),
    ("in_review", "needs_clarification"): frozenset({"moderator", "superadmin"}),
    ("in_review", "approved"): frozenset({"moderator", "superadmin"}),
    ("in_review", "rejected"): frozenset({"moderator", "superadmin"}),
    ("submitted", "escalated"): frozenset({"moderator", "superadmin"}),
    ("in_review", "escalated"): frozenset({"moderator", "superadmin"}),
    ("escalated", "approved"): frozenset({"superadmin"}),
    ("escalated", "rejected"): frozenset({"superadmin"}),
    ("escalated", "needs_clarification"): frozenset({"superadmin"}),
}
ENFORCEMENT_ACTIONS: dict[str, frozenset[str]] = {  # action -> states it may start from
    "remove": frozenset({"taken_down"}),
    "restore": frozenset({"taken_down", "removed"}),
    "close": frozenset({"open"}),
}
APPEAL_OUTCOMES = frozenset({"upheld", "overturned"})
APPEALABLE_DECISIONS = frozenset({ModerationDecision.REJECT, ModerationDecision.HIDE})


def _now() -> datetime:
    return datetime.now(UTC)


def active_staff_ids(session: Session, *, exclude: uuid.UUID | None = None, roles: tuple[str, ...] = ("moderator", "superadmin")) -> list[str]:
    """The intended staff recipients of an event; re-checked when the notification is created (spec 11)."""
    rows = session.scalars(select(UserRole.user_id).where(UserRole.revoked_at.is_(None), UserRole.role.in_(roles)))
    return [str(user_id) for user_id in rows if user_id != exclude]


def emit(session: Session, topic: str, aggregate_id: uuid.UUID, payload: dict[str, Any]) -> None:
    events.emit(session, topic, aggregate_id, payload, aggregate_type=topic.split(".", 1)[0])


def is_verified_member(session: Session, user_id: uuid.UUID) -> bool:
    now = _now()
    return (
        session.scalar(
            select(Verification.id).where(
                Verification.user_id == user_id,
                Verification.verification_type == "VERIFIED_MEMBER",
                Verification.status == "APPROVED",
                Verification.revoked_at.is_(None),
                (Verification.expires_at.is_(None)) | (Verification.expires_at > now),
            )
        )
        is not None
    )


def _in_force(moment: datetime) -> Any:
    """A sanction is in force while it is active and has not reached its end time. One with only a review date
    (no end time) stays in force until a person reviews it."""
    return and_(Sanction.state == "active", or_(Sanction.ends_at.is_(None), Sanction.ends_at > moment))


def expire_due_sanctions(session: Session, user_id: uuid.UUID | None = None, *, now: datetime | None = None) -> int:
    """End sanctions whose time has passed (Moderation spec P-01). The daily job sweeps everyone; a request that
    meets an expired sanction ends it on the spot, so expiry never depends on that job having run."""
    moment = now or _now()
    statement = (
        select(Sanction)
        .where(Sanction.state == "active", Sanction.ends_at.is_not(None), Sanction.ends_at <= moment)
        .with_for_update(skip_locked=True)
    )
    if user_id is not None:
        statement = statement.where(Sanction.user_id == user_id)
    ended = 0
    for sanction in session.scalars(statement):
        reverse_sanction(session, None, sanction, expired=True)
        ended += 1
    return ended


def ensure_not_restricted(session: Session, user_id: uuid.UUID) -> None:
    """A posting restriction or suspension in force blocks member writes (spec 6.4)."""
    if expire_due_sanctions(session, user_id):
        session.commit()  # the expiry stands even if the request goes on to fail
    restricted = session.scalar(
        select(Sanction.id).where(
            Sanction.user_id == user_id,
            _in_force(_now()),
            Sanction.kind.in_(("posting_restriction", "suspension")),
        )
    )
    if restricted is not None:
        raise ApiError("ACCOUNT_RESTRICTED")


# =========================================================================================
# Verification (spec 6.2, 7.1)
# =========================================================================================


def open_verification(session: Session, applicant: Principal, statement: str | None = None, *, purpose: str = "initial") -> VerificationCase:
    """Start an application as a draft (sign-up form 4). Kept as the entry point other modules call."""
    from app.verification import service

    case = service.open_case(session, applicant, purpose=purpose)
    if statement:
        case.statement = statement
    return case


# Checklist a moderator ticks before approving (sign-up form 6.1). "not_expired" applies to passports and
# licences; "student" only when student status is claimed.
CHECKLIST = ("genuine", "name", "dob", "gender", "number", "not_expired", "face", "liveness", "student", "signals")


def required_checks(case: VerificationCase) -> set[str]:
    required = {"genuine", "name", "dob", "gender", "number", "face", "liveness", "signals"}
    if case.doc_type in ("PASSPORT", "DRIVING_LICENCE"):
        required.add("not_expired")
    if case.is_student_claim:
        required.add("student")
    return required


def renewal_due(decided: datetime, doc_expiry: date | None) -> datetime:
    """Renewal is due 2 years after approval or 30 days before the document expires, whichever is first (5)."""
    from app.config import get_settings

    due = decided + timedelta(days=365 * get_settings().verification_renewal_years)
    if doc_expiry is not None:
        before_expiry = datetime.combine(doc_expiry, datetime.min.time(), tzinfo=UTC) - timedelta(days=30)
        due = min(due, before_expiry)
    return max(due, decided + timedelta(days=1))


def _student_limit(case: VerificationCase, now: datetime) -> date:
    limit = (now + timedelta(days=365)).date()
    if case.study_end_month is not None:
        limit = min(limit, case.study_end_month)
    return limit


def _validated_attributes(case: VerificationCase, attributes: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    """VF-05: an approval names gender and birth year (and student status with its end date)."""
    if not attributes:
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "attributes", "code": "REQUIRED"}])
    errors: list[dict[str, str]] = []
    gender = attributes.get("gender")
    if gender not in ("FEMALE", "MALE", "THIRD"):
        errors.append({"field": "attributes.gender", "code": "REQUIRED"})
    birth_year = attributes.get("birth_year")
    if not isinstance(birth_year, int) or not 1900 <= birth_year <= now.year - 18:
        errors.append({"field": "attributes.birth_year", "code": "INVALID_VALUE"})
    is_student = bool(attributes.get("is_student"))
    student_until: date | None = None
    if is_student:
        try:
            student_until = date.fromisoformat(str(attributes.get("student_until") or ""))
        except ValueError:
            errors.append({"field": "attributes.student_until", "code": "REQUIRED"})
        else:
            if student_until <= now.date() or student_until > (now + timedelta(days=366)).date():
                errors.append({"field": "attributes.student_until", "code": "OUT_OF_RANGE"})
    if errors:
        raise ApiError("VALIDATION_FAILED", field_errors=errors)
    return {"gender": gender, "birth_year": birth_year, "is_student": is_student, "student_until": student_until}


def _write_attributes(session: Session, user_id: uuid.UUID, values: dict[str, Any], *, district: str | None, actor_id: uuid.UUID | None, now: datetime) -> None:
    row = session.get(VerificationAttributes, user_id)
    if row is None:
        row = VerificationAttributes(user_id=user_id, gender=values["gender"], birth_year=values["birth_year"])
        session.add(row)
    row.gender, row.birth_year = values["gender"], values["birth_year"]
    row.is_student, row.student_until = values["is_student"], values["student_until"]
    if district:
        row.home_district = district
    row.set_by, row.set_at = actor_id, now


def _approve(session: Session, principal: Principal, case: VerificationCase, attributes: dict[str, Any] | None, checklist: list[str] | None, now: datetime) -> None:
    from app.verification import service

    if case.doc_type is None and case.purpose == "initial":
        raise ApiError("EVIDENCE_REQUIRED")  # a legacy statement-only case: reject with "use-new-form"
    status = service.step_status(session, case)
    missing = [step for step in service.required_steps(case) if not status[step]]
    if missing:
        raise ApiError("EVIDENCE_REQUIRED")
    unticked = sorted(required_checks(case) - set(checklist or []))
    if unticked:
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": f"checklist.{name}", "code": "REQUIRED"} for name in unticked])
    if case.purpose == "student_update":
        current = session.get(VerificationAttributes, case.applicant_user_id)
        base = {"gender": current.gender, "birth_year": current.birth_year} if current else {}
        values = _validated_attributes(case, {**base, **(attributes or {}), "is_student": True}, now)
    else:
        values = _validated_attributes(case, attributes, now)
    if values["is_student"] and values["student_until"] > _student_limit(case, now):
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "attributes.student_until", "code": "OUT_OF_RANGE"}])
    previous = service.active_verification(session, case.applicant_user_id)
    if case.purpose == "student_update" and previous is not None:
        expires = previous.expires_at
    else:
        expires = renewal_due(now, case.doc_expiry)
    if previous is not None and case.purpose == "renewal":
        previous.status, previous.revoked_at, previous.revocation_reason = "RENEWED", now, "renewed"
    if case.purpose != "student_update" or previous is None:
        session.add(
            Verification(
                user_id=case.applicant_user_id, verification_type="VERIFIED_MEMBER", status="APPROVED", method="DOCUMENT_SELFIE_REVIEW",
                approved_by=principal.user.id, decided_at=now, expires_at=expires,
            )
        )
    _write_attributes(session, case.applicant_user_id, values, district=case.home_district, actor_id=principal.user.id, now=now)
    case.doc_number_enc = None  # the full number is destroyed at approval (8, 9.5); last 4 and the hash stay


def _reject_strikes(session: Session, principal: Principal, case: VerificationCase, reason_code: str, now: datetime) -> None:
    """Third counted rejection, or a fake document: 90-day ban, with the document and phone hashes (10.3)."""
    from app.verification import service

    if reason_code in service.NOT_COUNTED_REJECTIONS:
        return
    count = len(service.counted_rejections(session, case.applicant_user_id))  # includes this case (already rejected)
    if reason_code != "fake-document" and count < 3:
        return
    phone = session.get(PhoneNumber, case.phone_id) if case.phone_id else None
    session.add(
        VerificationBan(
            user_id=case.applicant_user_id, doc_hash=case.doc_hash, phone_hash=phone.phone_hash if phone else None,
            reason=reason_code if reason_code == "fake-document" else "third-rejection", until=now + timedelta(days=service.BAN_DAYS), created_by=principal.user.id,
        )
    )
    audit.record(session, actor=principal, action="verification.banned", target_type="user", target_id=case.applicant_user_id, reason=reason_code, metadata={"days": service.BAN_DAYS})


def staff_verification_transition(
    session: Session,
    principal: Principal,
    *,
    case_id: uuid.UUID,
    to: str,
    expected_version: int,
    task_id: uuid.UUID,
    lease_token: uuid.UUID,
    reason_code: str,
    note: str | None,
    request_id: str | None,
    steps: list[str] | None = None,
    attributes: dict[str, Any] | None = None,
    checklist: list[str] | None = None,
) -> dict[str, Any]:
    from app import reasons
    from app.verification import service

    case = session.scalar(select(VerificationCase).where(VerificationCase.id == case_id).with_for_update())
    if case is None:
        raise ApiError("NOT_FOUND")
    task = tasks.require_lease(session, principal, task_id, lease_token, case_id)
    if case.applicant_user_id == principal.user.id:
        raise ApiError("SELF_MODERATION_FORBIDDEN")  # nobody decides their own case (6)
    if case.version != expected_version:
        raise ApiError("REVIEW_VERSION_CONFLICT")
    allowed = VERIFICATION_TRANSITIONS.get((case.state, to))
    if allowed is None:
        raise ApiError("TRANSITION_NOT_ALLOWED")
    if principal.role not in allowed:
        raise ApiError("FORBIDDEN")
    if case.risk_flags and to in ("approved", "rejected") and principal.role != "superadmin":
        raise ApiError("FORBIDDEN")  # a flagged application needs a superadmin (6.2, 10.2)
    if to == "rejected" and not reasons.is_valid("verification_reject", reason_code):
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "reason_code", "code": "INVALID_VALUE"}])
    if to == "needs_clarification":
        if not reasons.is_valid("verification_clarify", reason_code):
            raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "reason_code", "code": "INVALID_VALUE"}])
        if not note:
            raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "note", "code": "REQUIRED"}])
        chosen = [s for s in (steps or []) if s in service.STEPS and s != "emergency"]
        if not chosen:
            raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "steps", "code": "REQUIRED"}])
    now = _now()
    if to == "approved":
        _approve(session, principal, case, attributes, checklist, now)
    previous = case.state
    case.state, case.version, case.updated_at = to, case.version + 1, now
    if to in ("approved", "rejected"):
        case.decided_by, case.decided_at, case.decision_reason, case.decision_note = principal.user.id, now, reason_code, note
        case.purge_after = now + (timedelta(hours=APPROVED_EVIDENCE_HOURS) if to == "approved" else timedelta(days=REJECTED_CASE_DAYS))
        case.clarification_steps = None
        tasks.complete(task)
        if to == "rejected":
            session.flush()
            _reject_strikes(session, principal, case, reason_code, now)
    elif to == "needs_clarification":
        from app.config import get_settings

        case.decision_reason, case.decision_note = reason_code, note  # the note is the question the applicant sees
        case.clarification_steps = [s for s in (steps or []) if s in service.STEPS and s != "emergency"]
        case.clarification_due_at = now + timedelta(days=get_settings().verification_clarification_days)
        if "selfie" in case.clarification_steps:
            case.liveness_code = case.liveness_gesture = None
            case.liveness_issued_at = None
        tasks.complete(task)  # waits for the applicant; their answer queues it again
    elif to == "escalated":
        task.escalated, task.required_role = True, "superadmin"
        task.claimed_by = task.claimed_at = task.lease_expires_at = task.lease_token = None
        task.version += 1
    audit.record(
        session, actor=principal, action=f"verification.{to}", target_type="verification_case", target_id=case.id,
        reason=reason_code, metadata={"from": previous, "to": to, "version": case.version, "steps": case.clarification_steps or [], "checklist": sorted(checklist or [])},
        request_id=request_id,
    )
    facts = {"case_id": str(case.id), "state": to, "applicant_id": str(case.applicant_user_id)}
    if to == "needs_clarification":
        facts["question"] = (note or "")[:300]  # meant for the applicant; moderator-only notes are never sent
    emit(session, "verification.state_changed", case.id, facts)
    return {"case_id": str(case.id), "state": case.state, "version": case.version}


def reopen_verification(session: Session, principal: Principal, case_id: uuid.UUID, reason_code: str, note: str | None, request_id: str | None) -> dict[str, Any]:
    """A superadmin sends a rejection back to the queue within 30 days (P-05)."""
    if principal.role != "superadmin":
        raise ApiError("FORBIDDEN")
    case = session.scalar(select(VerificationCase).where(VerificationCase.id == case_id).with_for_update())
    if case is None:
        raise ApiError("NOT_FOUND")
    if case.state != "rejected" or case.decided_at is None:
        raise ApiError("TRANSITION_NOT_ALLOWED")
    if _now() - case.decided_at > timedelta(days=REJECTED_CASE_DAYS):
        raise ApiError("REOPEN_WINDOW_CLOSED")
    if case.legal_name_enc is None and case.doc_type is not None:
        raise ApiError("REOPEN_WINDOW_CLOSED")  # its evidence is already gone
    case.state, case.version, case.updated_at, case.purge_after = "submitted", case.version + 1, _now(), None
    case.decided_by = case.decided_at = None
    tasks.ensure_task(session, "verification", case.id, required_role="superadmin" if case.risk_flags else "moderator")
    audit.record(session, actor=principal, action="verification.reopened", target_type="verification_case", target_id=case.id, reason=reason_code, metadata={"note": note or ""}, request_id=request_id)
    emit(session, "verification.state_changed", case.id, {"case_id": str(case.id), "state": "submitted", "applicant_id": str(case.applicant_user_id)})
    return {"case_id": str(case.id), "state": case.state, "version": case.version}


def _may_view_case(session: Session, principal: Principal, case: VerificationCase) -> None:
    """The lease holder, or a superadmin; never the applicant. Evidence only while the case is being decided."""
    if case.applicant_user_id == principal.user.id:
        raise ApiError("FORBIDDEN")
    if principal.role == "superadmin":
        return
    holder = session.scalar(
        select(ModerationTask.id).where(
            ModerationTask.subject_id == case.id,
            ModerationTask.status == "open",
            ModerationTask.claimed_by == principal.user.id,
            ModerationTask.lease_expires_at > _now(),
        )
    )
    if holder is None:
        raise ApiError("FORBIDDEN")


def verification_details(session: Session, principal: Principal, case_id: uuid.UUID, *, request_id: str | None) -> dict[str, Any]:
    """The review screen's right side (6.1). The full document number only while the case is being decided."""
    from app import fieldcrypt
    from app.verification import geo, service

    case = session.get(VerificationCase, case_id)
    if case is None:
        raise ApiError("NOT_FOUND")
    _may_view_case(session, principal, case)
    applicant = session.get(User, case.applicant_user_id)
    phone = session.get(PhoneNumber, case.phone_id) if case.phone_id else None
    institution = session.get(Institution, case.institution_id) if case.institution_id else None
    deciding = case.state in ("submitted", "in_review", "escalated")
    doc_number = None
    if deciding and case.doc_number_enc is not None:
        try:
            doc_number = fieldcrypt.open_text(case.doc_number_enc, aad=f"verification_case:{case.id}:doc_number_enc")
        except fieldcrypt.SealError:
            doc_number = None
    evidence = session.scalars(
        select(VerificationEvidence).where(VerificationEvidence.case_id == case.id, VerificationEvidence.status == "uploaded").order_by(VerificationEvidence.created_at)
    )
    other_rejections = len(service.counted_rejections(session, case.applicant_user_id))
    audit.record(session, actor=principal, action="verification.details_viewed", target_type="verification_case", target_id=case.id, request_id=request_id)
    view = service.own_view(session, case)
    return {
        "case_id": str(case.id),
        "state": case.state,
        "purpose": case.purpose,
        "version": case.version,
        "applicant": {"user_id": str(applicant.id), "display_name": applicant.display_name, "email": applicant.email, "joined_at": applicant.created_at.isoformat()} if applicant else None,
        "personal": view["personal"] | {"home_division": geo.division_of(case.home_district)},
        "phone": {"last4": phone.last4, "verified": phone.verified_at is not None} if phone else None,
        "document": {
            "doc_type": case.doc_type,
            "number": doc_number,  # full number only while the case is being decided (7)
            "last4": case.doc_last4,
            "expiry": case.doc_expiry.isoformat() if case.doc_expiry else None,
        } if case.doc_type else None,
        "student": {
            "institution": institution.name_en if institution else case.institution_other,
            "study_end": case.study_end_month.strftime("%Y-%m") if case.study_end_month else None,
            "email_verified": case.institution_email_verified,
            "max_student_until": _student_limit(case, _now()).isoformat(),
        } if case.is_student_claim else None,
        "liveness": {"code": case.liveness_code, "gesture": case.liveness_gesture, "gesture_en": (view.get("liveness") or {}).get("gesture_en")} if case.liveness_code else None,
        "evidence": [
            {"id": str(e.id), "kind": e.kind, "flags": e.flags or [], "challenge": e.challenge, "created_at": e.created_at.isoformat(), "sealed": e.sealed_key is not None}
            for e in evidence
        ],
        "risk_flags": case.risk_flags or [],
        "required_checks": sorted(required_checks(case)),
        "previous_rejections": other_rejections,
        "statement": case.statement,
        "submitted_at": case.submitted_at.isoformat() if case.submitted_at else None,
        "clarification_steps": case.clarification_steps or [],
    }


EVIDENCE_TOKEN_LABEL = "abhijatri:evidence-view:v1"  # noqa: S105 - an HMAC context label, not a secret


def _evidence_token(staff_id: uuid.UUID, evidence_id: uuid.UUID, expires: int) -> str:
    from app import crypto

    return crypto.digest(EVIDENCE_TOKEN_LABEL, crypto.current_key_id(), f"{staff_id}:{evidence_id}:{expires}").hex()


def evidence_download(
    session: Session, storage: StorageClient, principal: Principal, case_id: uuid.UUID, evidence_id: uuid.UUID, *, request_id: str | None
) -> dict[str, Any]:
    """A 60-second link, only for the staff member holding this case (or a superadmin). Every view is audited.

    A sealed image is served by this API (decrypted and watermarked on the fly, never cached); an old
    unsealed file keeps the Storage signed link.
    """
    from app.config import get_settings

    evidence = session.get(VerificationEvidence, evidence_id)
    if evidence is None or evidence.case_id != case_id or evidence.status != "uploaded":
        raise ApiError("NOT_FOUND")
    case = session.get(VerificationCase, case_id)
    if case is None:
        raise ApiError("NOT_FOUND")
    _may_view_case(session, principal, case)
    if evidence.sealed_key:
        expires = int(_now().timestamp()) + 60
        token = _evidence_token(principal.user.id, evidence.id, expires)
        base = get_settings().backend_public_url.rstrip("/")
        url = f"{base}/api/v1/admin/verification-cases/{case_id}/evidence/{evidence_id}/content?expires={expires}&token={token}"
    else:
        url = storage.signed_download_url(evidence.object_key)
    audit.record(session, actor=principal, action="evidence.viewed", target_type="verification_case", target_id=case_id, metadata={"evidence_id": str(evidence.id), "kind": evidence.kind}, request_id=request_id)
    return {"url": url, "expires_in": 60, "content_type": "image/jpeg" if evidence.sealed_key else evidence.content_type}


def evidence_content(
    session: Session, storage: StorageClient, principal: Principal, case_id: uuid.UUID, evidence_id: uuid.UUID, *, expires: int, token: str
) -> bytes:
    """The decrypted, watermarked image behind a link from ``evidence_download`` (same staff member, 60 s)."""
    import hmac as _hmac
    import io

    from app import fieldcrypt
    from app.storage import SEALED_BUCKET, SEALED_MAX_BYTES
    from app.verification import images

    if expires < int(_now().timestamp()) or not _hmac.compare_digest(_evidence_token(principal.user.id, evidence_id, expires), token or ""):
        raise ApiError("NOT_FOUND")
    evidence = session.get(VerificationEvidence, evidence_id)
    if evidence is None or evidence.case_id != case_id or evidence.status != "uploaded" or not evidence.sealed_key:
        raise ApiError("NOT_FOUND")
    case = session.get(VerificationCase, case_id)
    if case is None:
        raise ApiError("NOT_FOUND")
    _may_view_case(session, principal, case)
    buffer = io.BytesIO()
    storage.download(evidence.sealed_key, buffer, SEALED_BUCKET, SEALED_MAX_BYTES)
    try:
        jpeg = fieldcrypt.open_bytes(buffer.getvalue(), aad=f"evidence:{evidence.id}")
    except fieldcrypt.SealError as error:
        raise ApiError("NOT_FOUND") from error
    stamp = f"{principal.user.id.hex[:8]} {_now():%Y-%m-%d %H:%M}"
    return images.watermark(jpeg, stamp)


def list_bans(session: Session) -> list[dict[str, Any]]:
    now = _now()
    rows = session.scalars(
        select(VerificationBan).where(VerificationBan.lifted_at.is_(None), or_(VerificationBan.until.is_(None), VerificationBan.until > now)).order_by(VerificationBan.created_at.desc()).limit(200)
    )
    out = []
    for ban in rows:
        user = session.get(User, ban.user_id) if ban.user_id else None
        out.append({
            "id": str(ban.id), "user_id": str(ban.user_id) if ban.user_id else None, "display_name": user.display_name if user else None,
            "email": user.email if user else None, "reason": ban.reason, "until": ban.until.isoformat() if ban.until else None, "created_at": ban.created_at.isoformat(),
        })
    return out


def lift_ban(session: Session, principal: Principal, ban_id: uuid.UUID, reason: str, request_id: str | None) -> dict[str, Any]:
    if principal.role != "superadmin":
        raise ApiError("FORBIDDEN")
    ban = session.scalar(select(VerificationBan).where(VerificationBan.id == ban_id).with_for_update())
    if ban is None or ban.lifted_at is not None:
        raise ApiError("NOT_FOUND")
    ban.lifted_at, ban.lifted_by = _now(), principal.user.id
    audit.record(session, actor=principal, action="verification.ban_lifted", target_type="user", target_id=ban.user_id or ban.id, reason=reason, request_id=request_id)
    return {"id": str(ban.id), "lifted_at": ban.lifted_at.isoformat()}


# =========================================================================================
# Enforcement and sanctions (spec 6.4, 7.3)
# =========================================================================================


def _hide_review(
    session: Session, principal: Principal, review: Review, reason_code: str, request_id: str | None, *, keep_rating: bool = False
) -> None:
    try:
        moderate_review(
            session, review_id=review.id, actor_user_id=principal.user.id, expected_version=review.version,
            decision=ModerationDecision.HIDE, reason_code=reason_code, note=None, request_id=request_id, keep_rating=keep_rating,
        )
    except ReviewError as error:
        raise ApiError("TRANSITION_NOT_ALLOWED" if error.code == "INVALID_TRANSITION" else error.code) from error


def close_takedowns_on_restore(session: Session, principal: Principal, review_id: uuid.UUID, reason_code: str, request_id: str | None) -> int:
    """A review restored from the queue or a report is no longer taken down: its open takedown cases end as
    ``restored`` (counted again, closed, audited), so the Enforcement screen never shows a stale takedown."""
    ended = 0
    for case in session.scalars(
        select(EnforcementCase)
        .where(EnforcementCase.review_id == review_id, EnforcementCase.kind == "takedown", EnforcementCase.state == "taken_down")
        .with_for_update()
    ):
        previous = case.state
        case.state, case.counts_toward_rating, case.closed_at = "restored", True, _now()
        case.version += 1
        case.updated_at = _now()
        for task in session.scalars(select(ModerationTask).where(ModerationTask.subject_id == case.id, ModerationTask.status == "open").with_for_update()):
            tasks.complete(task)
        audit.record(
            session, actor=principal, action="enforcement.restore", target_type="enforcement_case", target_id=case.id, reason=reason_code,
            metadata={"from": previous, "to": case.state, "via": "review.restore", "review_id": str(review_id)}, request_id=request_id,
        )
        ended += 1
    return ended


def _restore_review(session: Session, principal: Principal, review: Review, reason_code: str, request_id: str | None) -> None:
    if review.status != ReviewStatus.HIDDEN:
        return
    try:
        moderate_review(
            session, review_id=review.id, actor_user_id=principal.user.id, expected_version=review.version,
            decision=ModerationDecision.RESTORE, reason_code=reason_code, note=None, request_id=request_id,
        )
    except ReviewError as error:
        raise ApiError(error.code) from error


def _set_account_state(session: Session, user_id: uuid.UUID) -> None:
    """A user is disabled exactly while an active suspension exists."""
    user = session.get(User, user_id)
    if user is None:
        return
    suspended = session.scalar(select(Sanction.id).where(Sanction.user_id == user_id, _in_force(_now()), Sanction.kind == "suspension"))
    user.status = "disabled" if suspended is not None else "active"
    user.disabled_at = _now() if suspended is not None else None


def open_enforcement(
    session: Session,
    principal: Principal,
    *,
    review_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    reason_code: str,
    note: str | None,
    emergency: bool,
    counts_toward_rating: bool,
    sanction: dict[str, Any] | None,
    request_id: str | None,
) -> EnforcementCase:
    if (review_id is None) == (user_id is None):
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "target", "code": "INVALID_VALUE"}])
    now = _now()
    if review_id is not None:
        review = session.scalar(select(Review).where(Review.id == review_id).with_for_update())
        if review is None:
            raise ApiError("NOT_FOUND")
        if review.author_user_id == principal.user.id:
            raise ApiError("SELF_MODERATION_FORBIDDEN")
        if review.status != ReviewStatus.PUBLISHED:
            raise ApiError("TRANSITION_NOT_ALLOWED")
        _hide_review(session, principal, review, reason_code, request_id, keep_rating=counts_toward_rating)
        case = EnforcementCase(
            kind="takedown", review_id=review_id, state="taken_down", emergency=emergency, counts_toward_rating=counts_toward_rating,
            follow_up_due_at=now + timedelta(hours=EMERGENCY_FOLLOW_UP_HOURS) if emergency else None,
            opened_by=principal.user.id, reason_code=reason_code, note=note,
        )
        subject_id: uuid.UUID | None = review.author_user_id
    else:
        assert user_id is not None
        if user_id == principal.user.id:
            raise ApiError("FORBIDDEN")
        target = session.get(User, user_id)
        if target is None:
            raise ApiError("NOT_FOUND")
        if session.scalar(select(UserRole.id).where(UserRole.user_id == user_id, UserRole.revoked_at.is_(None))) is not None and principal.role != "superadmin":
            raise ApiError("FORBIDDEN")  # only a superadmin acts against staff accounts
        case = EnforcementCase(kind="account", subject_user_id=user_id, state="open", emergency=emergency, counts_toward_rating=True, opened_by=principal.user.id, reason_code=reason_code, note=note)
        subject_id = user_id
    session.add(case)
    session.flush()
    if emergency:  # an emergency takedown always gets a superadmin follow-up (spec 6.4)
        tasks.ensure_task(session, "enforcement", case.id, priority=2, required_role="superadmin")
    audit.record(session, actor=principal, action="enforcement.opened", target_type="enforcement_case", target_id=case.id, reason=reason_code, metadata={"kind": case.kind, "emergency": emergency, "review_id": str(review_id) if review_id else None, "user_id": str(user_id) if user_id else None}, request_id=request_id)
    emit(session, "enforcement.opened", case.id, {"case_id": str(case.id), "kind": case.kind, "subject_id": str(subject_id) if subject_id else None, "emergency": emergency, "staff_recipients": active_staff_ids(session, exclude=principal.user.id, roles=("superadmin",)) if emergency else []})
    if sanction is not None:
        if subject_id is None:
            raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "sanction", "code": "NO_ACCOUNT"}])  # a guest review has no account
        add_sanction(session, principal, case, subject_id, **sanction, request_id=request_id)
    return case


def add_sanction(
    session: Session,
    principal: Principal,
    case: EnforcementCase,
    user_id: uuid.UUID,
    *,
    kind: str,
    ends_at: datetime | None = None,
    review_on: Any = None,
    scope: str = "reviews",
    request_id: str | None = None,
) -> Sanction:
    if kind not in ("warning", "posting_restriction", "suspension"):
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "sanction.kind", "code": "INVALID_VALUE"}])
    if ends_at is None and review_on is None:
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "sanction.ends_at", "code": "REQUIRED"}])
    if ends_at is not None and ends_at <= _now():
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "sanction.ends_at", "code": "TOO_SMALL"}])
    if kind == "suspension" and principal.role != "superadmin":
        raise ApiError("FORBIDDEN")
    sanction = Sanction(user_id=user_id, enforcement_case_id=case.id, kind=kind, scope=scope, ends_at=ends_at, review_on=review_on, reason_code=case.reason_code, created_by=principal.user.id)
    session.add(sanction)
    session.flush()
    _set_account_state(session, user_id)
    audit.record(session, actor=principal, action="sanction.created", target_type="user", target_id=user_id, reason=case.reason_code, metadata={"sanction_id": str(sanction.id), "kind": kind, "ends_at": ends_at.isoformat() if ends_at else None}, request_id=request_id)
    emit(session, "sanction.created", sanction.id, {"sanction_id": str(sanction.id), "user_id": str(user_id), "kind": kind})
    return sanction


def reverse_sanction(session: Session, principal: Principal | None, sanction: Sanction, *, expired: bool = False, request_id: str | None = None) -> None:
    if sanction.state != "active":
        raise ApiError("TRANSITION_NOT_ALLOWED")
    sanction.state = "expired" if expired else "reversed"
    sanction.reversed_at = _now()
    sanction.reversed_by = principal.user.id if principal else None
    _set_account_state(session, sanction.user_id)
    audit.record(session, actor=principal, action="sanction.expired" if expired else "sanction.reversed", target_type="user", target_id=sanction.user_id, metadata={"sanction_id": str(sanction.id)}, request_id=request_id)
    emit(session, "sanction.ended", sanction.id, {"sanction_id": str(sanction.id), "user_id": str(sanction.user_id), "kind": sanction.kind, "how": sanction.state})


def enforcement_action(
    session: Session, principal: Principal, *, case_id: uuid.UUID, action: str, expected_version: int,
    reason_code: str, note: str | None, counts_toward_rating: bool | None, sanction_id: uuid.UUID | None, request_id: str | None,
) -> dict[str, Any]:
    case = session.scalar(select(EnforcementCase).where(EnforcementCase.id == case_id).with_for_update())
    if case is None:
        raise ApiError("NOT_FOUND")
    if case.version != expected_version:
        raise ApiError("REVIEW_VERSION_CONFLICT")
    if case.opened_by == principal.user.id and case.emergency and principal.role != "superadmin":
        raise ApiError("FORBIDDEN")  # an emergency takedown is followed up by someone else
    if action == "reverse_sanction":
        sanction = session.get(Sanction, sanction_id) if sanction_id else None
        if sanction is None or sanction.enforcement_case_id != case.id:
            raise ApiError("NOT_FOUND")
        reverse_sanction(session, principal, sanction, request_id=request_id)
    else:
        if case.state not in ENFORCEMENT_ACTIONS.get(action, frozenset()):
            raise ApiError("TRANSITION_NOT_ALLOWED")
        if case.emergency and principal.role != "superadmin":
            raise ApiError("FORBIDDEN")
        review = session.get(Review, case.review_id) if case.review_id else None
        previous = case.state
        if action == "remove":
            case.state = "removed"
            if counts_toward_rating is not None:
                case.counts_toward_rating = counts_toward_rating
                if review is not None:
                    set_hidden_rating_kept(session, review.id, counts_toward_rating)  # moves the totals under the usual locks
        elif action == "restore":
            assert review is not None
            _restore_review(session, principal, review, reason_code, request_id)
            case.state, case.counts_toward_rating = "restored", True
        elif action == "close":
            case.state = "closed"
        if case.state in ("removed", "restored", "closed"):
            case.closed_at = _now()
            for task in session.scalars(select(ModerationTask).where(ModerationTask.subject_id == case.id, ModerationTask.status == "open").with_for_update()):
                tasks.complete(task)
        audit.record(session, actor=principal, action=f"enforcement.{action}", target_type="enforcement_case", target_id=case.id, reason=reason_code, metadata={"from": previous, "to": case.state, "counts_toward_rating": case.counts_toward_rating}, request_id=request_id)
        emit(session, "enforcement.state_changed", case.id, {"case_id": str(case.id), "kind": case.kind, "state": case.state, "subject_id": str(case.subject_user_id or (review.author_user_id if review else None) or "")})
    case.version += 1
    case.updated_at = _now()
    if note:
        case.note = note
    return {"case_id": str(case.id), "state": case.state, "version": case.version, "counts_toward_rating": case.counts_toward_rating}


# =========================================================================================
# Appeals (spec 6.5, 7.4)
# =========================================================================================


def appealable_decisions(session: Session, user_id: uuid.UUID) -> list[dict[str, Any]]:
    """Decisions this member may appeal now, with their deadlines (the member's own content and cases)."""
    now = _now()
    items: list[dict[str, Any]] = []
    actions = session.execute(
        select(ModerationActionRecord, Review)
        .join(Review, Review.id == ModerationActionRecord.review_id)
        .where(Review.author_user_id == user_id, ModerationActionRecord.decision.in_(APPEALABLE_DECISIONS))
        .order_by(ModerationActionRecord.created_at.desc())
    ).all()
    for action, review in actions:
        if review.status.value != action.new_status.value:
            continue  # superseded by a later decision
        items.append({"target_type": "moderation_action", "target_id": str(action.id), "label": f"review {review.status.value.lower()}", "decided_at": action.created_at, "review_id": str(review.id)})
    for case in session.scalars(select(VerificationCase).where(VerificationCase.applicant_user_id == user_id, VerificationCase.state == "rejected")):
        items.append({"target_type": "verification_case", "target_id": str(case.id), "label": "verification rejected", "decided_at": case.decided_at or case.updated_at})
    enforcement = session.execute(
        select(EnforcementCase).outerjoin(Review, Review.id == EnforcementCase.review_id).where(
            (EnforcementCase.subject_user_id == user_id) | (Review.author_user_id == user_id),
            EnforcementCase.state.in_(("taken_down", "removed", "open")),
        )
    ).scalars()
    for ecase in enforcement:
        items.append({"target_type": "enforcement_case", "target_id": str(ecase.id), "label": f"enforcement {ecase.state}", "decided_at": ecase.created_at})
    result = []
    for item in items:
        deadline = appeal_deadline(item["decided_at"])
        existing = session.scalar(select(Appeal.state).where(getattr(Appeal, f"{item['target_type']}_id") == uuid.UUID(item["target_id"]), Appeal.state != "withdrawn"))
        result.append({**item, "decided_at": item["decided_at"].isoformat(), "deadline_at": deadline.isoformat(), "open": deadline > now and existing is None, "appeal_state": existing})
    return result


def _appeal_target(session: Session, user_id: uuid.UUID, target_type: str, target_id: uuid.UUID) -> tuple[datetime, uuid.UUID | None]:
    """Validate standing and appealability; return (decision time, original decider)."""
    if target_type == "moderation_action":
        action = session.get(ModerationActionRecord, target_id)
        review = session.get(Review, action.review_id) if action else None
        if action is None or review is None or review.author_user_id != user_id or action.decision not in APPEALABLE_DECISIONS:
            raise ApiError("NOT_FOUND")
        if review.status.value != action.new_status.value:
            raise ApiError("TRANSITION_NOT_ALLOWED")  # a later decision already replaced it
        return action.created_at, action.actor_user_id
    if target_type == "verification_case":  # locked: the retention job deletes this row under the same lock
        case = session.scalar(select(VerificationCase).where(VerificationCase.id == target_id).with_for_update())
        if case is None or case.applicant_user_id != user_id or case.state != "rejected":
            raise ApiError("NOT_FOUND")
        return case.decided_at or case.updated_at, case.decided_by
    if target_type == "enforcement_case":
        enforcement = session.get(EnforcementCase, target_id)
        review = session.get(Review, enforcement.review_id) if enforcement and enforcement.review_id else None
        owner = enforcement.subject_user_id if enforcement else None
        if enforcement is None or (owner != user_id and (review is None or review.author_user_id != user_id)):
            raise ApiError("NOT_FOUND")
        if enforcement.state not in ("taken_down", "removed", "open"):
            raise ApiError("TRANSITION_NOT_ALLOWED")
        return enforcement.created_at, enforcement.opened_by
    raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "target_type", "code": "INVALID_VALUE"}])


def create_appeal(session: Session, appellant: Principal, *, target_type: str, target_id: uuid.UUID, reason: str) -> Appeal:
    if target_type in ("moderation_action", "enforcement_case", "verification_case"):
        earlier = session.scalar(
            select(Appeal.id).where(getattr(Appeal, f"{target_type}_id") == target_id, Appeal.appellant_user_id == appellant.user.id, Appeal.state != "withdrawn")
        )
        if earlier is not None:  # one appeal per decision, decided or not (spec 6.5)
            raise ApiError("DUPLICATE_APPEAL")
    decided_at, decider = _appeal_target(session, appellant.user.id, target_type, target_id)
    deadline = appeal_deadline(decided_at)
    if _now() > deadline:
        raise ApiError("APPEAL_WINDOW_CLOSED")
    appeal = Appeal(appellant_user_id=appellant.user.id, reason=reason, original_decider_id=decider, deadline_at=deadline, **{f"{target_type}_id": target_id})
    try:
        with session.begin_nested():
            session.add(appeal)
            session.flush()
    except IntegrityError as error:
        raise ApiError("DUPLICATE_APPEAL") from error
    tasks.ensure_task(session, "appeal", appeal.id, priority=1)
    audit.record(session, actor=appellant, action="appeal.received", target_type="appeal", target_id=appeal.id, metadata={"target_type": target_type, "target_id": str(target_id), "deadline_at": deadline.isoformat()})
    emit(session, "appeal.received", appeal.id, {"appeal_id": str(appeal.id), "appellant_id": str(appellant.user.id), "deadline_at": deadline.isoformat(), "staff_recipients": active_staff_ids(session, exclude=decider)})
    return appeal


def create_guest_appeal(session: Session, review_id: uuid.UUID, *, statement: str) -> Appeal:
    """A Guest's appeal against the rejection of their review (Review.md 4.2, API.md 5.6).

    The caller has already proved ownership with the receipt. The appeal targets the rejection
    decision itself, so it follows the same rules as a member's: one per decision, 30-day window,
    independent reviewer. ``appellant_user_id`` stays empty because a Guest has no account.
    """
    review = session.scalar(select(Review).where(Review.id == review_id).with_for_update())
    if review is None:
        raise ApiError("NOT_FOUND")
    action = session.scalar(
        select(ModerationActionRecord)
        .where(ModerationActionRecord.review_id == review.id, ModerationActionRecord.decision == ModerationDecision.REJECT)
        .order_by(ModerationActionRecord.created_at.desc())
        .limit(1)
    )
    if review.status != ReviewStatus.REJECTED or action is None:
        raise ApiError("APPEAL_WINDOW_CLOSED")  # nothing to appeal (API.md 5.6)
    if session.scalar(select(Appeal.id).where(Appeal.moderation_action_id == action.id, Appeal.state != "withdrawn")) is not None:
        raise ApiError("DUPLICATE_APPEAL")
    deadline = appeal_deadline(action.created_at)
    if _now() > deadline:
        raise ApiError("APPEAL_WINDOW_CLOSED")
    appeal = Appeal(
        appellant_user_id=None,
        moderation_action_id=action.id,
        reason=statement,
        original_decider_id=action.actor_user_id,
        deadline_at=deadline,
    )
    try:
        with session.begin_nested():
            session.add(appeal)
            session.flush()
    except IntegrityError as error:
        raise ApiError("DUPLICATE_APPEAL") from error
    tasks.ensure_task(session, "appeal", appeal.id, priority=1)
    audit.record(
        session,
        actor=None,
        action="appeal.received",
        target_type="appeal",
        target_id=appeal.id,
        metadata={"target_type": "moderation_action", "target_id": str(action.id), "deadline_at": deadline.isoformat(), "by": "guest_receipt"},
    )
    emit(
        session,
        "appeal.received",
        appeal.id,
        {
            "appeal_id": str(appeal.id),
            "appellant_id": None,  # a Guest has no inbox; the receipt status shows the outcome
            "deadline_at": deadline.isoformat(),
            "staff_recipients": active_staff_ids(session, exclude=action.actor_user_id),
        },
    )
    return appeal


def withdraw_appeal(session: Session, appellant: Principal, appeal_id: uuid.UUID) -> Appeal:
    appeal = session.scalar(select(Appeal).where(Appeal.id == appeal_id).with_for_update())
    if appeal is None or appeal.appellant_user_id != appellant.user.id:
        raise ApiError("NOT_FOUND")
    if appeal.state not in ("received", "in_review"):
        raise ApiError("TRANSITION_NOT_ALLOWED")
    appeal.state, appeal.version = "withdrawn", appeal.version + 1
    tasks.cancel_open_tasks(session, appeal.id)
    audit.record(session, actor=appellant, action="appeal.withdrawn", target_type="appeal", target_id=appeal.id)
    return appeal


def _overturn(session: Session, principal: Principal, appeal: Appeal, request_id: str | None) -> None:
    """Undo the appealed decision. The original action and its audit history stay untouched."""
    if appeal.moderation_action_id:
        action = session.get(ModerationActionRecord, appeal.moderation_action_id)
        review = session.scalar(select(Review).where(Review.id == action.review_id).with_for_update()) if action else None
        if review is None:
            return
        if review.status == ReviewStatus.HIDDEN:
            _restore_review(session, principal, review, "appeal-overturned", request_id)
        elif review.status == ReviewStatus.REJECTED:  # back to the queue for a fresh, independent review
            review.status, review.version, review.updated_at = ReviewStatus.PENDING, review.version + 1, _now()
            tasks.ensure_task(session, "review_moderation", review.id)
    elif appeal.verification_case_id:
        vcase = session.get(VerificationCase, appeal.verification_case_id)
        if vcase is not None and not is_verified_member(session, vcase.applicant_user_id):
            now = _now()
            session.add(
                Verification(
                    user_id=vcase.applicant_user_id, verification_type="VERIFIED_MEMBER", status="APPROVED", method="APPEAL",
                    approved_by=principal.user.id, decided_at=now, expires_at=renewal_due(now, vcase.doc_expiry),
                )
            )
            # The independent reviewer upheld the applicant: the claims checked in review become the verified
            # attributes, so tours eligibility works after an appeal too (loophole L11).
            if vcase.gender_claimed and vcase.birth_year:
                student = vcase.is_student_claim and vcase.study_end_month is not None
                _write_attributes(
                    session, vcase.applicant_user_id,
                    {"gender": vcase.gender_claimed, "birth_year": vcase.birth_year, "is_student": student,
                     "student_until": _student_limit(vcase, now) if student else None},
                    district=vcase.home_district, actor_id=principal.user.id, now=now,
                )
            vcase.state, vcase.version, vcase.doc_number_enc = "approved", vcase.version + 1, None
            vcase.purge_after = now + timedelta(hours=APPROVED_EVIDENCE_HOURS)
    elif appeal.enforcement_case_id:
        ecase = session.scalar(select(EnforcementCase).where(EnforcementCase.id == appeal.enforcement_case_id).with_for_update())
        if ecase is None:
            return
        if ecase.review_id:
            target = session.get(Review, ecase.review_id)
            if target is not None:
                _restore_review(session, principal, target, "appeal-overturned", request_id)
            ecase.state = "restored"
        else:
            ecase.state = "closed"
        ecase.counts_toward_rating, ecase.closed_at, ecase.version = True, _now(), ecase.version + 1
        for sanction in session.scalars(select(Sanction).where(Sanction.enforcement_case_id == ecase.id, Sanction.state == "active")):
            reverse_sanction(session, principal, sanction, request_id=request_id)


def decide_appeal(
    session: Session, principal: Principal, *, appeal_id: uuid.UUID, outcome: str, expected_version: int,
    note: str | None, task_id: uuid.UUID, lease_token: uuid.UUID, request_id: str | None,
) -> dict[str, Any]:
    appeal = session.scalar(select(Appeal).where(Appeal.id == appeal_id).with_for_update())
    if appeal is None:
        raise ApiError("NOT_FOUND")
    task = tasks.require_lease(session, principal, task_id, lease_token, appeal_id)
    if appeal.original_decider_id == principal.user.id:
        raise ApiError("APPEAL_REVIEWER_NOT_INDEPENDENT")
    if appeal.appellant_user_id is not None and appeal.appellant_user_id == principal.user.id:
        raise ApiError("FORBIDDEN")
    if appeal.version != expected_version:
        raise ApiError("REVIEW_VERSION_CONFLICT")
    if outcome not in APPEAL_OUTCOMES or appeal.state not in ("received", "in_review"):
        raise ApiError("TRANSITION_NOT_ALLOWED")
    if outcome == "overturned":
        _overturn(session, principal, appeal, request_id)
    appeal.state, appeal.version = outcome, appeal.version + 1
    appeal.decided_by, appeal.decided_at, appeal.decision_note = principal.user.id, _now(), note
    tasks.complete(task)
    audit.record(session, actor=principal, action=f"appeal.{outcome}", target_type="appeal", target_id=appeal.id, reason=note, metadata={"version": appeal.version}, request_id=request_id)
    emit(
        session,
        "appeal.decided",
        appeal.id,
        {"appeal_id": str(appeal.id), "appellant_id": str(appeal.appellant_user_id) if appeal.appellant_user_id else None, "outcome": outcome},
    )
    return {"appeal_id": str(appeal.id), "state": appeal.state, "version": appeal.version}
