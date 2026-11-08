"""Who may see and do what in Tours (spec 2, 6, 13.2; architecture 10.2).

Gate order on every tour route: verified and 18+ -> not restricted -> member or eligible viewer -> role ->
resource state. Any failure before "member or eligible viewer" is a 404, never a 403, so private tours and
their existence are never revealed (AC-01). Eligibility reads ``verification_attributes`` only, never values
sent by the client (VF-10).
"""

import secrets
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.sessions import Principal
from app.config import get_settings
from app.errors import ApiError
from app.models import Sanction, User, VerificationAttributes
from app.tours.models import Tour, TourMember, UserBlock

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # 31 characters: no 0/O, 1/I/L (spec 12)
ORGANISER_ROLES = ("CREATOR", "CO_ORGANIZER")
OPEN_LIFECYCLES = ("RECRUITING", "CONFIRMED")
LIVE_LIFECYCLES = ("RECRUITING", "CONFIRMED", "ONGOING")
FINAL_LIFECYCLES = ("COMPLETED", "CANCELLED", "ARCHIVED")


def now() -> datetime:
    return datetime.now(UTC)


def dhaka_today(at: datetime | None = None) -> date:
    return (at or now()).astimezone(get_settings().display_tz).date()


def start_instant(day: date) -> datetime:
    """Midnight at the start of ``day`` in Asia/Dhaka, as an aware UTC datetime."""
    return datetime.combine(day, time.min, tzinfo=get_settings().display_tz).astimezone(UTC)


def end_instant(day: date) -> datetime:
    return start_instant(day + timedelta(days=1))


def new_public_id(year: int) -> str:
    return f"T-{year}-" + "".join(secrets.choice(ALPHABET) for _ in range(5))


def new_code() -> str:
    return "ABH-" + "".join(secrets.choice(ALPHABET) for _ in range(6))


def normalise_code(raw: str) -> str:
    value = (raw or "").strip().upper().replace(" ", "")
    if value.startswith("HTTP"):
        value = value.rstrip("/").rsplit("/", 1)[-1]
    if not value.startswith("ABH-") and len(value) == 6:
        value = "ABH-" + value
    return value


@dataclass(frozen=True)
class Viewer:
    user_id: uuid.UUID
    display_name: str
    verified: bool
    gender: str | None
    birth_year: int | None
    is_student: bool
    student_until: date | None
    home_district: str | None
    restricted: bool

    @property
    def adult(self) -> bool:
        return self.birth_year is not None and dhaka_today().year - self.birth_year >= 18

    @property
    def first_name(self) -> str:
        return first_name(self.display_name)


def first_name(display_name: str | None) -> str:
    return (display_name or "").strip().split(" ")[0] or "Traveller"


def tourmate_restricted(session: Session, user_id: uuid.UUID) -> bool:
    moment = now()
    return session.scalar(
        select(Sanction.id).where(
            Sanction.user_id == user_id,
            Sanction.state == "active",
            Sanction.kind.in_(("tourmate_restriction", "suspension")),
            or_(Sanction.ends_at.is_(None), Sanction.ends_at > moment),
        )
    ) is not None


def viewer_for(session: Session, user_id: uuid.UUID) -> Viewer:
    from app.admin.cases import is_verified_member

    user = session.get(User, user_id)
    attributes = session.get(VerificationAttributes, user_id)
    return Viewer(
        user_id=user_id,
        display_name=user.display_name if user else "",
        verified=is_verified_member(session, user_id) and attributes is not None,
        gender=attributes.gender if attributes else None,
        birth_year=attributes.birth_year if attributes else None,
        is_student=bool(attributes and attributes.is_student),
        student_until=attributes.student_until if attributes else None,
        home_district=attributes.home_district if attributes else None,
        restricted=tourmate_restricted(session, user_id),
    )


def feature_on(name: str) -> bool:
    return name in get_settings().enabled_features


def access(session: Session, principal: Principal, feature: str = "tours_core") -> Viewer:
    """The Tours gate: 404 unless the feature is on and the person is a Verified Member aged 18 or over."""
    if not feature_on(feature):
        raise ApiError("NOT_FOUND")
    viewer = viewer_for(session, principal.user.id)
    if not viewer.verified or not viewer.adult:
        raise ApiError("NOT_FOUND")  # AC-01, AC-02
    return viewer


def access_state(session: Session, principal: Principal) -> dict[str, object]:
    """For the landing page: why a member does not see Tours yet (never 404 itself)."""
    if not feature_on("tours_core"):
        return {"access": False, "reason": "FEATURE_OFF"}
    viewer = viewer_for(session, principal.user.id)
    if not viewer.verified:
        return {"access": False, "reason": "NOT_VERIFIED"}
    if not viewer.adult:
        return {"access": False, "reason": "UNDER_18"}
    return {
        "access": True,
        "reason": None,
        "restricted": viewer.restricted,
        "features": sorted(f for f in get_settings().enabled_features if f.startswith("tours_")),
    }


