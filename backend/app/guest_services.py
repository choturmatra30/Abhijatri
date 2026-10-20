"""Guest footprint: how many guests come each day, never who (scope owner, 20 Oct 2026).

A guest types a name on the landing page; it stays on the device and is never sent here. Each
browser reports at most one visit per display-time-zone day, and the server stores only a
running number and the time (`guest_visits.id`, `visited_at`). The browser keeps the number of
its first visit to say "Guest #N".
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import Date, cast, func, insert, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.destination_services import today_in_display_tz
from app.models import GuestVisit


def record_guest_visit(session: Session) -> int:
    """Insert one visit and return its running number."""
    return int(session.execute(insert(GuestVisit).returning(GuestVisit.id)).scalar_one())


def guest_visit_stats(
    session: Session, *, days: int = 30, now: datetime | None = None
) -> tuple[int, int, list[tuple[date, int]]]:
    """Return ``(total_visits, visits_today, [(day, visits), ...])`` on display-time-zone days.

    ``daily`` covers the last ``days`` days including today, oldest first, with zero days filled.
    """
    tz = get_settings().display_tz
    today = today_in_display_tz(now)
    first_day = today - timedelta(days=days - 1)
    local_day = cast(func.timezone(tz.key, GuestVisit.visited_at), Date)
    counts = dict(
        session.execute(
            select(local_day, func.count())
            .where(GuestVisit.visited_at >= datetime.combine(first_day, time.min, tzinfo=tz))
            .group_by(local_day)
        ).all()
    )
    daily = [(day, int(counts.get(day, 0))) for day in (first_day + timedelta(n) for n in range(days))]
    total = int(session.scalar(select(func.count()).select_from(GuestVisit)) or 0)
    return total, daily[-1][1], daily
