"""Create the first review vertical slice.

Revision ID: 0001_review_vertical_slice
Revises: None
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_review_vertical_slice"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


destination_status = postgresql.ENUM("DRAFT", "PUBLISHED", "ARCHIVED", name="destination_status")
review_status = postgresql.ENUM(
    "PENDING",
    "UNDER_REVIEW",
    "CHANGES_REQUESTED",
    "PUBLISHED",
    "HIDDEN",
    "REJECTED",
    "WITHDRAWN",
    "DELETED",
    name="review_status",
)
rating_eligibility = postgresql.ENUM(
    "NOT_EVALUATED",
    "ELIGIBLE",
    "INELIGIBLE_GUEST",
    "INELIGIBLE_UNVERIFIED",
    "INELIGIBLE_DUPLICATE",
    "INELIGIBLE_CONFLICT",
    "INELIGIBLE_REPORTED",
    "INELIGIBLE_REMOVED",
    name="rating_eligibility",
)
revision_status = postgresql.ENUM("PENDING", "PUBLISHED", "REJECTED", "TOMBSTONED", name="revision_status")
review_language = postgresql.ENUM("BN", "EN", "MIXED", name="review_language")
traveller_type = postgresql.ENUM("SOLO", "STUDENT", "COUPLE", "FAMILY", "GROUP", name="traveller_type")
comfort_tier = postgresql.ENUM("ECONOMY", "STANDARD", "PREMIUM", name="comfort_tier")
moderation_decision = postgresql.ENUM(
    "PUBLISH",
    "REJECT",
    "HIDE",
    "RESTORE",
    "SET_CONFLICT",
    "CLEAR_CONFLICT",
    name="moderation_decision",
)
moderation_previous_status = postgresql.ENUM(
    "PENDING",
    "UNDER_REVIEW",
    "CHANGES_REQUESTED",
    "PUBLISHED",
    "HIDDEN",
    "REJECTED",
    "WITHDRAWN",
    "DELETED",
    name="moderation_previous_status",
)
moderation_new_status = postgresql.ENUM(
    "PENDING",
    "UNDER_REVIEW",
    "CHANGES_REQUESTED",
    "PUBLISHED",
    "HIDDEN",
    "REJECTED",
    "WITHDRAWN",
    "DELETED",
    name="moderation_new_status",
)


def upgrade() -> None:
    op.create_table(
        "destinations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", destination_status, nullable=False),
        sa.Column("name_bn", sa.String(160), nullable=False),
        sa.Column("name_en", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("is_team_account", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "platform_roles",
        sa.Column("id", sa.SmallInteger(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
    )
    op.create_table(
        "user_platform_roles",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.SmallInteger(), sa.ForeignKey("platform_roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_platform_role"),
    )
    op.create_table(
        "verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("verification_type", sa.String(60), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("method", sa.String(60), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revocation_reason", sa.String(240)),
    )
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("destination_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("guest_display_name", sa.String(80)),
        sa.Column("guest_scope_hash", sa.LargeBinary(32)),
        sa.Column("client_draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_revision_id", postgresql.UUID(as_uuid=True)),
        sa.Column("status", review_status, nullable=False),
        sa.Column("rating_eligibility", rating_eligibility, nullable=False),
        sa.Column("conflict_declared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("duplicate_override", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("overall_rating", sa.SmallInteger(), nullable=False),
        sa.Column("counted_rating", sa.SmallInteger()),
        sa.Column("visit_month", sa.Date(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("overall_rating BETWEEN 1 AND 5", name="ck_review_rating_range"),
        sa.CheckConstraint(
            "counted_rating IS NULL OR counted_rating BETWEEN 1 AND 5",
            name="ck_review_counted_rating_range",
        ),
        sa.CheckConstraint(
            "(author_user_id IS NOT NULL AND guest_display_name IS NULL AND guest_scope_hash IS NULL) OR "
            "(author_user_id IS NULL AND guest_display_name IS NOT NULL AND guest_scope_hash IS NOT NULL)",
            name="ck_review_author_shape",
        ),
    )
    op.create_index(
        "uq_reviews_member_draft",
        "reviews",
        ["author_user_id", "client_draft_id"],
        unique=True,
        postgresql_where=sa.text("author_user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_reviews_guest_draft",
        "reviews",
        ["guest_scope_hash", "client_draft_id"],
        unique=True,
        postgresql_where=sa.text("author_user_id IS NULL"),
    )
    op.create_index(
        "uq_reviews_member_active_visit",
        "reviews",
        ["author_user_id", "destination_id", "visit_month"],
        unique=True,
        postgresql_where=sa.text(
            "author_user_id IS NOT NULL AND duplicate_override = false AND "
            "status IN ('PENDING', 'UNDER_REVIEW', 'CHANGES_REQUESTED', 'PUBLISHED', 'HIDDEN')"
        ),
    )
    op.create_index(
        "ix_reviews_published_feed",
        "reviews",
        ["destination_id", sa.text("published_at DESC"), sa.text("id DESC")],
        postgresql_where=sa.text("status = 'PUBLISHED'"),
    )
    op.create_table(
        "review_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", revision_status, nullable=False),
        sa.Column("language", review_language, nullable=False),
        sa.Column("traveller_type", traveller_type, nullable=False),
        sa.Column("comfort_tier", comfort_tier, nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("overall_rating", sa.SmallInteger(), nullable=False),
        sa.Column("consent_version", sa.String(40), nullable=False),
        sa.Column("tombstoned_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("review_id", "sequence", name="uq_review_revision_sequence"),
        sa.CheckConstraint("overall_rating BETWEEN 1 AND 5", name="ck_revision_rating_range"),
    )
    op.create_foreign_key(
        "fk_review_current_revision",
        "reviews",
        "review_revisions",
        ["current_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "review_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(32), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "destination_rating_stats",
        sa.Column("destination_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("destinations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("community_rating_sum", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("community_rating_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("guest_rating_sum", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("guest_rating_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("community_rating_count >= 0", name="ck_community_count_nonnegative"),
        sa.CheckConstraint("guest_rating_count >= 0", name="ck_guest_count_nonnegative"),
        sa.CheckConstraint("community_rating_sum >= 0", name="ck_community_sum_nonnegative"),
        sa.CheckConstraint("guest_rating_sum >= 0", name="ck_guest_sum_nonnegative"),
    )
    op.create_table(
        "moderation_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reviews.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decision", moderation_decision, nullable=False),
        sa.Column("previous_status", moderation_previous_status, nullable=False),
        sa.Column("new_status", moderation_new_status, nullable=False),
        sa.Column("reason_code", sa.String(60), nullable=False),
        sa.Column("note", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("moderation_actions")
    op.drop_table("destination_rating_stats")
    op.drop_table("review_receipts")
    op.drop_constraint("fk_review_current_revision", "reviews", type_="foreignkey")
    op.drop_table("review_revisions")
    op.drop_index("ix_reviews_published_feed", table_name="reviews")
    op.drop_index("uq_reviews_member_active_visit", table_name="reviews")
    op.drop_index("uq_reviews_guest_draft", table_name="reviews")
    op.drop_index("uq_reviews_member_draft", table_name="reviews")
    op.drop_table("reviews")
    op.drop_table("verifications")
    op.drop_table("user_platform_roles")
    op.drop_table("platform_roles")
    op.drop_table("users")
    op.drop_table("destinations")
    bind = op.get_bind()
    for enum_type in reversed(
        (
            destination_status,
            review_status,
            rating_eligibility,
            revision_status,
            review_language,
            traveller_type,
            comfort_tier,
            moderation_decision,
            moderation_previous_status,
            moderation_new_status,
        )
    ):
        enum_type.drop(bind, checkfirst=True)

