"""Build, version and describe offline destination packs (R14, PF 18.4, Security 7.4).

A pack is the public content of one published destination: bilingual profile, guide items,
contacts, dated advisories and a bounded snapshot of published reviews. It never carries
researcher or reviewer names, account, receipt or staff data, or signed media links.

Versions:

- ``content_version`` is the SHA-256 of the canonical JSON of the content alone. It does not
  depend on the clock or on ``updated_at`` columns (which are not bumped automatically), so it
  changes exactly when something a reader sees changes, including a review removed by moderation.
- ``pack_version`` counts builds of one destination. A build happens when the content version
  changes, when the newest build is older than ``PACK_REBUILD_AFTER_HOURS`` or when it expired.
- ``sha256`` is the SHA-256 of the exact bytes stored and served.

Packs are built on read, under a per-destination advisory lock, and only the newest build is kept.
"""

import base64
import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import media
from app.auth.validation import public_author_name
from app.config import get_settings
from app.destination_services import (
    _contact_rows,
    _contacts,
    _float,
    _guide_items,
    _guide_rows,
    _provenance,
    _ratings,
    advisory_state,
    today_in_display_tz,
)
from app.guest_tag import display_guest_tag
from app.models import (
    Destination,
    DestinationAdvisory,
    DestinationPackVersion,
    DestinationRatingStats,
    DestinationStatus,
    User,
)
from app.review_lists import published_review_rows
from app.schemas import (
    PackAdvisory,
    PackAdvisoryStateAtGeneration,
    PackContent,
    PackDestination,
    PackDocument,
    PackFreshness,
    PackFreshnessItem,
    PackManifest,
    PackMedia,
    PackReview,
    PackReviewCount,
    PackReviewSnapshot,
)
from app.services import category_averages, revision_category_ratings

PACK_SCHEMA_VERSION = 1
LANGUAGES: list[Literal["bn", "en"]] = ["bn", "en"]
MAX_FRESHNESS_IDS = 20


class PackNotFound(Exception):
    """Unknown or draft destination: answered exactly like any unknown id."""


class PackWithdrawn(Exception):
    """The destination was public and is now archived: devices should delete the pack."""


@dataclass(frozen=True)
class CurrentPack:
    row: DestinationPackVersion
    content: PackContent


