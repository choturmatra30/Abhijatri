"""Tour Operations endpoints in the existing staff security boundary."""

import uuid
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.sessions import Principal, staff_principal
from app.db import get_session
from app.errors import ApiError
from app.tours import service, tour_ops

DbSession = Annotated[Session, Depends(get_session)]
Staff = Annotated[Principal, Depends(staff_principal("moderator", "superadmin"))]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/api/v1/admin/tours", tags=["tour-operations"], dependencies=[Depends(_private)])


def _commit[T](session: Session, work: Callable[[], T]) -> T:
    try:
        result = work()
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


@router.post("/reports/{report_id}/resolve")
def resolve_report(report_id: uuid.UUID, body: dict[str, Any], principal: Staff, session: DbSession) -> dict[str, Any]:
    """Close a tour, chat or SOS report task (lease required); the chosen action runs in the same transaction."""
    try:
        task_id, lease = uuid.UUID(str(body["task_id"])), uuid.UUID(str(body["lease_token"]))
    except (KeyError, ValueError) as error:
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "lease_token", "code": "REQUIRED"}]) from error
    return _commit(session, lambda: tour_ops.resolve_report(
        session, principal, report_id, task_id=task_id, lease_token=lease, action=str(body.get("action") or "dismiss"),
        reason_code=str(body.get("reason_code") or "other"), note=body.get("note"), days=int(body.get("days") or 7),
    ))


@router.get("")
def search(
    principal: Staff,
    session: DbSession,
    q: Annotated[str | None, Query(max_length=80)] = None,
    lifecycle: str | None = None,
    flag: str | None = None,
) -> dict[str, Any]:
    return {"items": tour_ops.search_tours(session, query=q, lifecycle=lifecycle, flag=flag)}


@router.get("/{public_id}")
def detail(public_id: str, principal: Staff, session: DbSession) -> dict[str, Any]:
    return tour_ops.detail(session, public_id)


@router.post("/{public_id}/suspend")
def suspend(public_id: str, body: dict[str, Any], principal: Staff, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: service.card(session, tour_ops.suspend(session, principal, public_id, str(body.get("reason_code") or "safety"), body.get("note"))))


@router.post("/{public_id}/restore")
def restore(public_id: str, body: dict[str, Any], principal: Staff, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: service.card(session, tour_ops.restore(session, principal, public_id, str(body.get("reason_code") or "resolved"))))


@router.post("/{public_id}/cancel")
def cancel(public_id: str, body: dict[str, Any], principal: Staff, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: tour_ops.cancel_by_staff(session, principal, public_id, str(body.get("reason_code") or "safety"), body.get("note")))


@router.post("/{public_id}/members/{member_id}/remove")
def remove_member(public_id: str, member_id: uuid.UUID, body: dict[str, Any], principal: Staff, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: service.card(session, tour_ops.remove_member(session, principal, public_id, member_id, str(body.get("reason_code") or "safety"))))


@router.post("/{public_id}/messages/{message_id}/hide")
def hide_message(public_id: str, message_id: uuid.UUID, body: dict[str, Any], principal: Staff, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: tour_ops.hide_message(session, principal, public_id, message_id, uuid.UUID(str(body["report_id"])), str(body.get("reason_code") or "harassment")))


@router.post("/users/{user_id}/restrict")
def restrict_user(user_id: uuid.UUID, body: dict[str, Any], principal: Staff, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: tour_ops.restrict_user(session, principal, user_id, str(body.get("reason_code") or "abuse"), int(body.get("days") or 7)))


@router.post("/{public_id}/breakglass", status_code=201)
def breakglass(public_id: str, body: dict[str, Any], principal: Staff, session: DbSession) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        grant = tour_ops.grant_breakglass(session, principal, public_id, str(body.get("reason") or ""), list(body.get("scope") or []))
        return {"id": str(grant.id), "scope": grant.scope, "expires_at": grant.expires_at.isoformat()}

    return _commit(session, work)


@router.get("/{public_id}/private/{scope}")
def private_view(public_id: str, scope: str, principal: Staff, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: tour_ops.private_view(session, principal, public_id, scope))
