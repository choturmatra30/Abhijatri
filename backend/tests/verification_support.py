"""Helpers for tests of the Verified Member application: a storage fake that keeps bytes per bucket, an SMS
recorder, real JPEG images, a full walk through the 7-step wizard, and a moderator approval."""

import io
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import ModerationTask, User


class FakeStorage:
    """Stands in for Supabase Storage. ``objects`` holds keys of every bucket (old tests check membership)."""

    def __init__(self) -> None:
        self.blobs: dict[tuple[str, str], bytes] = {}
        self.objects: set[str] = set()
        self.deleted: list[str] = []

    def signed_upload_url(self, key: str, bucket: str = "verification-evidence") -> str:
        return f"http://storage.test/upload/{bucket}/{key}?token=t"

    def put(self, bucket: str, key: str, data: bytes) -> None:
        self.blobs[(bucket, key)] = data
        self.objects.add(key)

    def exists(self, key: str, bucket: str = "verification-evidence") -> bool:
        return (bucket, key) in self.blobs or (bucket == "verification-evidence" and key in self.objects)

    def signed_download_url(self, key: str, bucket: str = "verification-evidence", seconds: int = 60) -> str:
        return f"http://storage.test/download/{key}?token=t"

    def download(self, key: str, target: Any, bucket: str, max_bytes: int) -> int:
        data = self.blobs[(bucket, key)]
        if len(data) > max_bytes:
            raise ValueError("object larger than allowed")
        target.write(data)
        return len(data)

    def upload(self, key: str, data: bytes, content_type: str, bucket: str) -> None:
        self.put(bucket, key, data if isinstance(data, bytes) else data.read())

    def delete(self, keys: list[str], bucket: str = "verification-evidence") -> None:
        self.deleted += keys
        for key in keys:
            self.blobs.pop((bucket, key), None)
            self.objects.discard(key)


class RecordingSms:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, e164: str, text: str) -> None:
        self.sent.append((e164, text))

    def last_code(self) -> str:
        return self.sent[-1][1].split("code is ")[1][:6]


def jpeg(seed: int | None = None, size: tuple[int, int] = (900, 640), *, fmt: str = "JPEG") -> bytes:
    """A unique photo-like image: random blocks, so neither hash matches another test image."""
    rng = random.Random(seed if seed is not None else uuid.uuid4().int)  # noqa: S311 - test pixels, not security
    picture = Image.new("RGB", size)
    pixels = picture.load()
    assert pixels is not None
    block = 40
    for bx in range(0, size[0], block):
        for by in range(0, size[1], block):
            colour = (rng.randrange(256), rng.randrange(256), rng.randrange(256))
            for x in range(bx, min(bx + block, size[0])):
                for y in range(by, min(by + block, size[1])):
                    pixels[x, y] = colour
    out = io.BytesIO()
    picture.save(out, format=fmt)
    return out.getvalue()


def upload(browser: TestClient, storage: FakeStorage, case_id: str, kind: str, data: bytes | None = None, content_type: str = "image/jpeg") -> dict[str, Any]:
    data = data if data is not None else jpeg()
    intent = browser.post(f"/api/v1/verifications/{case_id}/evidence", json={"kind": kind, "content_type": content_type, "size_bytes": len(data)})
    assert intent.status_code == 200, intent.text
    body = intent.json()
    bucket, key = body["upload_url"].split("/upload/")[1].split("?")[0].split("/", 1)
    storage.put(bucket, key, data)
    done = browser.post(f"/api/v1/verifications/{case_id}/evidence/{body['evidence_id']}/complete")
    assert done.status_code == 200, done.text
    return done.json()


PERSONAL = {
    "legal_name_en": "Nila Rahman",
    "legal_name_bn": "নীলা রহমান",
    "date_of_birth": "1998-04-12",
    "gender": "FEMALE",
    "home_district": "Sylhet",
    "current_area": "Zindabazar",
    "occupation": "EMPLOYED",
}


def age_account(session: Session, email: str) -> None:
    """New accounts are a risk flag (10.1); most tests want an ordinary, older account."""
    session.execute(update(User).where(User.email == email).values(created_at=datetime.now(UTC) - timedelta(days=30)))
    session.commit()