def require_unrestricted(viewer: Viewer) -> None:
    if viewer.restricted:
        raise ApiError("ACCOUNT_RESTRICTED")


def eligible(viewer: Viewer, policy: str, start_date: date) -> bool:
    """Spec 6. Third gender is open to every policy except Women only and Men only (owner, 6 Nov)."""
    if policy == "WOMEN":
        return viewer.gender == "FEMALE"
    if policy == "MEN":
        return viewer.gender == "MALE"
    if policy == "STUDENTS":
        return viewer.is_student and viewer.student_until is not None and viewer.student_until >= start_date
    return True


def blocked_between(session: Session, user_id: uuid.UUID, others: Iterable[uuid.UUID]) -> bool:
    ids = [o for o in others if o != user_id]
    if not ids:
        return False
    return session.scalar(
        select(UserBlock.blocker_id).where(
            or_(
                (UserBlock.blocker_id == user_id) & (UserBlock.blocked_id.in_(ids)),
                (UserBlock.blocked_id == user_id) & (UserBlock.blocker_id.in_(ids)),
            )
        ).limit(1)
    ) is not None


def active_member_ids(session: Session, tour_id: uuid.UUID) -> list[uuid.UUID]:
    return list(session.scalars(select(TourMember.user_id).where(TourMember.tour_id == tour_id, TourMember.state == "ACTIVE")))


def membership(session: Session, tour_id: uuid.UUID, user_id: uuid.UUID) -> TourMember | None:
    return session.scalar(
        select(TourMember).where(TourMember.tour_id == tour_id, TourMember.user_id == user_id, TourMember.state.in_(("ACTIVE", "INACTIVE")))
    )


# Spec 13.2. Staff actions go through Tour Operations, not this table.
PERMISSIONS: dict[str, frozenset[str]] = {
    "tour.edit_basics": frozenset({"CREATOR", "CO_ORGANIZER"}),
    "tour.edit_key_details": frozenset({"CREATOR"}),
    "tour.approve": frozenset({"CREATOR", "CO_ORGANIZER"}),
    "tour.invite": frozenset({"CREATOR", "CO_ORGANIZER"}),
    "tour.remove_member": frozenset({"CREATOR", "CO_ORGANIZER"}),
    "tour.appoint": frozenset({"CREATOR"}),
    "tour.transfer": frozenset({"CREATOR"}),
    "tour.recruitment": frozenset({"CREATOR", "CO_ORGANIZER"}),
    "tour.regenerate_code": frozenset({"CREATOR", "CO_ORGANIZER"}),
    "tour.cancel": frozenset({"CREATOR"}),
    "chat.pin": frozenset({"CREATOR", "CO_ORGANIZER"}),
    "chat.delete_any": frozenset({"CREATOR", "CO_ORGANIZER"}),
    "chat.post": frozenset({"CREATOR", "CO_ORGANIZER", "TOURMATE"}),
    "chat.read": frozenset({"CREATOR", "CO_ORGANIZER", "TOURMATE"}),
    "itinerary.edit": frozenset({"CREATOR", "CO_ORGANIZER"}),
    "itinerary.suggest": frozenset({"TOURMATE"}),
    "expense.add": frozenset({"CREATOR", "CO_ORGANIZER", "TOURMATE"}),
    "safety.meeting_points": frozenset({"CREATOR", "CO_ORGANIZER"}),
    "safety.own": frozenset({"CREATOR", "CO_ORGANIZER", "TOURMATE"}),
    "safety.others": frozenset({"CREATOR", "CO_ORGANIZER"}),
    "safety.checkin": frozenset({"CREATOR", "CO_ORGANIZER"}),
}


def can(role: str | None, action: str) -> bool:
    return role is not None and role in PERMISSIONS.get(action, frozenset())


def require(member: TourMember | None, action: str) -> TourMember:
    if member is None or member.state != "ACTIVE":
        raise ApiError("NOT_FOUND")
    if not can(member.role, action):
        raise ApiError("FORBIDDEN")
    return member


def locked_tour(session: Session, tour_id: uuid.UUID) -> Tour:
    """Every write locks the tour row first: one lock order, so no deadlocks (architecture 6.1)."""
    tour = session.scalar(select(Tour).where(Tour.id == tour_id).with_for_update())
    if tour is None:
        raise ApiError("NOT_FOUND")
    return tour
