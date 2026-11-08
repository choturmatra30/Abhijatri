"""Scheduled verification transitions (sign-up form 5, 9.5, 13.6).

- A draft not submitted within 14 days, or a clarification not answered within 7 days, becomes ``expired``.
- Renewal reminders 30 and 7 days before the verification is due, then a "lapsed" notice when it passes.
  The badge itself disappears on its own: ``is_verified_member`` only counts verifications not yet due.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin import audit, tasks
from app.models import Verification, VerificationCase
from app.notify import events

BATCH = 200


def expire_drafts(session: Session, now: datetime) -> int:
    rows = session.scalars(
        select(VerificationCase)
        .where(VerificationCase.state == "draft", VerificationCase.draft_expires_at <= now)
        .limit(BATCH)
        .with_for_update(skip_locked=True)
    )
    count = 0
    for case in rows:
        case.state, case.version, case.updated_at, case.purge_after = "expired", case.version + 1, now, now
        audit.record(session, actor=None, action="verification.expired", target_type="verification_case", target_id=case.id, metadata={"from": "draft"})
        count += 1
    return count


def expire_clarifications(session: Session, now: datetime) -> int:
    rows = session.scalars(
        select(VerificationCase)
        .where(VerificationCase.state == "needs_clarification", VerificationCase.clarification_due_at <= now)
        .limit(BATCH)
        .with_for_update(skip_locked=True)
    )
    count = 0
    for case in rows:
        case.state, case.version, case.updated_at = "expired", case.version + 1, now
        case.purge_after = now + timedelta(days=30)
        tasks.cancel_open_tasks(session, case.id)
        audit.record(session, actor=None, action="verification.expired", target_type="verification_case", target_id=case.id, metadata={"from": "needs_clarification"})
        count += 1
    return count


def renewal_reminders(session: Session, now: datetime) -> int:
    sent = 0
    due = session.scalars(
        select(Verification)
        .where(
            Verification.verification_type == "VERIFIED_MEMBER", Verification.status == "APPROVED", Verification.revoked_at.is_(None),
            Verification.expires_at.is_not(None), Verification.expires_at > now, Verification.expires_at <= now + timedelta(days=30),
        )
        .limit(BATCH)
    )
    for verification in due:
        assert verification.expires_at is not None
        days = 7 if verification.expires_at <= now + timedelta(days=7) else 30
        if events.emit(
            session, "verification.renewal_due", verification.id, {"user_id": str(verification.user_id), "count": str(days)},
            aggregate_type="verification", dedupe_key=f"verification.renewal_due:{verification.id}:{days}",
        ):
            sent += 1
    lapsed = session.scalars(
        select(Verification)
        .where(
            Verification.verification_type == "VERIFIED_MEMBER", Verification.status == "APPROVED", Verification.revoked_at.is_(None),
            Verification.expires_at.is_not(None), Verification.expires_at <= now, Verification.expires_at > now - timedelta(days=60),
        )
        .limit(BATCH)
    )
    for verification in lapsed:
        if events.emit(
            session, "verification.lapsed", verification.id, {"user_id": str(verification.user_id)},
            aggregate_type="verification", dedupe_key=f"verification.lapsed:{verification.id}",
        ):
            sent += 1
    return sent


JOBS = [
    ("verification.expire_drafts", expire_drafts),
    ("verification.expire_clarifications", expire_clarifications),
    ("verification.renewal_reminders", renewal_reminders),
]
