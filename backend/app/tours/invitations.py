"""Direct invitations (spec 11). An organiser's invitation counts as approval in advance; accepting it joins the
tour at once, with capacity re-checked under the tour lock at that moment (11.4)."""

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.abuse import Rule, hit
from app.config import get_settings
from app.errors import ApiError
from app.models import User
from app.tours import policy, search, service
from app.tours.models import InvitationOptOut, Tour, TourInvitation, TourJoinRequest, TourMember
from app.tours.policy import Viewer, now

EXPIRY = timedelta(days=7)


def _problem(session: Session, tour: Tour, inviter: Viewer, invitee_id: uuid.UUID) -> str | None:
    """11.2: the server's checks. Returned as a code to the organiser; never says who blocked whom."""
    if invitee_id == inviter.user_id:
        return "SELF"
    person = policy.viewer_for(session, invitee_id)
    if not person.verified or not person.adult or person.restricted:
        return "NOT_ELIGIBLE"
    if not policy.eligible(person, tour.policy, tour.start_date):
        return "POLICY_NOT_MET"
    if policy.blocked_between(session, invitee_id, policy.active_member_ids(session, tour.id)):
        return "NOT_ELIGIBLE"
    if session.scalar(select(TourMember.id).where(TourMember.tour_id == tour.id, TourMember.user_id == invitee_id)):
        return "ALREADY_IN_OR_LEFT"
    if session.scalar(select(TourJoinRequest.id).where(TourJoinRequest.tour_id == tour.id, TourJoinRequest.user_id == invitee_id, TourJoinRequest.state == "PENDING")):
        return "ALREADY_REQUESTED"
    if service._overlapping(session, invitee_id, tour.start_date, tour.end_date):  # noqa: SLF001
        return "DATE_OVERLAP"
    if session.scalar(select(TourInvitation.id).where(TourInvitation.tour_id == tour.id, TourInvitation.invitee_id == invitee_id, TourInvitation.state.in_(("DECLINED", "PENDING")))):
        return "ALREADY_INVITED"
    opted_out = session.scalar(
        select(InvitationOptOut.invitee_id).where(
            InvitationOptOut.invitee_id == invitee_id,
            InvitationOptOut.organiser_id.in_(select(TourMember.user_id).where(TourMember.tour_id == tour.id, TourMember.state == "ACTIVE", TourMember.role.in_(policy.ORGANISER_ROLES))),
        )
    )
    if opted_out:
        return "NOT_ELIGIBLE"  # "Don't invite me again" acts like a soft block (11.6)
    return None


def invite(session: Session, viewer: Viewer, tour_id: uuid.UUID, invitee_id: uuid.UUID, factory: Any) -> TourInvitation:
    settings = get_settings()
    tour = policy.locked_tour(session, tour_id)
    policy.require(policy.membership(session, tour.id, viewer.user_id), "tour.invite")
    policy.require_unrestricted(viewer)
    service._guard_open_for_members(tour)  # noqa: SLF001
    if tour.recruitment != "OPEN":
        raise ApiError("RECRUITMENT_CLOSED")
    problem = _problem(session, tour, viewer, invitee_id)
    if problem:
        raise ApiError("INVITATION_NOT_ALLOWED", field_errors=[{"field": "invitee", "code": problem}])
    seats_left = tour.max_members - tour.seats_taken
    pending = session.scalar(select(func.count()).select_from(TourInvitation).where(TourInvitation.tour_id == tour.id, TourInvitation.state == "PENDING")) or 0
    if pending >= 2 * seats_left:
        raise ApiError("INVITATION_NOT_ALLOWED", field_errors=[{"field": "invitee", "code": "TOO_MANY_PENDING"}])  # 11.7
    count, wait = hit(factory, Rule("tour_invitations", 86400, settings.tour_invitations_per_day), viewer.user_id.bytes)
    if wait is not None:
        service._signal(session, viewer.user_id, "mass_invitations", count=count)  # noqa: SLF001
        raise ApiError("RATE_LIMITED", headers={"Retry-After": str(wait)})
    invitation = TourInvitation(
        id=uuid.uuid4(), tour_id=tour.id, invitee_id=invitee_id, inviter_id=viewer.user_id, expires_at=min(now() + EXPIRY, tour.recruit_deadline),
    )
    session.add(invitation)
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError as error:
        raise ApiError("INVITATION_NOT_ALLOWED", field_errors=[{"field": "invitee", "code": "ALREADY_INVITED"}]) from error
    service._emit(session, "tour.invitation_received", tour, {"user_id": str(invitee_id), "invitation_id": str(invitation.id)})  # noqa: SLF001
    return invitation


