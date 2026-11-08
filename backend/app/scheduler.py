"""Time-based transitions (architecture 7): one loop, every minute, a single active instance.

Each tick runs in its own transaction holding ``pg_try_advisory_xact_lock``: a transaction-scoped lock, so
it also works through the Supabase transaction pooler (port 6543), where session advisory locks do not. A
second API instance simply finds the lock taken and skips the tick. Every job is idempotent and keyed (outbox
``dedupe_key``), so a tick that runs twice sends nothing twice. Jobs pick due rows in small batches with
``FOR UPDATE SKIP LOCKED`` and use the same guarded transitions as the API.

Tour reads also apply overdue transitions on the spot (``app.tours.service.settle``), so a missed tick is
never visible to a user.
"""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings

logger = logging.getLogger(__name__)

LOCK_KEY = 7_311_302_026  # any constant shared by every instance
Job = Callable[[Session, datetime], int]


def jobs() -> list[tuple[str, Job]]:
    from app.tours import jobs as tour_jobs
    from app.verification import jobs as verification_jobs

    return [*verification_jobs.JOBS, *tour_jobs.JOBS]


def run_once(sessions: Callable[[], Session], now: datetime | None = None) -> dict[str, int]:
    """One tick. Returns rows changed per job (tests call this directly)."""
    moment = now or datetime.now(UTC)
    results: dict[str, int] = {}
    with sessions() as session:
        if not session.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": LOCK_KEY}).scalar():
            session.rollback()
            return results
        for name, job in jobs():
            try:
                with session.begin_nested():
                    results[name] = job(session, moment)
            except Exception:  # one failing job must not stop the others
                logger.exception("scheduled job %s failed", name)
                results[name] = -1
        session.commit()
    return results


class Scheduler:
    def __init__(self, sessions: Callable[[], Session]) -> None:
        self._sessions = sessions
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._failures = 0

    def start(self) -> None:
        if not get_settings().scheduler_enabled:
            return
        self._thread = threading.Thread(target=self._loop, name="scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        interval = get_settings().scheduler_interval_seconds
        while not self._stop.wait(interval):
            try:
                run_once(self._sessions)
                self._failures = 0
            except Exception:
                self._failures += 1
                level = logging.ERROR if self._failures >= 3 else logging.WARNING
                logger.log(level, "scheduler tick failed (%s in a row)", self._failures, exc_info=True)
