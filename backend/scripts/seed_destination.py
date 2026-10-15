"""Seed one published destination so the guest-review smoke test has a target.

Usage: uv run python scripts/seed_destination.py [--force]
Refuses to run when APP_ENV is production unless --force is given.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import Destination, DestinationRatingStats, DestinationStatus

    if get_settings().is_production and "--force" not in sys.argv:
        raise SystemExit("Refusing to seed a production database without --force")
    with SessionLocal() as session:
        destination = Destination(
            status=DestinationStatus.PUBLISHED, name_bn="কক্সবাজার", name_en="Cox's Bazar"
        )
        session.add(destination)
        session.flush()
        session.add(DestinationRatingStats(destination_id=destination.id))
        session.commit()
        print(f"destination_id={destination.id}")


if __name__ == "__main__":
    main()
