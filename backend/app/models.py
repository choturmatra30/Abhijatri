from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class DestinationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class ReviewStatus(str, enum.Enum):
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    PUBLISHED = "PUBLISHED"
    HIDDEN = "HIDDEN"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    DELETED = "DELETED"


class RatingEligibility(str, enum.Enum):
    NOT_EVALUATED = "NOT_EVALUATED"
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE_GUEST = "INELIGIBLE_GUEST"
    INELIGIBLE_UNVERIFIED = "INELIGIBLE_UNVERIFIED"
    INELIGIBLE_DUPLICATE = "INELIGIBLE_DUPLICATE"
    INELIGIBLE_CONFLICT = "INELIGIBLE_CONFLICT"
    INELIGIBLE_REPORTED = "INELIGIBLE_REPORTED"
    INELIGIBLE_REMOVED = "INELIGIBLE_REMOVED"


class RevisionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    TOMBSTONED = "TOMBSTONED"


class ReviewLanguage(str, enum.Enum):
    BN = "BN"
    EN = "EN"
    MIXED = "MIXED"


class TravellerType(str, enum.Enum):
    SOLO = "SOLO"
    STUDENT = "STUDENT"
    COUPLE = "COUPLE"
    FAMILY = "FAMILY"
    GROUP = "GROUP"


class ComfortTier(str, enum.Enum):
    ECONOMY = "ECONOMY"
    STANDARD = "STANDARD"
    PREMIUM = "PREMIUM"


class ReviewCategory(str, enum.Enum):
    """Review.md 3.1 and amendment A2: the seven frozen rating categories, in display order."""

    CLEANLINESS = "CLEANLINESS"
    ACCESSIBILITY = "ACCESSIBILITY"
    HOSPITALITY = "HOSPITALITY"
    FOOD = "FOOD"
    TRANSPORT = "TRANSPORT"
    SAFETY_PERCEPTION = "SAFETY_PERCEPTION"
    VALUE = "VALUE"


class RatingAudience(str, enum.Enum):
    """Which aggregate a counted rating belongs to (Review.md 6.1, 6.2); never merged."""

    GUEST = "GUEST"
    COMMUNITY = "COMMUNITY"


class ModerationDecision(str, enum.Enum):
    PUBLISH = "PUBLISH"
    REJECT = "REJECT"
    HIDE = "HIDE"
    RESTORE = "RESTORE"
    SET_CONFLICT = "SET_CONFLICT"
    CLEAR_CONFLICT = "CLEAR_CONFLICT"


class SourceType(str, enum.Enum):
    OFFICIAL = "OFFICIAL"
    TEAM_RESEARCH = "TEAM_RESEARCH"
    OPEN_LICENCE = "OPEN_LICENCE"
    VENDOR_LICENSED = "VENDOR_LICENSED"
    OTHER = "OTHER"


class GuideCategory(str, enum.Enum):
    ATTRACTION = "ATTRACTION"
    ACCOMMODATION = "ACCOMMODATION"
    FOOD = "FOOD"
    TRANSPORT = "TRANSPORT"
    LOCAL_PRACTICE = "LOCAL_PRACTICE"


class AdvisorySeverity(str, enum.Enum):
    INFO = "INFO"
    CAUTION = "CAUTION"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ContactKind(str, enum.Enum):
    POLICE = "POLICE"
    TOURIST_POLICE = "TOURIST_POLICE"
    AMBULANCE = "AMBULANCE"
    FIRE = "FIRE"
    HOSPITAL = "HOSPITAL"
    COAST_GUARD = "COAST_GUARD"
    FOREST_OFFICE = "FOREST_OFFICE"
    LOCAL_GUIDE = "LOCAL_GUIDE"
    OTHER = "OTHER"


class ProvenanceMixin:
    """Source, date and licence metadata required on every maintained record (PF 17)."""

    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType, name="source_type"), nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[str] = mapped_column(String(160), nullable=False)
    effective_on: Mapped[date] = mapped_column(Date, nullable=False)
    verified_on: Mapped[date] = mapped_column(Date, nullable=False)
    next_review_on: Mapped[date | None] = mapped_column(Date)
    licence: Mapped[str] = mapped_column(String(160), nullable=False)
    researcher: Mapped[str] = mapped_column(String(120), nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String(120))


