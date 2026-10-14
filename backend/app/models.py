from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
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
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
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


class ModerationDecision(str, enum.Enum):
    PUBLISH = "PUBLISH"
    REJECT = "REJECT"
    HIDE = "HIDE"
    RESTORE = "RESTORE"
    SET_CONFLICT = "SET_CONFLICT"
    CLEAR_CONFLICT = "CLEAR_CONFLICT"


class Destination(Base):
    __tablename__ = "destinations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[DestinationStatus] = mapped_column(
        Enum(DestinationStatus, name="destination_status"),
        nullable=False,
        default=DestinationStatus.DRAFT,
    )
    name_bn: Mapped[str] = mapped_column(String(160), nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_team_account: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


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


class ReviewReceipt(Base):
    __tablename__ = "review_receipts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True, nullable=False)
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