def mine(session: Session, viewer: Viewer) -> list[dict[str, Any]]:
    rows = session.execute(
        select(TourInvitation, Tour, User)
        .join(Tour, Tour.id == TourInvitation.tour_id)
        .join(User, User.id == TourInvitation.inviter_id)
        .where(TourInvitation.invitee_id == viewer.user_id, TourInvitation.state == "PENDING")
        .order_by(TourInvitation.created_at.desc())
    ).all()
    out = []
    for invitation, tour, inviter in rows:
        if invitation.expires_at <= now():
            continue
        out.append({
            "id": str(invitation.id),
            "expires_at": invitation.expires_at.isoformat(),
            "from": policy.first_name(inviter.display_name),
            "tour": service.card(session, tour) | {"match": search.score_for(session, viewer.user_id, tour)},
        })
    return out


def _own(session: Session, viewer: Viewer, invitation_id: uuid.UUID) -> TourInvitation:
    invitation = session.scalar(select(TourInvitation).where(TourInvitation.id == invitation_id).with_for_update())
    if invitation is None or invitation.invitee_id != viewer.user_id:
        raise ApiError("NOT_FOUND")
    if invitation.state != "PENDING":
        raise ApiError("TRANSITION_NOT_ALLOWED")
    return invitation


def accept(session: Session, viewer: Viewer, invitation_id: uuid.UUID) -> Tour:
    head = session.get(TourInvitation, invitation_id)
    if head is None or head.invitee_id != viewer.user_id:
        raise ApiError("NOT_FOUND")
    tour = policy.locked_tour(session, head.tour_id)  # tour first, then the invitation: one lock order
    invitation = _own(session, viewer, invitation_id)
    policy.require_unrestricted(viewer)
    if invitation.expires_at <= now():
        invitation.state = "EXPIRED"
        raise ApiError("TRANSITION_NOT_ALLOWED")
    try:
        service._guard_open_for_members(tour)  # noqa: SLF001
    except ApiError:
        invitation.state, invitation.answered_at = "CLOSED", now()  # 11.4: the tour filled up or closed
        session.commit()
        raise
    problem = service.requester_problem(session, tour, viewer.user_id, 1)
    if problem == "NO_SEATS":
        invitation.state, invitation.answered_at = "CLOSED", now()
        session.commit()
        raise ApiError("TOUR_FULL")
    if problem:
        raise ApiError("REQUEST_NOT_ALLOWED")
    service._join(session, tour, viewer.user_id, seats=1, companions=None, via="INVITATION", approved_by=invitation.inviter_id)  # noqa: SLF001
    invitation.state, invitation.answered_at = "ACCEPTED", now()
    service._emit(session, "tour.invitation_answered", tour, {"user_id": str(invitation.inviter_id), "outcome": "accepted"})  # noqa: SLF001
    return tour


def decline(session: Session, viewer: Viewer, invitation_id: uuid.UUID, *, dont_invite_again: bool) -> TourInvitation:
    invitation = _own(session, viewer, invitation_id)
    invitation.state, invitation.answered_at = "DECLINED", now()
    tour = session.get(Tour, invitation.tour_id)
    if dont_invite_again and session.get(InvitationOptOut, (viewer.user_id, invitation.inviter_id)) is None:
        session.add(InvitationOptOut(invitee_id=viewer.user_id, organiser_id=invitation.inviter_id))
    if tour is not None:
        service._emit(session, "tour.invitation_answered", tour, {"user_id": str(invitation.inviter_id), "outcome": "declined"})  # noqa: SLF001
    return invitation


def expire_due(session: Session, moment: Any) -> int:
    rows = session.scalars(select(TourInvitation).where(TourInvitation.state == "PENDING", TourInvitation.expires_at <= moment).limit(200).with_for_update(skip_locked=True))
    count = 0
    for invitation in rows:
        invitation.state, invitation.answered_at = "EXPIRED", moment
        count += 1
    return count
