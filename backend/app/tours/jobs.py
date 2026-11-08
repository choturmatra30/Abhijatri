"""Scheduled tour transitions (architecture 7). Every job is idempotent; warnings are keyed so each goes once."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.tours import invitations, safety, service
from app.tours.models import Tour

BATCH = 100


def transitions(session: Session, now: datetime) -> int:
    """Deadlines, At Risk warnings and cancel, start, end, archive: the same guarded code the API runs."""
    count = 0
    ids = list(session.scalars(select(Tour.id).where(Tour.lifecycle.in_(("RECRUITING", "CONFIRMED", "ONGOING", "COMPLETED", "CANCELLED"))).limit(1000)))
    for tour_id in ids[:BATCH * 10]:
        tour = session.scalar(select(Tour).where(Tour.id == tour_id).with_for_update(skip_locked=True))
        if tour is not None and service.apply_due(session, tour, now):
            count += 1
    return count


def expire_invitations(session: Session, now: datetime) -> int:
    return invitations.expire_due(session, now)


def safety_purge(session: Session, now: datetime) -> int:
    return safety.purge_due(session, now)


def contact_reminders(session: Session, now: datetime) -> int:
    return safety.missing_contact_reminders(session, now)


def breakglass_notices(session: Session, now: datetime) -> int:
    import app.tours.tour_ops as tour_ops

    return tour_ops.notify_organisers_after_grants(session, now)


JOBS = [
    ("tours.transitions", transitions),
    ("tours.expire_invitations", expire_invitations),
    ("tours.safety_purge", safety_purge),
    ("tours.contact_reminders", contact_reminders),
    ("tours.breakglass_notices", breakglass_notices),
]
