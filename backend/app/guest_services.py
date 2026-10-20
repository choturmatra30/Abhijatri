"""Anonymous guest counter behind the landing-page welcome (Review.md 3.2 step 1).

The guest types a name on the landing page; it stays on the device and is never sent here.
The server only gives each guest device a stable number for "Welcome, <name> · Guest #N",
keyed by a digest of the device's Guest scope secret under its own context label.
"""

from datetime import datetime, time

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import crypto
from app.config import get_settings
from app.destination_services import today_in_display_tz
from app.models import GuestVisit
from app.services import now_utc


def register_guest_visit(session: Session, guest_scope_secret: str) -> tuple[int, int]:
    """Return ``(guest_number, total_guests)``. The same device always gets the same number."""
    moment = now_utc()
    digests = crypto.candidate_digests(crypto.GUEST_VISIT_LABEL, guest_scope_secret)
    existing = session.scalar(
        select(GuestVisit).where(GuestVisit.scope_hash.in_([value for _, value in digests]))
    )
    if existing is not None:
        existing.last_seen_at = moment
        number = existing.guest_number
    else:
        key_id, scope_hash = digests[0]  # current key first
        # A simultaneous first visit from the same device lands on the conflict branch and
        # gets the number the other request created.
        number = session.execute(
            insert(GuestVisit)
            .values(scope_hash=scope_hash, key_id=key_id, first_seen_at=moment, last_seen_at=moment)
            .on_conflict_do_update(
                index_elements=[GuestVisit.scope_hash], set_={"last_seen_at": moment}
            )
            .returning(GuestVisit.guest_number)
        ).scalar_one()
    total = int(session.scalar(select(func.count()).select_from(GuestVisit)) or 0)
    return int(number), total


def guest_visit_stats(session: Session, *, now: datetime | None = None) -> tuple[int, int]:
    """Return ``(total_guests, guests_today)``; "today" is the display-time-zone date (PF 11.2)."""
    tz = get_settings().display_tz
    start_of_day = datetime.combine(today_in_display_tz(now), time.min, tzinfo=tz)
    total = int(session.scalar(select(func.count()).select_from(GuestVisit)) or 0)
    today = int(
        session.scalar(
            select(func.count())
            .select_from(GuestVisit)
            .where(GuestVisit.first_seen_at >= start_of_day)
        )
        or 0
    )
    return total, today
