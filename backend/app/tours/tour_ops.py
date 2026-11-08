"""Staff Tour Operations with enforcement records and break-glass access."""

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.admin import audit
from app.auth.sessions import Principal
from app.errors import ApiError
from app.models import EnforcementCase, Sanction, User
from app.notify import events
from app.tours import chat, policy, realtime, safety, service
from app.tours.models import (
    BreakglassGrant,
    ChatMessage,
    Tour,
    TourMember,
    TourReport,
    TourStaffAction,
)
from app.tours.policy import now

BREAKGLASS_SCOPES = frozenset({"chat", "safety", "expenses"})


def _tour(session: Session, public_id: str, *, lock: bool = False) -> Tour:
    query = select(Tour).where(Tour.public_id == public_id)
    tour = session.scalar(query.with_for_update() if lock else query)
    if tour is None:
        raise ApiError("NOT_FOUND")
    return tour


def search_tours(session: Session, *, query: str | None, lifecycle: str | None, flag: str | None) -> list[dict[str, Any]]:
    statement = select(Tour)
    if query:
        value = query.strip()
        statement = statement.join(User, User.id == Tour.creator_id).where(
            or_(Tour.public_id.ilike(f"%{value}%"), Tour.code.ilike(f"%{value}%"), Tour.title.ilike(f"%{value}%"), User.display_name.ilike(f"%{value}%"))
        )
    if lifecycle:
        statement = statement.where(Tour.lifecycle == lifecycle)
    if flag == "SUSPENDED":
        statement = statement.where(Tour.suspended_at.is_not(None))
    elif flag == "AT_RISK":
        statement = statement.where(Tour.is_at_risk.is_(True))
    return [service.card(session, tour) for tour in session.scalars(statement.order_by(Tour.updated_at.desc()).limit(100))]


def detail(session: Session, public_id: str) -> dict[str, Any]:
    tour = _tour(session, public_id)
    reports = session.scalars(select(TourReport).where(TourReport.tour_id == tour.id).order_by(TourReport.created_at.desc()).limit(50))
    members = service.member_list(session, tour, full_names=True, viewer_id=None)
    user_ids = {
        str(member.id): str(member.user_id)
        for member in session.scalars(select(TourMember).where(TourMember.tour_id == tour.id))
    }
    for member in members:
        member["user_id"] = user_ids.get(member["member_id"])
    return service.card(session, tour) | {
        "members": members,
        "reports": [{"id": str(item.id), "subject_kind": item.subject_kind, "reason_code": item.reason_code, "state": item.state, "created_at": item.created_at.isoformat()} for item in reports],
        "changes": service.workspace_view(session, tour, policy.viewer_for(session, tour.creator_id))["changes"],
    }


def suspend(session: Session, principal: Principal, public_id: str, reason_code: str, note: str | None) -> Tour:
    tour = _tour(session, public_id, lock=True)
    if tour.suspended_at is not None or tour.lifecycle in ("CANCELLED", "ARCHIVED"):
        raise ApiError("TRANSITION_NOT_ALLOWED")
    case = EnforcementCase(kind="tour", tour_id=tour.id, state="open", opened_by=principal.user.id, reason_code=reason_code, note=(note or "")[:500] or None)
    session.add(case)
    tour.suspended_at = now()
    tour.version += 1
    realtime.revoke_all(session, tour.id)
    audit.record(session, actor=principal, action="tour.suspended", target_type="tour", target_id=tour.id, reason=reason_code, metadata={"case_id": str(case.id)})
    events.emit(session, "tour.suspended", tour.id, {"public_id": tour.public_id, "tour_title": tour.title, "member_ids": service.member_ids(session, tour.id)}, aggregate_type="tour")
    return tour


def restore(session: Session, principal: Principal, public_id: str, reason_code: str) -> Tour:
    tour = _tour(session, public_id, lock=True)
    if tour.suspended_at is None:
        raise ApiError("TRANSITION_NOT_ALLOWED")
    case = session.scalar(select(EnforcementCase).where(EnforcementCase.tour_id == tour.id, EnforcementCase.state == "open").order_by(EnforcementCase.created_at.desc()).with_for_update())
    if case is not None:
        case.state, case.closed_at, case.updated_at = "restored", now(), now()
        case.version += 1
    tour.suspended_at = None
    tour.version += 1
    audit.record(session, actor=principal, action="tour.restored", target_type="tour", target_id=tour.id, reason=reason_code)
    events.emit(session, "tour.restored", tour.id, {"public_id": tour.public_id, "tour_title": tour.title, "member_ids": service.member_ids(session, tour.id)}, aggregate_type="tour")
    return tour


