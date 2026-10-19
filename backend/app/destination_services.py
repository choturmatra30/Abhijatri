"""Read services for published destinations, advisories and contacts (R02).

Calendar rules (advisory validity, staleness) use the Asia/Dhaka date, never the UTC date
(Platform Foundation 11.2). Callers may inject ``today`` so tests are deterministic.
"""

import base64
import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Destination,
    DestinationAdvisory,
    DestinationContact,
    DestinationGuideItem,
    DestinationRatingStats,
    DestinationStatus,
)
from app.schemas import (
    Advisory,
    AdvisoryState,
    CommunityRatingSummary,
    Contact,
    DestinationList,
    DestinationProfile,
    DestinationSummary,
    GuestFeedbackSummary,
    GuideItem,
    Provenance,
)


class DestinationNotFound(Exception):
    pass


class InvalidCursor(ValueError):
    pass


def today_in_display_tz(now: datetime | None = None) -> date:
    zone = get_settings().display_tz
    moment = now.astimezone(zone) if now is not None else datetime.now(zone)
    return moment.date()


def advisory_state(
    *, effective_on: date, valid_until: date, verified_on: date, today: date, stale_after_days: int
) -> AdvisoryState:
    """Classify an advisory. Expired always wins over stale so it is never shown as current."""
    if today < effective_on:
        return "NOT_YET_EFFECTIVE"
    if today > valid_until:
        return "EXPIRED"
    if (today - verified_on).days > stale_after_days:
        return "STALE"
    return "CURRENT"


def encode_destination_cursor(name_en: str, destination_id: uuid.UUID) -> str:
    raw = f"{name_en}|{destination_id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_destination_cursor(cursor: str) -> tuple[str, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        name_en, destination_id = base64.urlsafe_b64decode(padded).decode("utf-8").rsplit("|", 1)
        return name_en, uuid.UUID(destination_id)
    except (ValueError, UnicodeDecodeError) as error:
        raise InvalidCursor("invalid cursor") from error


def _float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _provenance(row: DestinationGuideItem | DestinationAdvisory | DestinationContact) -> Provenance:
    return Provenance.model_validate(row)


def _ratings(stats: DestinationRatingStats | None) -> tuple[CommunityRatingSummary, GuestFeedbackSummary]:
    if stats is None:
        return CommunityRatingSummary(average=None, count=0), GuestFeedbackSummary(average=None, count=0)
    community = CommunityRatingSummary(
        average=stats.community_rating_sum / stats.community_rating_count
        if stats.community_rating_count
        else None,
        count=stats.community_rating_count,
    )
    guest = GuestFeedbackSummary(
        average=stats.guest_rating_sum / stats.guest_rating_count if stats.guest_rating_count else None,
        count=stats.guest_rating_count,
    )
    return community, guest


def _published_destination(session: Session, destination_id: uuid.UUID) -> Destination:
    destination = session.scalar(
        select(Destination).where(
            Destination.id == destination_id, Destination.status == DestinationStatus.PUBLISHED
        )
    )
    if destination is None:
        raise DestinationNotFound("destination not found")
    return destination


def _advisory_rows(
    session: Session, destination_id: uuid.UUID, *, today: date, include_expired: bool
) -> Sequence[DestinationAdvisory]:
    statement = (
        select(DestinationAdvisory)
        .where(
            DestinationAdvisory.destination_id == destination_id,
            DestinationAdvisory.is_published.is_(True),
            DestinationAdvisory.effective_on <= today,
        )
        .order_by(DestinationAdvisory.severity.desc(), DestinationAdvisory.valid_until.asc(), DestinationAdvisory.id.asc())
    )
    if not include_expired:
        statement = statement.where(DestinationAdvisory.valid_until >= today)
    return session.scalars(statement).all()


def _advisories(rows: Sequence[DestinationAdvisory], today: date) -> list[Advisory]:
    stale_after = get_settings().advisory_stale_after_days
    return [
        Advisory(
            id=row.id,
            severity=row.severity,
            title_bn=row.title_bn,
            title_en=row.title_en,
            text_bn=row.text_bn,
            text_en=row.text_en,
            effective_on=row.effective_on,
            valid_until=row.valid_until,
            state=advisory_state(
                effective_on=row.effective_on,
                valid_until=row.valid_until,
                verified_on=row.verified_on,
                today=today,
                stale_after_days=stale_after,
            ),
            provenance=_provenance(row),
        )
        for row in rows
    ]


