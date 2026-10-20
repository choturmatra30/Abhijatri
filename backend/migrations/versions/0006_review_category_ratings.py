"""Seven category ratings per revision and their per-destination aggregates (Review.md 3.1, A2).

Revision ID: 0006_review_category_ratings
Revises: 0005_rate_limit_buckets
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006_review_category_ratings"
down_revision: str | None = "0005_rate_limit_buckets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVIEW_CATEGORY = postgresql.ENUM(
    "CLEANLINESS",
    "ACCESSIBILITY",
    "HOSPITALITY",
    "FOOD",
    "TRANSPORT",
    "SAFETY_PERCEPTION",
    "VALUE",
    name="review_category",
    create_type=False,
)
RATING_AUDIENCE = postgresql.ENUM("GUEST", "COMMUNITY", name="rating_audience", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    REVIEW_CATEGORY.create(bind, checkfirst=True)
    RATING_AUDIENCE.create(bind, checkfirst=True)

    op.create_table(
        "review_category_ratings",
        sa.Column(
            "revision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("review_revisions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("category", REVIEW_CATEGORY, primary_key=True),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_category_rating_range"),
    )
    op.create_table(
        "destination_category_stats",
        sa.Column(
            "destination_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("destinations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("category", REVIEW_CATEGORY, primary_key=True),
        sa.Column("audience", RATING_AUDIENCE, primary_key=True),
        sa.Column("rating_sum", sa.Integer(), nullable=False),
        sa.Column("rating_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rating_sum >= 0", name="ck_category_stats_sum_nonnegative"),
        sa.CheckConstraint("rating_count >= 0", name="ck_category_stats_count_nonnegative"),
    )
    for table in ("review_category_ratings", "destination_category_stats"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        DECLARE r text;
        BEGIN
          FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
              EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', r);
            END IF;
          END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("destination_category_stats")
    op.drop_table("review_category_ratings")
    bind = op.get_bind()
    RATING_AUDIENCE.drop(bind, checkfirst=True)
    REVIEW_CATEGORY.drop(bind, checkfirst=True)
