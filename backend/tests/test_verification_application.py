"""The Verified Member application (Features/Verified user sign-up form.md): acceptance criteria VF-01 to VF-11
and the loopholes closed in the old single-form flow (Backend-Implemented 8)."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import test_admin as admin
import test_auth as support
import verification_support as vs
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app import scheduler, sms
from app.models import (
    Appeal,
    OutboxEvent,
    PhoneNumber,
    User,
    Verification,
    VerificationAttributes,
    VerificationBan,
    VerificationCase,
    VerificationEvidence,
)
from app.storage import get_storage

auth_env = support.auth_env
fake = support.fake
redis_fake = support.redis_fake
_reset_limiter = support._reset_limiter  # noqa: SLF001
pytestmark = pytest.mark.integration
BASE = "/api/v1/admin"


@pytest.fixture()
def storage() -> vs.FakeStorage:
    return vs.FakeStorage()


@pytest.fixture()
def sms_box() -> Iterator[vs.RecordingSms]:
    recorder = vs.RecordingSms()
    sms.use_for_tests(recorder)
    yield recorder
    sms.use_for_tests(None)


@pytest.fixture()
def client(auth_env: None, postgres_session: Session, fake: support.FakeGoTrue, redis_fake: Any, storage: vs.FakeStorage, sms_box: vs.RecordingSms) -> TestClient:
    base = support.make_client(postgres_session, fake, redis_fake)
    base.app.dependency_overrides[get_storage] = lambda: storage  # type: ignore[attr-defined]
    return base


def member(client: TestClient, session: Session, fake: support.FakeGoTrue, email: str, ip: str) -> TestClient:
    return admin.staff_client(client, session, fake, email, None, ip, aal="aal1")


def sessions(session: Session) -> sessionmaker[Session]:
    return sessionmaker(bind=session.get_bind(), expire_on_commit=False)


def _user_id(fake: support.FakeGoTrue, email: str) -> uuid.UUID:
    return uuid.UUID(str(fake.users[email]["id"]))


# ---------------------------------------------------------------- VF-01, VF-02


def test_vf01_an_unverified_email_cannot_start(client: TestClient, postgres_session: Session, fake: support.FakeGoTrue) -> None:
    browser = member(client, postgres_session, fake, "new@example.com", "203.0.113.150")
    postgres_session.execute(update(User).where(User.email == "new@example.com").values(email_verified_at=None))
    postgres_session.commit()
    refused = browser.post("/api/v1/verifications", json={})
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


def test_vf02_under_18_is_refused_at_step_2_and_nothing_is_uploaded(client: TestClient, postgres_session: Session, fake: support.FakeGoTrue) -> None:
    browser = member(client, postgres_session, fake, "teen@example.com", "203.0.113.151")
    case = browser.post("/api/v1/verifications", json={}).json()
    early = browser.post(f"/api/v1/verifications/{case['id']}/evidence", json={"kind": "SELFIE", "content_type": "image/jpeg", "size_bytes": 100})
    assert early.status_code == 422, "no image before the age check passed"
    young = (datetime.now(UTC) - timedelta(days=365 * 17)).date().isoformat()
    refused = browser.patch(f"/api/v1/verifications/{case['id']}/steps/personal", json={**vs.PERSONAL, "date_of_birth": young})
    assert refused.status_code == 422 and refused.json()["error"]["field_errors"] == [{"field": "date_of_birth", "code": "UNDER_18"}]
    assert postgres_session.scalar(select(func.count()).select_from(VerificationEvidence)) == 0


# ---------------------------------------------------------------- VF-03 one person, one account


def test_vf03_a_linked_phone_or_document_is_refused_without_naming_the_account(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue, storage: vs.FakeStorage, sms_box: vs.RecordingSms
) -> None:
    first = member(client, postgres_session, fake, "first@example.com", "203.0.113.152")
    mod = admin.staff_client(client, postgres_session, fake, "mod@example.com", "moderator", "203.0.113.153")
    case = vs.apply(first, postgres_session, storage, sms_box, "first@example.com", phone="01711222333", doc_number="9988776655")
    assert vs.approve(mod, postgres_session, case["id"]).status_code == 200

    second = member(client, postgres_session, fake, "second@example.com", "203.0.113.154")
    draft = second.post("/api/v1/verifications", json={}).json()
    second.patch(f"/api/v1/verifications/{draft['id']}/steps/eligibility", json={"age_confirmed": True, "consent": True})
    second.patch(f"/api/v1/verifications/{draft['id']}/steps/personal", json=vs.PERSONAL)
    taken = second.post(f"/api/v1/verifications/{draft['id']}/phone/send-code", json={"phone": "+8801711222333"})
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "PHONE_ALREADY_LINKED"
    assert "first@example.com" not in taken.text and "First" not in taken.text
    doc = second.patch(f"/api/v1/verifications/{draft['id']}/steps/document", json={"doc_type": "NID", "doc_number": "99-8877-6655"})
    assert doc.status_code == 409 and doc.json()["error"]["code"] == "DOCUMENT_ALREADY_LINKED", "normalised before hashing"


def test_the_same_image_on_another_account_is_a_risk_flag_and_escalates(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue, storage: vs.FakeStorage, sms_box: vs.RecordingSms
) -> None:
    image = vs.jpeg(seed=42)
    one = member(client, postgres_session, fake, "one@example.com", "203.0.113.155")
    vs.age_account(postgres_session, "one@example.com")
    case_one = vs.fill(one, storage, sms_box, phone="01711000011", doc_number="1111111111")
    vs.upload(one, storage, case_one["id"], "DOC_FRONT", image)
    vs.submit(one, case_one["id"])
    two = member(client, postgres_session, fake, "two@example.com", "203.0.113.156")
    vs.age_account(postgres_session, "two@example.com")
    case_two = vs.fill(two, storage, sms_box, phone="01711000012", doc_number="2222222222")
    vs.upload(two, storage, case_two["id"], "DOC_FRONT", image)
    submitted = vs.submit(two, case_two["id"])
    assert submitted["state"] == "escalated", "a flagged application goes to a superadmin (10.2)"
    postgres_session.expire_all()
    stored = postgres_session.get(VerificationCase, uuid.UUID(case_two["id"]))
    assert stored is not None and "image_reused" in stored.risk_flags


def test_a_new_account_is_flagged_and_a_moderator_cannot_approve_it(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue, storage: vs.FakeStorage, sms_box: vs.RecordingSms
) -> None:
    fresh = member(client, postgres_session, fake, "fresh@example.com", "203.0.113.157")
    case = vs.fill(fresh, storage, sms_box)  # account created just now
    submitted = vs.submit(fresh, case["id"])
    assert submitted["state"] == "escalated"
    mod = admin.staff_client(client, postgres_session, fake, "mod@example.com", "moderator", "203.0.113.158")
    assert not next(i for i in mod.get(f"{BASE}/queue").json()["items"] if i["subject_id"] == case["id"])["claimable"]
    boss = admin.staff_client(client, postgres_session, fake, "boss@example.com", "superadmin", "203.0.113.159")
    assert vs.approve(boss, postgres_session, case["id"]).status_code == 200


# ---------------------------------------------------------------- VF-04 liveness


def test_vf04_a_selfie_needs_a_server_issued_challenge(client: TestClient, postgres_session: Session, fake: support.FakeGoTrue, storage: vs.FakeStorage) -> None:
    browser = member(client, postgres_session, fake, "selfie@example.com", "203.0.113.160")
    case = browser.post("/api/v1/verifications", json={}).json()
    browser.patch(f"/api/v1/verifications/{case['id']}/steps/eligibility", json={"age_confirmed": True, "consent": True})
    browser.patch(f"/api/v1/verifications/{case['id']}/steps/personal", json=vs.PERSONAL)
    refused = browser.post(f"/api/v1/verifications/{case['id']}/evidence", json={"kind": "SELFIE", "content_type": "image/jpeg", "size_bytes": 1000})
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "LIVENESS_REQUIRED"
    challenge = browser.post(f"/api/v1/verifications/{case['id']}/liveness-challenge").json()
    assert len(challenge["code"]) == 4 and challenge["gesture_en"]
    vs.upload(browser, storage, case["id"], "SELFIE")
    evidence = postgres_session.scalar(select(VerificationEvidence).where(VerificationEvidence.kind == "SELFIE"))
    assert evidence is not None and evidence.challenge == f"{challenge['code']}|{challenge['gesture']}"


def test_evidence_is_cleaned_sealed_and_the_original_deleted(client: TestClient, postgres_session: Session, fake: support.FakeGoTrue, storage: vs.FakeStorage) -> None:
    browser = member(client, postgres_session, fake, "img@example.com", "203.0.113.161")
    case = browser.post("/api/v1/verifications", json={}).json()
    browser.patch(f"/api/v1/verifications/{case['id']}/steps/eligibility", json={"age_confirmed": True, "consent": True})
    browser.patch(f"/api/v1/verifications/{case['id']}/steps/personal", json=vs.PERSONAL)
    browser.patch(f"/api/v1/verifications/{case['id']}/steps/document", json={"doc_type": "PASSPORT", "doc_number": "A01234567", "doc_expiry": "2031-01-01"})
    png = vs.jpeg(fmt="PNG")
    done = vs.upload(browser, storage, case["id"], "DOC_FRONT", png, content_type="image/png")
    assert done["status"] == "uploaded"
    assert not [k for (b, k) in storage.blobs if b == "verification-quarantine"], "the original never stays (9.2)"
    sealed = [v for (b, _), v in storage.blobs.items() if b == "verification-sealed"]
    assert len(sealed) == 1 and sealed[0].startswith(b"F1") and b"JFIF" not in sealed[0], "sealed, not a readable image"
    evidence = postgres_session.scalar(select(VerificationEvidence).where(VerificationEvidence.kind == "DOC_FRONT"))
    assert evidence is not None and "screenshot_suspected" in evidence.flags
    broken = browser.post(f"/api/v1/verifications/{case['id']}/evidence", json={"kind": "DOC_BACK", "content_type": "image/jpeg", "size_bytes": 10})
    assert broken.status_code == 422, "a passport has no back side to upload"


# ---------------------------------------------------------------- VF-05 the approval transaction


def test_vf05_approval_writes_one_verification_and_one_attribute_row_and_destroys_the_number(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue, storage: vs.FakeStorage, sms_box: vs.RecordingSms
) -> None:
    browser = member(client, postgres_session, fake, "stu@example.com", "203.0.113.162")
    mod = admin.staff_client(client, postgres_session, fake, "mod@example.com", "moderator", "203.0.113.163")
    case = vs.apply(browser, postgres_session, storage, sms_box, "stu@example.com", student=True)
    no_student_check = vs.approve(mod, postgres_session, case["id"], attributes={"gender": "FEMALE", "birth_year": 1998, "is_student": True, "student_until": (datetime.now(UTC) + timedelta(days=200)).date().isoformat()})
    assert no_student_check.status_code == 422, "a student claim adds the student check"
    postgres_session.expire_all()
    stored = postgres_session.get(VerificationCase, uuid.UUID(case["id"]))
    assert stored is not None
    task = postgres_session.scalar(select(admin.ModerationTask).where(admin.ModerationTask.subject_id == stored.id, admin.ModerationTask.status == "open"))
    assert task is not None
    too_long = vs.decide(
        mod, case["id"], str(task.id), str(task.lease_token), stored.version, "approved", reason_code="ok", checklist=[*vs.CHECKLIST, "student"],
        attributes={"gender": "FEMALE", "birth_year": 1998, "is_student": True, "student_until": (datetime.now(UTC) + timedelta(days=500)).date().isoformat()},
    )
    assert too_long.status_code == 422, "student status lasts at most a year"
    ok = vs.decide(
        mod, case["id"], str(task.id), str(task.lease_token), stored.version, "approved", reason_code="ok", checklist=[*vs.CHECKLIST, "student"],
        attributes={"gender": "FEMALE", "birth_year": 1998, "is_student": True, "student_until": (datetime.now(UTC) + timedelta(days=300)).date().isoformat()},
    )
    assert ok.status_code == 200, ok.text
    user_id = _user_id(fake, "stu@example.com")
    assert postgres_session.scalar(select(func.count()).select_from(Verification).where(Verification.user_id == user_id)) == 1
    attributes = postgres_session.get(VerificationAttributes, user_id)
    assert attributes is not None and attributes.gender == "FEMALE" and attributes.is_student and attributes.home_district == "Sylhet"
    postgres_session.expire_all()
    approved = postgres_session.get(VerificationCase, uuid.UUID(case["id"]))
    assert approved is not None and approved.doc_number_enc is None and approved.doc_last4 == "7890"
    mine = browser.get("/api/v1/verifications/mine").json()
    assert mine["verified_member"] and mine["attributes"]["is_student"] and mine["emergency_contact"]["relationship"] == "Sister"


# ---------------------------------------------------------------- VF-06 leases


def test_vf06_two_moderators_cannot_decide_the_same_application(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue, storage: vs.FakeStorage, sms_box: vs.RecordingSms
) -> None:
    browser = member(client, postgres_session, fake, "lease@example.com", "203.0.113.164")
    one = admin.staff_client(client, postgres_session, fake, "one@example.com", "moderator", "203.0.113.165")
    two = admin.staff_client(client, postgres_session, fake, "two@example.com", "moderator", "203.0.113.166")
    case = vs.apply(browser, postgres_session, storage, sms_box, "lease@example.com")
    task_id, lease = vs.lease_for(one, postgres_session, case["id"])
    assert two.post(f"{BASE}/tasks/{task_id}/claim").status_code == 409, "already claimed"
    stolen = vs.decide(two, case["id"], task_id, lease, 2, "in_review")
    assert stolen.status_code in (403, 409)


# ---------------------------------------------------------------- VF-09 cooldowns and bans


def _reject(staff: TestClient, session: Session, case_id: str, reason: str = "details-mismatch") -> None:
    task_id, lease = vs.lease_for(staff, session, case_id)
    assert vs.decide(staff, case_id, task_id, lease, 2, "in_review").status_code == 200
    assert vs.decide(staff, case_id, task_id, lease, 3, "rejected", reason_code=reason).status_code == 200


def test_vf09_cooldowns_grow_and_a_fake_document_bans_the_person_and_the_document(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue, storage: vs.FakeStorage, sms_box: vs.RecordingSms
) -> None:
    browser = member(client, postgres_session, fake, "faker@example.com", "203.0.113.167")
    mod = admin.staff_client(client, postgres_session, fake, "mod@example.com", "moderator", "203.0.113.168")
    case = vs.apply(browser, postgres_session, storage, sms_box, "faker@example.com", phone="01911000077", doc_number="5555555555")
    _reject(mod, postgres_session, case["id"], "fake-document")
    banned = browser.post("/api/v1/verifications", json={})
    assert banned.status_code == 403 and banned.json()["error"]["code"] == "VERIFICATION_BANNED"
    ban = postgres_session.scalar(select(VerificationBan))
    assert ban is not None and ban.doc_hash is not None and ban.phone_hash is not None
    assert ban.until is not None and ban.until > datetime.now(UTC) + timedelta(days=89)

    # the banned document and phone are refused on another account too (10.3)
    other = member(client, postgres_session, fake, "alias@example.com", "203.0.113.169")
    draft = other.post("/api/v1/verifications", json={}).json()
    other.patch(f"/api/v1/verifications/{draft['id']}/steps/eligibility", json={"age_confirmed": True, "consent": True})
    other.patch(f"/api/v1/verifications/{draft['id']}/steps/personal", json=vs.PERSONAL)
    assert other.patch(f"/api/v1/verifications/{draft['id']}/steps/document", json={"doc_type": "NID", "doc_number": "5555555555"}).json()["error"]["code"] == "DOCUMENT_ALREADY_LINKED"
    assert other.post(f"/api/v1/verifications/{draft['id']}/phone/send-code", json={"phone": "01911000077"}).json()["error"]["code"] == "PHONE_ALREADY_LINKED"

    boss = admin.staff_client(client, postgres_session, fake, "boss@example.com", "superadmin", "203.0.113.170")
    listed = boss.get(f"{BASE}/verification-bans").json()["items"]
    assert [item["email"] for item in listed] == ["faker@example.com"]
    assert mod.get(f"{BASE}/verification-bans").status_code == 403
    lifted = boss.post(f"{BASE}/verification-bans/{ban.id}/lift", json={"reason": "checked with the person in the office"})
    assert lifted.status_code == 200
    again = browser.post("/api/v1/verifications", json={})
    assert again.status_code == 409 and again.json()["error"]["code"] == "VERIFICATION_COOLDOWN", "the first-rejection cooldown still applies"


def test_asking_to_reapply_on_the_new_form_is_no_strike(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue, storage: vs.FakeStorage, sms_box: vs.RecordingSms
) -> None:
    browser = member(client, postgres_session, fake, "old@example.com", "203.0.113.171")
    mod = admin.staff_client(client, postgres_session, fake, "mod@example.com", "moderator", "203.0.113.172")
    case = vs.apply(browser, postgres_session, storage, sms_box, "old@example.com")
    _reject(mod, postgres_session, case["id"], "use-new-form")
    assert browser.post("/api/v1/verifications", json={}).status_code == 201


# ---------------------------------------------------------------- one-time codes


def test_phone_codes_are_limited_and_expire_after_three_wrong_tries(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue, sms_box: vs.RecordingSms
) -> None:
    browser = member(client, postgres_session, fake, "otp@example.com", "203.0.113.173")
    case = browser.post("/api/v1/verifications", json={}).json()
    browser.patch(f"/api/v1/verifications/{case['id']}/steps/personal", json=vs.PERSONAL)
    bad_number = browser.post(f"/api/v1/verifications/{case['id']}/phone/send-code", json={"phone": "01211000000"})
    assert bad_number.status_code == 422, "012 is not a mobile prefix"
    sent = browser.post(f"/api/v1/verifications/{case['id']}/phone/send-code", json={"phone": "01711000099"})
    assert sent.status_code == 200 and sent.json()["sent_to"].endswith("0099") and sms_box.sent[-1][0] == "+8801711000099"
    resend = browser.post(f"/api/v1/verifications/{case['id']}/phone/send-code", json={"phone": "01711000099"})
    assert resend.status_code == 429 and "Retry-After" in resend.headers, "resend after 60 seconds"
    wrong = "000000" if sms_box.last_code() != "000000" else "111111"
    assert browser.post(f"/api/v1/verifications/{case['id']}/phone/verify", json={"code": wrong}).json()["error"]["code"] == "CODE_INVALID"
    browser.post(f"/api/v1/verifications/{case['id']}/phone/verify", json={"code": wrong})
    third = browser.post(f"/api/v1/verifications/{case['id']}/phone/verify", json={"code": wrong})
    assert third.json()["error"]["code"] == "CODE_ATTEMPTS_EXCEEDED"
    late = browser.post(f"/api/v1/verifications/{case['id']}/phone/verify", json={"code": sms_box.last_code()})
    assert late.json()["error"]["code"] == "CODE_ATTEMPTS_EXCEEDED", "the right code is too late"
    assert postgres_session.scalar(select(PhoneNumber)) is None


# ---------------------------------------------------------------- scheduler: drafts, renewal, lapse


def test_drafts_expire_and_renewal_reminders_go_out_once(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue, storage: vs.FakeStorage, sms_box: vs.RecordingSms
) -> None:
    browser = member(client, postgres_session, fake, "draft@example.com", "203.0.113.174")
    draft = browser.post("/api/v1/verifications", json={}).json()
    assert draft["draft_expires_at"] is not None
    postgres_session.execute(update(VerificationCase).values(draft_expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    postgres_session.commit()
    ran = scheduler.run_once(sessions(postgres_session))
    assert ran["verification.expire_drafts"] == 1
    postgres_session.expire_all()
    assert postgres_session.get(VerificationCase, uuid.UUID(draft["id"])).state == "expired"  # type: ignore[union-attr]

    holder = member(client, postgres_session, fake, "holder@example.com", "203.0.113.175")
    mod = admin.staff_client(client, postgres_session, fake, "mod@example.com", "moderator", "203.0.113.176")
    case = vs.apply(holder, postgres_session, storage, sms_box, "holder@example.com")
    assert vs.approve(mod, postgres_session, case["id"]).status_code == 200
    postgres_session.execute(update(Verification).values(expires_at=datetime.now(UTC) + timedelta(days=20)))
    postgres_session.commit()
    scheduler.run_once(sessions(postgres_session))
    scheduler.run_once(sessions(postgres_session))
    reminders = postgres_session.scalars(select(OutboxEvent).where(OutboxEvent.topic == "verification.renewal_due")).all()
    assert len(reminders) == 1, "VF-11: once per threshold"
    assert holder.get("/api/v1/verifications/mine").json()["verification"]["state"] == "renewal_due"
    renewal = holder.post("/api/v1/verifications", json={"purpose": "renewal"})
    assert renewal.status_code == 201 and renewal.json()["required_steps"] == ["eligibility", "document", "selfie"]
    holder.post(f"/api/v1/verifications/{renewal.json()['id']}/withdraw")

    postgres_session.execute(update(Verification).values(expires_at=datetime.now(UTC) - timedelta(hours=1)))
    postgres_session.commit()
    scheduler.run_once(sessions(postgres_session))
    assert postgres_session.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.topic == "verification.lapsed")) == 1
    mine = holder.get("/api/v1/verifications/mine").json()
    assert mine["verified_member"] is False and mine["verification"]["state"] == "lapsed", "badge hidden (VF-11)"


# ---------------------------------------------------------------- idempotency, appeals (L11)


def test_a_retried_submit_returns_the_first_answer(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue, storage: vs.FakeStorage, sms_box: vs.RecordingSms
) -> None:
    browser = member(client, postgres_session, fake, "retry@example.com", "203.0.113.177")
    vs.age_account(postgres_session, "retry@example.com")
    case = vs.fill(browser, storage, sms_box)
    key = str(uuid.uuid4())
    first = browser.post(f"/api/v1/verifications/{case['id']}/submit", json={"declaration": True}, headers={"Idempotency-Key": key})
    second = browser.post(f"/api/v1/verifications/{case['id']}/submit", json={"declaration": True}, headers={"Idempotency-Key": key})
    assert first.status_code == 200 and second.status_code == 200 and second.headers.get("Idempotent-Replayed") == "true"
    assert first.json()["state"] == second.json()["state"] == "submitted"


def test_an_overturned_appeal_writes_the_attributes(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue, storage: vs.FakeStorage, sms_box: vs.RecordingSms
) -> None:
    browser = member(client, postgres_session, fake, "appeal@example.com", "203.0.113.178")
    mod = admin.staff_client(client, postgres_session, fake, "mod@example.com", "moderator", "203.0.113.179")
    other = admin.staff_client(client, postgres_session, fake, "mod2@example.com", "moderator", "203.0.113.180")
    case = vs.apply(browser, postgres_session, storage, sms_box, "appeal@example.com")
    _reject(mod, postgres_session, case["id"], "face-mismatch")
    appeal = browser.post("/api/v1/appeals", json={"target_type": "verification_case", "target_id": case["id"], "reason": "That is my face, please look again."})
    assert appeal.status_code == 201
    stored = postgres_session.scalar(select(Appeal))
    assert stored is not None
    task_id, lease = vs.lease_for(other, postgres_session, str(stored.id))
    decided = other.post(f"{BASE}/appeals/{stored.id}/decision", json={"outcome": "overturned", "expected_version": stored.version, "task_id": task_id, "lease_token": lease, "note": "matches"})
    assert decided.status_code == 200, decided.text
    attributes = postgres_session.get(VerificationAttributes, _user_id(fake, "appeal@example.com"))
    assert attributes is not None and attributes.gender == "FEMALE" and attributes.birth_year == 1998, "L11"
    assert browser.get("/api/v1/verifications/mine").json()["verified_member"] is True
