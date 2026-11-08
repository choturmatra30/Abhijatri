"""Reports about tours, members, requests, invitations and chat messages (spec 16.1), plus user blocks."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin import audit, tasks
from app.errors import ApiError
from app.models import User
from app.tours import policy
from app.tours.models import Tour, TourMember, TourReport, UserBlock
from app.tours.policy import Viewer

REASONS = ("spam", "harassment", "safety", "false_information", "privacy", "fraud", "other")
SUBJECTS = ("TOUR", "MEMBER", "REQUEST", "INVITATION", "REMOVAL")


def _bad(field: str, code: str = "INVALID_VALUE") -> ApiError:
    return ApiError("VALIDATION_FAILED", field_errors=[{"field": field, "code": code}])


def check_reason(code: str) -> None:
    if code not in REASONS:
        raise _bad("reason_code")


def report_tour(session: Session, viewer: Viewer, tour: Tour, *, subject_kind: str, subject_id: uuid.UUID | None, reason_code: str, details: str | None) -> TourReport:
    check_reason(reason_code)
    if subject_kind not in SUBJECTS:
        raise _bad("subject_kind")
    if policy.membership(session, tour.id, viewer.user_id) is None and subject_kind != "REMOVAL":
        raise ApiError("NOT_FOUND")  # only people connected to the tour can report it
    item = TourReport(tour_id=tour.id, reporter_id=viewer.user_id, subject_kind=subject_kind, subject_id=subject_id, reason_code=reason_code, details=(details or "")[:1000] or None)
    session.add(item)
    session.flush()
    tasks.ensure_task(session, "tour_report", item.id, priority=2 if reason_code in ("safety", "harassment") else 1)
    audit.record(session, actor=None, action="tour.report_created", target_type="tour", target_id=tour.id, metadata={"subject": subject_kind, "reason": reason_code})
    return item


def block(session: Session, viewer: Viewer, user_id: uuid.UUID) -> dict[str, Any]:
    if user_id == viewer.user_id or session.get(User, user_id) is None:
        raise ApiError("NOT_FOUND")
    if session.get(UserBlock, (viewer.user_id, user_id)) is None:
        session.add(UserBlock(blocker_id=viewer.user_id, blocked_id=user_id))
        audit.record(session, actor=None, action="block.created", target_type="user", target_id=user_id, metadata={"by": str(viewer.user_id)})
    session.flush()
    return {"blocked": True}


def unblock(session: Session, viewer: Viewer, user_id: uuid.UUID) -> dict[str, Any]:
    row = session.get(UserBlock, (viewer.user_id, user_id))
    if row is not None:
        session.delete(row)
        audit.record(session, actor=None, action="block.removed", target_type="user", target_id=user_id, metadata={"by": str(viewer.user_id)})
    return {"blocked": False}


def blocks(session: Session, viewer: Viewer) -> list[dict[str, Any]]:
    rows = session.execute(select(UserBlock, User).join(User, User.id == UserBlock.blocked_id).where(UserBlock.blocker_id == viewer.user_id)).all()
    return [{"user_id": str(u.id), "first_name": policy.first_name(u.display_name)} for _, u in rows]


def member_user(session: Session, tour: Tour, member_id: uuid.UUID) -> uuid.UUID:
    member = session.get(TourMember, member_id)
    if member is None or member.tour_id != tour.id:
        raise ApiError("NOT_FOUND")
    return member.user_id