def canonical_json(value: Any) -> bytes:
    """Sorted keys, no whitespace, UTF-8 text (Bangla kept as is): one byte string per value."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode(
        "utf-8"
    )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_digest(sha256: str) -> str:
    """The RFC 9530 ``Content-Digest`` value for a SHA-256 given in hex."""
    return "sha-256=:" + base64.b64encode(bytes.fromhex(sha256)).decode("ascii") + ":"


def pack_url(destination_id: uuid.UUID, pack_version: int) -> str:
    return f"/api/v1/destinations/{destination_id}/pack?version={pack_version}"


def advisory_window(today: date, max_age_days: int) -> tuple[date, date]:
    """Advisories in a pack: still valid today, and effective before the pack can expire.

    An advisory that starts within the pack's lifetime is included so an offline device shows it on
    its first day; the device computes the state from the dates.
    """
    return today, today + timedelta(days=max_age_days)


def needs_rebuild(
    latest: DestinationPackVersion | None, content_version: str, now: datetime, *, rebuild_after: timedelta
) -> bool:
    if latest is None:
        return True
    return (
        latest.content_version != content_version
        or latest.schema_version != PACK_SCHEMA_VERSION
        or latest.expires_at <= now
        or now - latest.generated_at >= rebuild_after
    )


def _pack_advisory_rows(session: Session, destination_id: uuid.UUID, today: date) -> Sequence[DestinationAdvisory]:
    valid_from, starts_before = advisory_window(today, get_settings().pack_max_age_days)
    return session.scalars(
        select(DestinationAdvisory)
        .where(
            DestinationAdvisory.destination_id == destination_id,
            DestinationAdvisory.is_published.is_(True),
            DestinationAdvisory.valid_until >= valid_from,
            DestinationAdvisory.effective_on <= starts_before,
        )
        .order_by(
            DestinationAdvisory.severity.desc(),
            DestinationAdvisory.valid_until.asc(),
            DestinationAdvisory.id.asc(),
        )
    ).all()


def _review_snapshot(session: Session, destination_id: uuid.UUID, limit: int) -> PackReviewSnapshot:
    rows = published_review_rows(session, destination_id, limit=limit) if limit else []
    categories = revision_category_ratings(session, [revision.id for _, revision in rows])
    attached = media.published_media_metadata(session, [review.id for review, _ in rows])
    author_ids = {review.author_user_id for review, _ in rows if review.author_user_id}
    authors: dict[uuid.UUID, str | None] = (
        {row.id: row.display_name for row in session.execute(select(User.id, User.display_name).where(User.id.in_(author_ids)))}
        if author_ids
        else {}
    )
    items = [
        PackReview(
            id=review.id,
            author_type="MEMBER" if review.author_user_id else "GUEST",
            guest_tag=display_guest_tag(review.guest_tag),
            author_display_name=public_author_name(authors.get(review.author_user_id))
            if review.author_user_id
            else None,
            overall_rating=review.overall_rating,
            category_ratings=categories[revision.id],
            published_at=review.published_at,
            title=revision.title,
            body=revision.body,
            media=[
                PackMedia(id=item.id, kind=item.kind, alt_text=item.alt_text, caption=item.caption)
                for item in attached.get(review.id, [])
            ],
        )
        for review, revision in rows
        if review.published_at is not None
    ]
    return PackReviewSnapshot(limit=limit, count=len(items), items=items)


def _destination_or_raise(session: Session, destination_id: uuid.UUID) -> Destination:
    destination = session.get(Destination, destination_id)
    if destination is None or destination.status == DestinationStatus.DRAFT:
        raise PackNotFound("destination not found")
    if destination.status != DestinationStatus.PUBLISHED:
        raise PackWithdrawn("destination withdrawn")
    return destination


def build_content(session: Session, destination: Destination, today: date) -> tuple[PackContent, list[DestinationAdvisory]]:
    settings = get_settings()
    community, guest = _ratings(
        destination.id,
        session.get(DestinationRatingStats, destination.id),
        category_averages(session, [destination.id]),
    )
    advisory_rows = list(_pack_advisory_rows(session, destination.id, today))
    content = PackContent(
        schema_version=PACK_SCHEMA_VERSION,
        languages=LANGUAGES,
        stale_after_days=settings.advisory_stale_after_days,
        destination=PackDestination(
            id=destination.id,
            name_bn=destination.name_bn,
            name_en=destination.name_en,
            region_bn=destination.region_bn,
            region_en=destination.region_en,
            summary_bn=destination.summary_bn,
            summary_en=destination.summary_en,
            seasonality_bn=destination.seasonality_bn,
            seasonality_en=destination.seasonality_en,
            restrictions_bn=destination.restrictions_bn,
            restrictions_en=destination.restrictions_en,
            latitude=_float(destination.latitude),
            longitude=_float(destination.longitude),
            content_licence=destination.content_licence,
            content_verified_on=destination.content_verified_on,
            community_rating=community,
            guest_feedback=guest,
        ),
        guide_items=_guide_items(_guide_rows(session, destination.id)),
        advisories=[
            PackAdvisory(
                id=row.id,
                severity=row.severity,
                title_bn=row.title_bn,
                title_en=row.title_en,
                text_bn=row.text_bn,
                text_en=row.text_en,
                effective_on=row.effective_on,
                valid_until=row.valid_until,
                provenance=_provenance(row),
            )
            for row in advisory_rows
        ],
        contacts=_contacts(_contact_rows(session, destination.id)),
        reviews=_review_snapshot(session, destination.id, settings.pack_review_snapshot_limit),
    )
    return content, advisory_rows


def content_version_of(content: PackContent) -> str:
    return sha256_hex(canonical_json(content.model_dump(mode="json")))


def build_document(
    content: PackContent,
    advisory_rows: Sequence[DestinationAdvisory],
    *,
    content_version: str,
    pack_version: int,
    generated_at: datetime,
) -> PackDocument:
    max_age_days = get_settings().pack_max_age_days
    today = today_in_display_tz(generated_at)
    verified = [row.verified_on for row in advisory_rows]
    return PackDocument(
        **content.model_dump(),
        destination_id=content.destination.id,
        pack_version=pack_version,
        content_version=content_version,
        generated_at=generated_at,
        generated_on=today,
        expires_at=generated_at + timedelta(days=max_age_days),
        max_age_seconds=max_age_days * 86400,
        advisories_verified_on=min(verified) if verified else None,
        advisory_states=[
            PackAdvisoryStateAtGeneration(
                id=row.id,
                state=advisory_state(
                    effective_on=row.effective_on,
                    valid_until=row.valid_until,
                    verified_on=row.verified_on,
                    today=today,
                    stale_after_days=content.stale_after_days,
                ),
            )
            for row in advisory_rows
        ],
    )


def _latest(session: Session, destination_id: uuid.UUID) -> DestinationPackVersion | None:
    return session.scalar(
        select(DestinationPackVersion)
        .where(DestinationPackVersion.destination_id == destination_id)
        .order_by(DestinationPackVersion.pack_version.desc())
        .limit(1)
    )


def ensure_current_pack(session: Session, destination_id: uuid.UUID, *, now: datetime | None = None) -> CurrentPack:
    """Return the newest pack of a published destination, building a new version when needed."""
    settings = get_settings()
    now = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    rebuild_after = timedelta(hours=settings.pack_rebuild_after_hours)
    # Every path ends its transaction here, so the pooled connection goes back to the pool at
    # once instead of idling in a transaction until the request's dependency teardown runs. Under
    # load that idle wait exhausted the pool (load check, 6 Nov 2026).
    try:
        destination = _destination_or_raise(session, destination_id)
        content, advisory_rows = build_content(session, destination, today_in_display_tz(now))
        content_version = content_version_of(content)
        latest = _latest(session, destination_id)
        if not needs_rebuild(latest, content_version, now, rebuild_after=rebuild_after):
            session.commit()
            assert latest is not None  # narrowed by needs_rebuild
            return CurrentPack(row=latest, content=content)
    except Exception:
        session.rollback()
        raise

    try:
        # One builder per destination; a concurrent request waits and then reuses the new build.
        session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"pack:{destination_id}", 0))))
        latest = _latest(session, destination_id)
        if needs_rebuild(latest, content_version, now, rebuild_after=rebuild_after):
            pack_version = (latest.pack_version if latest else 0) + 1
            document = build_document(
                content,
                advisory_rows,
                content_version=content_version,
                pack_version=pack_version,
                generated_at=now,
            )
            body = canonical_json(document.model_dump(mode="json"))
            latest = DestinationPackVersion(
                destination_id=destination_id,
                pack_version=pack_version,
                content_version=content_version,
                sha256=sha256_hex(body),
                size_bytes=len(body),
                schema_version=PACK_SCHEMA_VERSION,
                generated_at=document.generated_at,
                expires_at=document.expires_at,
                body=body,
            )
            session.add(latest)
            session.flush()
            session.execute(
                delete(DestinationPackVersion).where(
                    DestinationPackVersion.destination_id == destination_id,
                    DestinationPackVersion.pack_version < pack_version,
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    assert latest is not None
    return CurrentPack(row=latest, content=content)


def manifest_of(current: CurrentPack) -> PackManifest:
    row, content = current.row, current.content
    verified = [advisory.provenance.verified_on for advisory in content.advisories]
    return PackManifest(
        schema_version=row.schema_version,
        destination_id=row.destination_id,
        pack_version=row.pack_version,
        content_version=row.content_version,
        sha256=row.sha256,
        size_bytes=row.size_bytes,
        generated_at=row.generated_at.astimezone(UTC),
        expires_at=row.expires_at.astimezone(UTC),
        max_age_seconds=int((row.expires_at - row.generated_at).total_seconds()),
        stale_after_days=content.stale_after_days,
        advisories_verified_on=min(verified) if verified else None,
        languages=content.languages,
        review_snapshot=PackReviewCount(count=content.reviews.count, limit=content.reviews.limit),
        pack_url=pack_url(row.destination_id, row.pack_version),
    )


def freshness(session: Session, destination_ids: Sequence[uuid.UUID], *, now: datetime | None = None) -> PackFreshness:
    """The reconnect check for every pack on a device, in the order the ids were sent."""
    items = []
    for destination_id in destination_ids:
        try:
            row = ensure_current_pack(session, destination_id, now=now).row
        except PackNotFound:
            items.append(PackFreshnessItem(destination_id=destination_id, status="NOT_FOUND"))
            continue
        except PackWithdrawn:
            items.append(PackFreshnessItem(destination_id=destination_id, status="WITHDRAWN"))
            continue
        items.append(
            PackFreshnessItem(
                destination_id=destination_id,
                status="AVAILABLE",
                pack_version=row.pack_version,
                content_version=row.content_version,
                sha256=row.sha256,
                size_bytes=row.size_bytes,
                generated_at=row.generated_at.astimezone(UTC),
                expires_at=row.expires_at.astimezone(UTC),
                pack_url=pack_url(destination_id, row.pack_version),
            )
        )
    return PackFreshness(items=items)