class Destination(Base):
    __tablename__ = "destinations"
    __table_args__ = (
        CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_destination_latitude_range"
        ),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_destination_longitude_range"
        ),
        CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="ck_destination_coordinates_pair"),
        Index(
            "ix_destinations_published_name",
            "name_en",
            "id",
            postgresql_where=text("status = 'PUBLISHED'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[DestinationStatus] = mapped_column(
        Enum(DestinationStatus, name="destination_status"),
        nullable=False,
        default=DestinationStatus.DRAFT,
    )
    name_bn: Mapped[str] = mapped_column(String(160), nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    region_bn: Mapped[str | None] = mapped_column(String(160))
    region_en: Mapped[str | None] = mapped_column(String(160))
    summary_bn: Mapped[str | None] = mapped_column(Text)
    summary_en: Mapped[str | None] = mapped_column(Text)
    seasonality_bn: Mapped[str | None] = mapped_column(Text)
    seasonality_en: Mapped[str | None] = mapped_column(Text)
    restrictions_bn: Mapped[str | None] = mapped_column(Text)
    restrictions_en: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    content_licence: Mapped[str | None] = mapped_column(String(160))
    content_verified_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class DestinationGuideItem(ProvenanceMixin, Base):
    __tablename__ = "destination_guide_items"
    __table_args__ = (
        Index("ix_guide_items_destination_category", "destination_id", "category", "sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    destination_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[GuideCategory] = mapped_column(Enum(GuideCategory, name="guide_category"), nullable=False)
    title_bn: Mapped[str] = mapped_column(String(160), nullable=False)
    title_en: Mapped[str] = mapped_column(String(160), nullable=False)
    body_bn: Mapped[str] = mapped_column(Text, nullable=False)
    body_en: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class DestinationAdvisory(ProvenanceMixin, Base):
    __tablename__ = "destination_advisories"
    __table_args__ = (
        CheckConstraint("valid_until >= effective_on", name="ck_advisory_validity_window"),
        Index("ix_advisories_destination_valid_until", "destination_id", "valid_until"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    destination_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), nullable=False
    )
    severity: Mapped[AdvisorySeverity] = mapped_column(
        Enum(AdvisorySeverity, name="advisory_severity"), nullable=False
    )
    title_bn: Mapped[str] = mapped_column(String(160), nullable=False)
    title_en: Mapped[str] = mapped_column(String(160), nullable=False)
    text_bn: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str] = mapped_column(Text, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class DestinationContact(ProvenanceMixin, Base):
    __tablename__ = "destination_contacts"
    __table_args__ = (
        CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_contact_latitude_range"
        ),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_contact_longitude_range"
        ),
        CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="ck_contact_coordinates_pair"),
        CheckConstraint(r"phone ~ '^\+?[0-9][0-9 -]{2,30}$'", name="ck_contact_phone_format"),
        Index("ix_contacts_destination_kind", "destination_id", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    destination_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ContactKind] = mapped_column(Enum(ContactKind, name="contact_kind"), nullable=False)
    name_bn: Mapped[str] = mapped_column(String(160), nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    address_bn: Mapped[str | None] = mapped_column(String(300))
    address_en: Mapped[str | None] = mapped_column(String(300))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_team_account: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    # Member visit days (Guest-Identity-and-Visits 4.3): set by GET /auth/session once R04 exists.
    first_visit_on: Mapped[date | None] = mapped_column(Date)
    last_visit_on: Mapped[date | None] = mapped_column(Date)


class PlatformRole(Base):
    __tablename__ = "platform_roles"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)


class UserPlatformRole(Base):
    __tablename__ = "user_platform_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_platform_role"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("platform_roles.id", ondelete="RESTRICT"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    verification_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    method: Mapped[str] = mapped_column(String(60), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(String(240))


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("overall_rating BETWEEN 1 AND 5", name="ck_review_rating_range"),
        CheckConstraint(
            "counted_rating IS NULL OR counted_rating BETWEEN 1 AND 5",
            name="ck_review_counted_rating_range",
        ),
        CheckConstraint(
            "(author_user_id IS NOT NULL AND guest_display_name IS NULL AND guest_scope_hash IS NULL) OR "
            "(author_user_id IS NULL AND guest_display_name IS NOT NULL AND guest_scope_hash IS NOT NULL)",
            name="ck_review_author_shape",
        ),
        CheckConstraint(
            "(guest_scope_hash IS NULL) = (guest_scope_key_id IS NULL)",
            name="ck_review_scope_key_pair",
        ),
        CheckConstraint(
            "guest_tag IS NULL OR (author_user_id IS NULL AND guest_tag ~ '^[0-9A-HJKMNP-TV-Z]{10}$')",
            name="ck_review_guest_tag",
        ),
        Index(
            "uq_reviews_member_draft",
            "author_user_id",
            "client_draft_id",
            unique=True,
            postgresql_where=text("author_user_id IS NOT NULL"),
        ),
        Index(
            "uq_reviews_guest_draft",
            "guest_scope_hash",
            "client_draft_id",
            unique=True,
            postgresql_where=text("author_user_id IS NULL"),
        ),
        Index(
            "uq_reviews_member_active_visit",
            "author_user_id",
            "destination_id",
            "visit_month",
            unique=True,
            postgresql_where=text(
                "author_user_id IS NOT NULL AND duplicate_override = false AND "
                "status IN ('PENDING', 'UNDER_REVIEW', 'CHANGES_REQUESTED', 'PUBLISHED', 'HIDDEN')"
            ),
        ),
        Index(
            "ix_reviews_published_feed",
            "destination_id",
            text("published_at DESC"),
            text("id DESC"),
            postgresql_where=text("status = 'PUBLISHED'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    destination_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=False
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    guest_display_name: Mapped[str | None] = mapped_column(String(80))
    guest_scope_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    guest_scope_key_id: Mapped[str | None] = mapped_column(String(16))
    # Public pseudonym derived from the scope secret (Guest-Identity-and-Visits 3.1), no dash.
    guest_tag: Mapped[str | None] = mapped_column(CHAR(10))
    client_draft_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "review_revisions.id",
            name="fk_review_current_revision",
            ondelete="SET NULL",
            use_alter=True,
        )
    )
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status"), nullable=False, default=ReviewStatus.PENDING
    )
    rating_eligibility: Mapped[RatingEligibility] = mapped_column(
        Enum(RatingEligibility, name="rating_eligibility"),
        nullable=False,
        default=RatingEligibility.NOT_EVALUATED,
    )
    conflict_declared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    overall_rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    counted_rating: Mapped[int | None] = mapped_column(SmallInteger)
    visit_month: Mapped[date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    current_revision: Mapped[ReviewRevision | None] = relationship(
        "ReviewRevision",
        primaryjoin="Review.current_revision_id == ReviewRevision.id",
        foreign_keys=[current_revision_id],
        post_update=True,
    )


class ReviewRevision(Base):
    __tablename__ = "review_revisions"
    __table_args__ = (
        UniqueConstraint("review_id", "sequence", name="uq_review_revision_sequence"),
        CheckConstraint("overall_rating BETWEEN 1 AND 5", name="ck_revision_rating_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RevisionStatus] = mapped_column(
        Enum(RevisionStatus, name="revision_status"), nullable=False, default=RevisionStatus.PENDING
    )
    language: Mapped[ReviewLanguage] = mapped_column(
        Enum(ReviewLanguage, name="review_language"), nullable=False
    )
    traveller_type: Mapped[TravellerType] = mapped_column(
        Enum(TravellerType, name="traveller_type"), nullable=False
    )
    comfort_tier: Mapped[ComfortTier] = mapped_column(
        Enum(ComfortTier, name="comfort_tier"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    overall_rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    consent_version: Mapped[str] = mapped_column(String(40), nullable=False)
    tombstoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ReviewCategoryRating(Base):
    """One optional category score of a revision; an absent row means not applicable."""

    __tablename__ = "review_category_ratings"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_category_rating_range"),)

    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_revisions.id", ondelete="CASCADE"), primary_key=True
    )
    category: Mapped[ReviewCategory] = mapped_column(
        Enum(ReviewCategory, name="review_category"), primary_key=True
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class ReviewReceipt(Base):
    """Keyed digest of a client-generated receipt. The raw receipt is never stored."""

    __tablename__ = "review_receipts"
    __table_args__ = (UniqueConstraint("key_id", "digest", name="uq_review_receipt_key_digest"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )
    key_id: Mapped[str] = mapped_column(String(16), nullable=False)
    digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DestinationRatingStats(Base):
    __tablename__ = "destination_rating_stats"
    __table_args__ = (
        CheckConstraint("community_rating_count >= 0", name="ck_community_count_nonnegative"),
        CheckConstraint("guest_rating_count >= 0", name="ck_guest_count_nonnegative"),
        CheckConstraint("community_rating_sum >= 0", name="ck_community_sum_nonnegative"),
        CheckConstraint("guest_rating_sum >= 0", name="ck_guest_sum_nonnegative"),
    )

    destination_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), primary_key=True
    )
    community_rating_sum: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    community_rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    guest_rating_sum: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    guest_rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class DestinationCategoryStats(Base):
    """O(1) per-category sum and count, moved in the same transaction as the overall aggregate."""

    __tablename__ = "destination_category_stats"
    __table_args__ = (
        CheckConstraint("rating_sum >= 0", name="ck_category_stats_sum_nonnegative"),
        CheckConstraint("rating_count >= 0", name="ck_category_stats_count_nonnegative"),
    )

    destination_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), primary_key=True
    )
    category: Mapped[ReviewCategory] = mapped_column(
        Enum(ReviewCategory, name="review_category"), primary_key=True
    )
    audience: Mapped[RatingAudience] = mapped_column(
        Enum(RatingAudience, name="rating_audience"), primary_key=True
    )
    rating_sum: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ModerationActionRecord(Base):
    __tablename__ = "moderation_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reviews.id", ondelete="RESTRICT"), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[ModerationDecision] = mapped_column(
        Enum(ModerationDecision, name="moderation_decision"), nullable=False
    )
    previous_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="moderation_previous_status"), nullable=False
    )
    new_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="moderation_new_status"), nullable=False
    )
    reason_code: Mapped[str] = mapped_column(String(60), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))