def fill(
    browser: TestClient, storage: FakeStorage, sms: RecordingSms, *, phone: str = "01711000001", doc_number: str = "1234567890",
    personal: dict[str, Any] | None = None, student: bool = False, emergency: bool = True,
) -> dict[str, Any]:
    """Steps 1 to 7, without submitting. Returns the case view."""
    created = browser.post("/api/v1/verifications", json={})
    assert created.status_code == 201, created.text
    case = created.json()
    cid = case["id"]
    assert browser.patch(f"/api/v1/verifications/{cid}/steps/eligibility", json={"age_confirmed": True, "consent": True}).status_code == 200
    details = {**PERSONAL, **(personal or {})}
    if student:
        details["occupation"] = "STUDENT"
    saved = browser.patch(f"/api/v1/verifications/{cid}/steps/personal", json=details)
    assert saved.status_code == 200, saved.text
    sent = browser.post(f"/api/v1/verifications/{cid}/phone/send-code", json={"phone": phone})
    assert sent.status_code == 200, sent.text
    verified = browser.post(f"/api/v1/verifications/{cid}/phone/verify", json={"code": sms.last_code()})
    assert verified.status_code == 200, verified.text
    doc = browser.patch(f"/api/v1/verifications/{cid}/steps/document", json={"doc_type": "NID", "doc_number": doc_number})
    assert doc.status_code == 200, doc.text
    upload(browser, storage, cid, "DOC_FRONT")
    upload(browser, storage, cid, "DOC_BACK")
    if student:
        end = (datetime.now(UTC) + timedelta(days=400)).strftime("%Y-%m")
        stud = browser.patch(f"/api/v1/verifications/{cid}/steps/student", json={"institution_other": "Sylhet Polytechnic Institute", "study_end": end})
        assert stud.status_code == 200, stud.text
        upload(browser, storage, cid, "STUDENT_CARD")
    assert browser.post(f"/api/v1/verifications/{cid}/liveness-challenge").status_code == 200
    upload(browser, storage, cid, "SELFIE")
    if emergency:
        em = browser.patch(f"/api/v1/verifications/{cid}/steps/emergency", json={"name": "Rina Rahman", "relationship": "Sister", "phone": "01811000002"})
        assert em.status_code == 200, em.text
    return browser.get("/api/v1/verifications/mine").json()["case"]


def submit(browser: TestClient, case_id: str) -> dict[str, Any]:
    response = browser.post(f"/api/v1/verifications/{case_id}/submit", json={"declaration": True, "turnstile_token": "ok"})
    assert response.status_code == 200, response.text
    return response.json()


def apply(
    browser: TestClient, session: Session, storage: FakeStorage, sms: RecordingSms, email: str, **kwargs: Any,
) -> dict[str, Any]:
    age_account(session, email)
    case = fill(browser, storage, sms, **kwargs)
    return submit(browser, case["id"])


CHECKLIST = ["genuine", "name", "dob", "gender", "number", "face", "liveness", "signals"]


def lease_for(staff: TestClient, session: Session, case_id: str) -> tuple[str, str]:
    session.expire_all()
    task = session.scalar(select(ModerationTask).where(ModerationTask.subject_id == uuid.UUID(case_id), ModerationTask.status == "open"))
    assert task is not None
    claimed = staff.post(f"/api/v1/admin/tasks/{task.id}/claim")
    assert claimed.status_code == 200, claimed.text
    return str(task.id), claimed.json()["lease_token"]


def decide(staff: TestClient, case_id: str, task_id: str, lease: str, version: int, to: str, **extra: Any) -> Any:
    body = {"to": to, "expected_version": version, "reason_code": extra.pop("reason_code", "start"), "task_id": task_id, "lease_token": lease, **extra}
    return staff.post(f"/api/v1/admin/verification-cases/{case_id}/transition", json=body)


def approve(staff: TestClient, session: Session, case_id: str, *, attributes: dict[str, Any] | None = None, checklist: list[str] | None = None) -> Any:
    task_id, lease = lease_for(staff, session, case_id)
    session.expire_all()
    from app.models import VerificationCase

    case = session.get(VerificationCase, uuid.UUID(case_id))
    assert case is not None
    version = case.version
    if case.state == "submitted":
        started = decide(staff, case_id, task_id, lease, version, "in_review")
        assert started.status_code == 200, started.text
        version += 1
    return decide(
        staff, case_id, task_id, lease, version, "approved", reason_code="documents-ok",
        checklist=checklist if checklist is not None else CHECKLIST,
        attributes=attributes if attributes is not None else {"gender": "FEMALE", "birth_year": 1998},
    )