def cancel_by_staff(session: Session, principal: Principal, public_id: str, reason_code: str, note: str | None) -> dict[str, Any]:
    tour = _tour(session, public_id, lock=True)
    if tour.lifecycle == "CONFIRMED":
        if principal.role != "superadmin":
            raise ApiError("FORBIDDEN")
        pending = session.scalar(select(TourStaffAction).where(TourStaffAction.tour_id == tour.id, TourStaffAction.action == "cancel", TourStaffAction.state == "pending").with_for_update())
        if pending is None:
            pending = TourStaffAction(tour_id=tour.id, action="cancel", reason_code=reason_code, note=(note or "")[:500] or None, requested_by=principal.user.id)
            session.add(pending)
            session.flush()
            audit.record(session, actor=principal, action="tour.staff_cancel_requested", target_type="tour", target_id=tour.id, reason=reason_code, metadata={"action_id": str(pending.id)})
            return {"state": "pending_second_approval", "action_id": str(pending.id)}
        if pending.requested_by == principal.user.id:
            raise ApiError("SECOND_APPROVAL_REQUIRED")
        pending.state, pending.approved_by, pending.decided_at = "done", principal.user.id, now()
    elif tour.lifecycle not in ("RECRUITING", "DRAFT"):
        raise ApiError("TRANSITION_NOT_ALLOWED")
    service.cancel(session, tour, by="STAFF", reason="Cancelled by Abhijatri", actor_id=principal.user.id)
    case = EnforcementCase(kind="tour", tour_id=tour.id, state="removed", opened_by=principal.user.id, reason_code=reason_code, note=(note or "")[:500] or None, closed_at=now())
    session.add(case)
    audit.record(session, actor=principal, action="tour.staff_cancelled", target_type="tour", target_id=tour.id, reason=reason_code, metadata={"case_id": str(case.id)})
    return {"state": "cancelled", "public_id": tour.public_id}


def remove_member(session: Session, principal: Principal, public_id: str, member_id: uuid.UUID, reason_code: str) -> Tour:
    tour = _tour(session, public_id, lock=True)
    member = session.get(TourMember, member_id)
    if member is None or member.tour_id != tour.id or member.state != "ACTIVE" or member.role == "CREATOR":
        raise ApiError("NOT_FOUND")
    service._end_membership(session, tour, member, "REMOVED", reason_code)  # noqa: SLF001
    case = EnforcementCase(kind="tour", tour_member_id=member.id, state="removed", opened_by=principal.user.id, reason_code=reason_code, closed_at=now())
    session.add(case)
    audit.record(session, actor=principal, action="tour.member_removed", target_type="tour_member", target_id=member.id, reason=reason_code)
    return tour


def hide_message(session: Session, principal: Principal, public_id: str, message_id: uuid.UUID, report_id: uuid.UUID, reason_code: str) -> dict[str, Any]:
    tour = _tour(session, public_id, lock=True)
    report = session.get(TourReport, report_id)
    message = session.scalar(select(ChatMessage).where(ChatMessage.id == message_id, ChatMessage.tour_id == tour.id).with_for_update())
    if report is None or report.tour_id != tour.id or message is None:
        raise ApiError("NOT_FOUND")
    message.hidden_by_staff_at, message.held_for_report = now(), True
    report.state, report.resolved_by, report.resolved_at = "actioned", principal.user.id, now()
    case = EnforcementCase(kind="tour", chat_message_id=message.id, state="removed", opened_by=principal.user.id, reason_code=reason_code, closed_at=now())
    session.add(case)
    audit.record(session, actor=principal, action="tour.message_hidden", target_type="chat_message", target_id=message.id, reason=reason_code, metadata={"report_id": str(report.id)})
    realtime.after_commit(session, tour.id, message.seq, kind="message")
    return {"hidden": True, "message_id": str(message.id)}


