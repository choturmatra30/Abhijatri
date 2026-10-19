"""Seed the five semester destinations with sourced bilingual content.

Usage: uv run python scripts/seed_destinations.py [--force]

Content lives in ``destination_seed_content.py``. The script is idempotent:

- a destination is matched by its English name, so the record made by ``seed_destination.py``
  keeps its id (and any reviews that point at it); a new destination gets a stable UUIDv5;
- profile fields are overwritten, guide items, advisories and contacts are replaced;
- the rating aggregate row is created if missing and never reset.

Refuses to run when APP_ENV is production unless --force is given.
"""

import sys
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

NAMESPACE = uuid.UUID("5b1f0c7e-6f0a-4f6e-9a57-4a2c1d0b7e31")
PROVENANCE_FIELDS = (
    "source_type",
    "source_ref",
    "publisher",
    "effective_on",
    "licence",
)


def stable_id(*parts: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, ":".join(("abhijatri", *parts)))


def _provenance(item: dict, verified_on, researcher: str) -> dict:
    return {
        **{field: item[field] for field in PROVENANCE_FIELDS},
        "verified_on": verified_on,
        "next_review_on": item.get("next_review_on"),
        "researcher": researcher,
        "reviewer": None,  # R01 content review by the content owner is still outstanding
    }


def main() -> None:
    from destination_seed_content import DESTINATIONS, RESEARCHER, TEAM_TEXT_LICENCE, VERIFIED_ON
    from sqlalchemy import delete, select

    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import (
        AdvisorySeverity,
        ContactKind,
        Destination,
        DestinationAdvisory,
        DestinationContact,
        DestinationGuideItem,
        DestinationRatingStats,
        DestinationStatus,
        GuideCategory,
        SourceType,
        utcnow,
    )

    if get_settings().is_production and "--force" not in sys.argv:
        raise SystemExit("Refusing to seed a production database without --force")

    with SessionLocal() as session:
        for content in DESTINATIONS:
            key = content["key"]
            destination = session.scalar(select(Destination).where(Destination.name_en == content["name_en"]))
            if destination is None:
                destination = Destination(id=stable_id("destination", key))
                session.add(destination)
            destination.status = DestinationStatus.PUBLISHED
            for field in (
                "name_bn",
                "name_en",
                "region_bn",
                "region_en",
                "summary_bn",
                "summary_en",
                "seasonality_bn",
                "seasonality_en",
                "restrictions_bn",
                "restrictions_en",
            ):
                setattr(destination, field, content[field])
            destination.latitude = Decimal(content["latitude"])
            destination.longitude = Decimal(content["longitude"])
            destination.content_licence = TEAM_TEXT_LICENCE
            destination.content_verified_on = VERIFIED_ON
            destination.updated_at = utcnow()
            session.flush()

            if session.get(DestinationRatingStats, destination.id) is None:
                session.add(DestinationRatingStats(destination_id=destination.id))

            for table in (DestinationGuideItem, DestinationAdvisory, DestinationContact):
                session.execute(delete(table).where(table.destination_id == destination.id))

            for item in content["guide_items"]:
                session.add(
                    DestinationGuideItem(
                        id=stable_id("guide", key, item["key"]),
                        destination_id=destination.id,
                        category=GuideCategory(item["category"]),
                        title_bn=item["title_bn"],
                        title_en=item["title_en"],
                        body_bn=item["body_bn"],
                        body_en=item["body_en"],
                        sort_order=item["sort_order"],
                        is_published=True,
                        **_provenance(item, VERIFIED_ON, RESEARCHER)
                        | {"source_type": SourceType(item["source_type"])},
                    )
                )
            for item in content["advisories"]:
                session.add(
                    DestinationAdvisory(
                        id=stable_id("advisory", key, item["key"]),
                        destination_id=destination.id,
                        severity=AdvisorySeverity(item["severity"]),
                        title_bn=item["title_bn"],
                        title_en=item["title_en"],
                        text_bn=item["text_bn"],
                        text_en=item["text_en"],
                        valid_until=item["valid_until"],
                        is_published=True,
                        **_provenance(item, VERIFIED_ON, RESEARCHER)
                        | {"source_type": SourceType(item["source_type"])},
                    )
                )
            for item in content["contacts"]:
                session.add(
                    DestinationContact(
                        id=stable_id("contact", key, item["key"]),
                        destination_id=destination.id,
                        kind=ContactKind(item["kind"]),
                        name_bn=item["name_bn"],
                        name_en=item["name_en"],
                        phone=item["phone"],
                        is_published=True,
                        **_provenance(item, VERIFIED_ON, RESEARCHER)
                        | {"source_type": SourceType(item["source_type"])},
                    )
                )
            print(f"{key}: destination_id={destination.id}")
        session.commit()


if __name__ == "__main__":
    main()