def _contacts(rows: Sequence[DestinationContact]) -> list[Contact]:
    return [
        Contact(
            id=row.id,
            kind=row.kind,
            name_bn=row.name_bn,
            name_en=row.name_en,
            phone=row.phone,
            address_bn=row.address_bn,
            address_en=row.address_en,
            latitude=_float(row.latitude),
            longitude=_float(row.longitude),
            provenance=_provenance(row),
        )
        for row in rows
    ]


def _contact_rows(session: Session, destination_id: uuid.UUID) -> Sequence[DestinationContact]:
    return session.scalars(
        select(DestinationContact)
        .where(
            DestinationContact.destination_id == destination_id,
            DestinationContact.is_published.is_(True),
        )
        .order_by(
            DestinationContact.kind.asc(), DestinationContact.name_en.asc(), DestinationContact.id.asc()
        )
    ).all()


def list_published_destinations(
    session: Session, *, limit: int, after: str | None, today: date | None = None
) -> DestinationList:
    today = today or today_in_display_tz()
    statement = (
        select(Destination)
        .where(Destination.status == DestinationStatus.PUBLISHED)
        .order_by(Destination.name_en.asc(), Destination.id.asc())
        .limit(limit + 1)
    )
    if after:
        name_en, destination_id = decode_destination_cursor(after)
        statement = statement.where(
            tuple_(Destination.name_en, Destination.id) > tuple_(name_en, destination_id)
        )
    destinations = list(session.scalars(statement).all())
    has_more = len(destinations) > limit
    destinations = destinations[:limit]
    ids = [destination.id for destination in destinations]

    stats = {
        row.destination_id: row
        for row in session.scalars(
            select(DestinationRatingStats).where(DestinationRatingStats.destination_id.in_(ids))
        )
    }
    active_counts = {
        destination_id: count
        for destination_id, count in session.execute(
            select(DestinationAdvisory.destination_id, func.count())
            .where(
                DestinationAdvisory.destination_id.in_(ids),
                DestinationAdvisory.is_published.is_(True),
                DestinationAdvisory.effective_on <= today,
                DestinationAdvisory.valid_until >= today,
            )
            .group_by(DestinationAdvisory.destination_id)
        )
    }
    items = []
    for destination in destinations:
        community, guest = _ratings(stats.get(destination.id))
        items.append(
            DestinationSummary(
                id=destination.id,
                name_bn=destination.name_bn,
                name_en=destination.name_en,
                region_bn=destination.region_bn,
                region_en=destination.region_en,
                summary_bn=destination.summary_bn,
                summary_en=destination.summary_en,
                latitude=_float(destination.latitude),
                longitude=_float(destination.longitude),
                community_rating=community,
                guest_feedback=guest,
                active_advisory_count=active_counts.get(destination.id, 0),
                last_updated=destination.updated_at,
            )
        )
    next_cursor = (
        encode_destination_cursor(destinations[-1].name_en, destinations[-1].id)
        if has_more and destinations
        else None
    )
    return DestinationList(items=items, next_cursor=next_cursor)


def get_destination_profile(
    session: Session,
    destination_id: uuid.UUID,
    *,
    include_expired: bool = False,
    today: date | None = None,
) -> DestinationProfile:
    today = today or today_in_display_tz()
    destination = _published_destination(session, destination_id)
    guide_rows = session.scalars(
        select(DestinationGuideItem)
        .where(
            DestinationGuideItem.destination_id == destination_id,
            DestinationGuideItem.is_published.is_(True),
        )
        .order_by(
            DestinationGuideItem.category.asc(),
            DestinationGuideItem.sort_order.asc(),
            DestinationGuideItem.title_en.asc(),
            DestinationGuideItem.id.asc(),
        )
    ).all()
    advisory_rows = _advisory_rows(session, destination_id, today=today, include_expired=include_expired)
    contact_rows = _contact_rows(session, destination_id)
    community, guest = _ratings(session.get(DestinationRatingStats, destination_id))
    last_updated = max(
        [
            destination.updated_at,
            *(row.updated_at for row in guide_rows),
            *(row.updated_at for row in advisory_rows),
            *(row.updated_at for row in contact_rows),
        ]
    )
    return DestinationProfile(
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
        community_rating=community,
        guest_feedback=guest,
        guide_items=[
            GuideItem(
                id=row.id,
                category=row.category,
                title_bn=row.title_bn,
                title_en=row.title_en,
                body_bn=row.body_bn,
                body_en=row.body_en,
                sort_order=row.sort_order,
                provenance=_provenance(row),
            )
            for row in guide_rows
        ],
        advisories=_advisories(advisory_rows, today),
        contacts=_contacts(contact_rows),
        content_licence=destination.content_licence,
        content_verified_on=destination.content_verified_on,
        as_of=today,
        stale_after_days=get_settings().advisory_stale_after_days,
        last_updated=last_updated,
    )