def restrict_user(session: Session, principal: Principal, user_id: uuid.UUID, reason_code: str, days: int) -> dict[str, Any]:
    if session.get(User, user_id) is None or user_id == principal.user.id or days < 1 or (days > 30 and principal.role != "superadmin"):
        raise ApiError("FORBIDDEN")
    case = EnforcementCase(kind="account", subject_user_id=user_id, state="open", opened_by=principal.user.id, reason_code=reason_code)
    session.add(case)
    session.flush()
    sanction = Sanction(user_id=user_id, enforcement_case_id=case.id, kind="tourmate_restriction", scope="tours", ends_at=now() + timedelta(days=days), reason_code=reason_code, created_by=principal.user.id)
    session.add(sanction)
    audit.record(session, actor=principal, action="tour.user_restricted", target_type="user", target_id=user_id, reason=reason_code, metadata={"days": days, "case_id": str(case.id)})
    return {"restricted": True, "until": sanction.ends_at.isoformat() if sanction.ends_at else None}


def grant_breakglass(session: Session, principal: Principal, public_id: str, reason: str, scopes: list[str]) -> BreakglassGrant:
    tour = _tour(session, public_id)
    selected = sorted(set(scopes))
    if len(reason.strip()) < 10 or not selected or any(scope not in BREAKGLASS_SCOPES for scope in selected):
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "reason", "code": "REQUIRED"}])
    grant = BreakglassGrant(staff_id=principal.user.id, tour_id=tour.id, reason=reason.strip()[:500], scope=selected, expires_at=now() + timedelta(minutes=60))
    session.add(grant)
    session.flush()
    audit.record(session, actor=principal, action="tour.breakglass_granted", target_type="tour", target_id=tour.id, reason=reason.strip()[:500], metadata={"grant_id": str(grant.id), "scope": selected})
    return grant


def _grant(session: Session, principal: Principal, tour: Tour, scope: str) -> BreakglassGrant:
    grant = session.scalar(select(BreakglassGrant).where(
        BreakglassGrant.tour_id == tour.id, BreakglassGrant.expires_at > now(), BreakglassGrant.scope.contains([scope]),
        or_(BreakglassGrant.staff_id == principal.user.id, BreakglassGrant.staff_id.is_(None)),
    ).order_by(BreakglassGrant.expires_at.desc()))
    if grant is None:
        raise ApiError("FORBIDDEN")
    audit.record(session, actor=principal, action="tour.breakglass_viewed", target_type="tour", target_id=tour.id, reason=grant.reason, metadata={"grant_id": str(grant.id), "scope": scope})
    return grant


def private_view(session: Session, principal: Principal, public_id: str, scope: str) -> dict[str, Any]:
    tour = _tour(session, public_id)
    _grant(session, principal, tour, scope)
    if scope == "safety":
        return {"scope": scope, "items": safety.staff_view(session, tour)}
    if scope == "chat":
        return {"scope": scope, "items": chat.staff_history(session, tour)}
    if scope == "expenses":
        from app.tours import workspace

        return {"scope": scope, "items": workspace.budget(session, policy.viewer_for(session, tour.creator_id), tour)}
    raise ApiError("NOT_FOUND")


def notify_organisers_after_grants(session: Session, moment: Any) -> int:
    grants = list(session.scalars(select(BreakglassGrant).where(BreakglassGrant.expires_at <= moment, BreakglassGrant.organisers_told_at.is_(None)).limit(100)))
    for grant in grants:
        tour = session.get(Tour, grant.tour_id)
        if tour is not None:
            events.emit(session, "tour.staff_reviewed", tour.id, {"public_id": tour.public_id, "tour_title": tour.title, "member_ids": service.organiser_ids(session, tour.id)}, aggregate_type="tour", dedupe_key=f"breakglass-notice:{grant.id}")
        grant.organisers_told_at = moment
    return len(grants)


# Report tasks in the shared staff queue (tour_report, chat_report, tour_safety)

REPORT_TASKS = frozenset({"tour_report", "chat_report", "tour_safety"})
REPORT_ACTIONS = frozenset({"dismiss", "hide_message", "suspend_tour", "restrict_user", "noted"})


