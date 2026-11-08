"""Member routes of the Verified Member application (sign-up form 11).

Every route needs a signed-in member; writes need the CSRF token. Submit, respond and withdraw also take an
``Idempotency-Key``, so a retry after a lost response returns the first answer instead of acting twice.
Answers are ``no-store``: they carry the applicant's own personal data.
"""

import uuid
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app import idempotency as idem
from app.auth.sessions import MemberPrincipal, Principal, require_csrf
from app.client_address import network_digest
from app.db import get_session
from app.storage import StorageClient, get_storage
from app.turnstile import Verifier, get_turnstile_verifier
from app.verification import geo, service


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/api/v1", tags=["verification"], dependencies=[Depends(_no_store)])
DbSession = Annotated[Session, Depends(get_session)]
Writer = Annotated[Principal, Depends(require_csrf)]
Storage = Annotated[StorageClient, Depends(get_storage)]
Turnstile = Annotated[Verifier, Depends(get_turnstile_verifier)]


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpenBody(_Body):
    purpose: str = Field(default="initial", pattern="^(initial|renewal|student_update)$")
    statement: str | None = Field(default=None, max_length=1000)  # accepted for old clients; not required


class PhoneBody(_Body):
    phone: str = Field(min_length=10, max_length=20)


class EmailBody(_Body):
    email: str = Field(min_length=6, max_length=200)


class CodeBody(_Body):
    code: str = Field(min_length=6, max_length=6)


class EvidenceBody(_Body):
    kind: str = Field(default="DOC_FRONT", pattern="^(DOC_FRONT|DOC_BACK|SELFIE|STUDENT_CARD)$")
    content_type: str = Field(max_length=80)
    size_bytes: int = Field(ge=1)


class SubmitBody(_Body):
    declaration: bool
    turnstile_token: str | None = Field(default=None, max_length=4096)


class EmptyBody(_Body):
    statement: str | None = Field(default=None, max_length=1000)


def _commit[T](session: Session, work: Callable[[], T]) -> T:
    try:
        result = work()
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def _idempotent(
    session: Session, principal: Principal, key_header: str | None, endpoint: str, path: dict[str, Any], body: dict[str, Any] | None,
    work: Callable[[], dict[str, Any]], status_code: int = 200,
) -> dict[str, Any] | JSONResponse:
    key = idem.parse_key(key_header)
    try:
        claim = idem.begin(
            session, key=key, scope=idem.member_scope(principal.user.id), endpoint=endpoint,
            request_fingerprint=idem.fingerprint_json(method="POST", path=path, body=body),
        )
        if isinstance(claim, idem.Replay):
            session.rollback()
            return idem.replay_response(claim)
        result = work()
        idem.finish_json(session, claim, status_code, result)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


# ---- reading ----


@router.get("/verifications/mine")
def my_verification(principal: MemberPrincipal, session: DbSession) -> dict[str, Any]:
    return service.mine(session, principal)


@router.get("/verifications/districts")
def districts() -> dict[str, Any]:
    return {"divisions": [{"division": division, "districts": list(items)} for division, items in geo.DIVISIONS.items()]}


@router.get("/verifications/institutions")
def institutions(principal: MemberPrincipal, session: DbSession, q: Annotated[str | None, Query(max_length=60)] = None) -> dict[str, Any]:
    return {"items": service.institutions(session, q)}


# ---- the application ----


@router.post("/verifications", status_code=201)
def open_application(body: OpenBody, principal: Writer, session: DbSession) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        case = service.open_case(session, principal, purpose=body.purpose)
        if body.statement:
            case.statement = body.statement
        return service.own_view(session, case)

    return _commit(session, work)


@router.patch("/verifications/{case_id}/steps/{step}")
def save_step(case_id: uuid.UUID, step: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: service.own_view(session, service.save_step(session, principal, case_id, step, body)))


@router.post("/verifications/{case_id}/phone/send-code")
def phone_send(case_id: uuid.UUID, body: PhoneBody, principal: Writer, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: service.send_phone_code(session, principal, case_id, body.phone))


@router.post("/verifications/{case_id}/phone/verify")
def phone_verify(case_id: uuid.UUID, body: CodeBody, principal: Writer, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: service.own_view(session, service.verify_phone_code(session, principal, case_id, body.code)))


@router.post("/verifications/{case_id}/student-email/send-code")
def student_email_send(case_id: uuid.UUID, body: EmailBody, principal: Writer, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: service.send_student_email_code(session, principal, case_id, body.email))


@router.post("/verifications/{case_id}/student-email/verify")
def student_email_verify(case_id: uuid.UUID, body: CodeBody, principal: Writer, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: service.own_view(session, service.verify_student_email_code(session, principal, case_id, body.code)))


@router.post("/verifications/{case_id}/liveness-challenge")
def liveness(case_id: uuid.UUID, principal: Writer, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: service.issue_liveness(session, principal, case_id))


@router.post("/verifications/{case_id}/evidence")
def evidence_upload(case_id: uuid.UUID, body: EvidenceBody, principal: Writer, session: DbSession, storage: Storage) -> dict[str, Any]:
    """A one-time signed URL to a quarantine object; the browser PUTs the image to it directly."""
    return _commit(session, lambda: service.request_evidence(session, storage, principal, case_id, kind=body.kind, content_type=body.content_type, size_bytes=body.size_bytes))


@router.post("/verifications/{case_id}/evidence/{evidence_id}/complete")
def evidence_complete(case_id: uuid.UUID, evidence_id: uuid.UUID, principal: Writer, session: DbSession, storage: Storage) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        item = service.complete_evidence(session, storage, principal, case_id, evidence_id)
        return {"id": str(item.id), "status": item.status, "kind": item.kind}

    return _commit(session, work)


@router.post("/verifications/{case_id}/submit", response_model=None)
def submit(
    request: Request, case_id: uuid.UUID, body: SubmitBody, principal: Writer, session: DbSession, verifier: Turnstile, idempotency_key: idem.KeyHeader = None,
) -> dict[str, Any] | JSONResponse:
    def work() -> dict[str, Any]:
        verifier(body.turnstile_token, action="verification_submit", remote_address=None)
        case = service.submit(session, principal, case_id, declaration=body.declaration, network=network_digest(request))
        return service.own_view(session, case)

    return _idempotent(
        session, principal, idempotency_key, idem.Endpoint.VERIFICATION_SUBMIT, {"case_id": case_id}, body.model_dump(), work,
    )


@router.post("/verifications/{case_id}/respond", response_model=None)
def respond(case_id: uuid.UUID, principal: Writer, session: DbSession, body: EmptyBody | None = None, idempotency_key: idem.KeyHeader = None) -> dict[str, Any] | JSONResponse:
    return _idempotent(
        session, principal, idempotency_key, idem.Endpoint.VERIFICATION_RESPOND, {"case_id": case_id}, None,
        lambda: service.own_view(session, service.respond(session, principal, case_id)),
    )


@router.post("/verifications/{case_id}/withdraw", response_model=None)
def withdraw(case_id: uuid.UUID, principal: Writer, session: DbSession, storage: Storage, idempotency_key: idem.KeyHeader = None) -> dict[str, Any] | JSONResponse:
    return _idempotent(
        session, principal, idempotency_key, idem.Endpoint.VERIFICATION_WITHDRAW, {"case_id": case_id}, None,
        lambda: service.own_view(session, service.withdraw(session, storage, principal, case_id)),
    )