class RateLimitBucket(Base):
    """Fixed-window attempt counter keyed by a keyed digest; never holds raw identifiers."""

    __tablename__ = "rate_limit_buckets"
    __table_args__ = (
        CheckConstraint("count >= 0", name="ck_rate_limit_count_nonnegative"),
        Index("ix_rate_limit_buckets_window_start", "window_start"),
    )

    rule: Mapped[str] = mapped_column(String(60), primary_key=True)
    key_digest: Mapped[bytes] = mapped_column(LargeBinary(32), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class VisitDailyStats(Base):
    """Four visit totals per Asia/Dhaka day, rolled up from Redis (Guest-Identity-and-Visits 4.5).

    Numbers only: no guest tag, secret, address or user reference. The split columns are NULL only
    for legacy days migrated from ``guest_visits``, whose totals sit in ``guest_total_legacy``.
    """

    __tablename__ = "visit_daily_stats"
    __table_args__ = tuple(
        CheckConstraint(f"{column} IS NULL OR {column} >= 0", name=f"ck_visit_daily_stats_{column}")
        for column in ("guest_new", "guest_returning", "member_new", "member_returning", "guest_total_legacy")
    )

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    guest_new: Mapped[int | None] = mapped_column(Integer)
    guest_returning: Mapped[int | None] = mapped_column(Integer)
    member_new: Mapped[int | None] = mapped_column(Integer)
    member_returning: Mapped[int | None] = mapped_column(Integer)
    guest_total_legacy: Mapped[int | None] = mapped_column(Integer)
    rolled_up_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