def _reported_user(session: Session, report: TourReport) -> uuid.UUID | None:
    """Who the report is about: the sender of a reported message, or a reported member."""
    if report.subject_kind == "MESSAGE" and report.subject_id:
        return session.scalar(select(ChatMessage.sender_id).where(ChatMessage.id == report.subject_id))
    if report.subject_kind == "MEMBER" and report.subject_id:
        member = session.get(TourMember, report.subject_id)
        return member.user_id if member else None
    return None


def report_summary(session: Session, task_type: str, report_id: uuid.UUID) -> dict[str, Any] | None:
    """Queue card and review screen for a tour, chat or SOS report. Chat reports carry the snapshot taken
    when the report was made (the message and the 20 around it), so evidence survives deletion."""
    report = session.get(TourReport, report_id)
    if report is None:
        return None
    tour = session.get(Tour, report.tour_id)
    reporter = session.get(User, report.reporter_id) if report.reporter_id else None
    target_id = _reported_user(session, report)
    target = session.get(User, target_id) if target_id else None
    message = session.scalar(select(ChatMessage).where(ChatMessage.id == report.subject_id)) if report.subject_kind == "MESSAGE" and report.subject_id else None
    return {
        "kind": "tour_report",
        "task_type": task_type,
        "report_id": str(report.id),
        "state": report.state,
        "version": report.version,
        "subject_kind": report.subject_kind,
        "reason_code": report.reason_code,
        "details": report.details,
        "reporter": reporter.display_name if reporter else None,
        "reported_user": {"id": str(target.id), "display_name": target.display_name} if target else None,
        "message": {"id": str(message.id), "seq": message.seq, "hidden": message.hidden_by_staff_at is not None} if message else None,
        "context": (report.context or {}).get("messages", []),
        "tour": {
            "public_id": tour.public_id, "title": tour.title, "lifecycle": tour.lifecycle,
            "suspended": tour.suspended_at is not None, "start_date": tour.start_date.isoformat(), "end_date": tour.end_date.isoformat(),
        } if tour else None,
        "created_at": report.created_at.isoformat(),
    }


def resolve_report(
    session: Session, principal: Principal, report_id: uuid.UUID, *, task_id: uuid.UUID, lease_token: uuid.UUID,
    action: str, reason_code: str, note: str | None, days: int = 7,
) -> dict[str, Any]:
    """Close a tour, chat or SOS report under the task lease, optionally acting on it in the same transaction."""
    from app.admin import tasks

    if action not in REPORT_ACTIONS:
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "action", "code": "INVALID_VALUE"}])
    task = tasks.require_lease(session, principal, task_id, lease_token, subject_id=report_id)
    if task.task_type not in REPORT_TASKS:
        raise ApiError("NOT_FOUND")
    report = session.scalar(select(TourReport).where(TourReport.id == report_id).with_for_update())
    if report is None:
        raise ApiError("NOT_FOUND")
    if report.state in ("actioned", "dismissed"):
        raise ApiError("TRANSITION_NOT_ALLOWED")
    tour = session.get(Tour, report.tour_id)
    if tour is None:
        raise ApiError("NOT_FOUND")
    result: dict[str, Any] = {}
    if action == "hide_message":
        if report.subject_kind != "MESSAGE" or report.subject_id is None:
            raise ApiError("TRANSITION_NOT_ALLOWED")
        result = hide_message(session, principal, tour.public_id, report.subject_id, report.id, reason_code)
    elif action == "suspend_tour":
        suspend(session, principal, tour.public_id, reason_code, note)
    elif action == "restrict_user":
        target = _reported_user(session, report)
        if target is None:
            raise ApiError("TRANSITION_NOT_ALLOWED")
        result = restrict_user(session, principal, target, reason_code, days)
    report.state = "dismissed" if action == "dismiss" else "actioned"
    report.resolved_by, report.resolved_at = principal.user.id, now()
    report.resolution_note = (note or "")[:500] or None
    report.version += 1
    tasks.complete(task)
    audit.record(
        session, actor=principal, action="tour.report_resolved", target_type="tour_report", target_id=report.id,
        reason=reason_code, metadata={"action": action, "tour": tour.public_id, "task_type": task.task_type},
    )
    return {"report_id": str(report.id), "state": report.state, "action": action, **result}
