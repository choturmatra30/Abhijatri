"""Anonymous guest counter: one keyed digest per guest device, no name (Review.md 3.2).

Revision ID: 0007_guest_visits
Revises: 0006_review_category_ratings
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007_guest_visits"
down_revision: str | None = "0006_review_category_ratings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guest_visits",
        sa.Column("scope_hash", sa.LargeBinary(32), primary_key=True),
        sa.Column("key_id", sa.String(16), nullable=False),
        sa.Column("guest_number", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("guest_number", name="guest_visits_guest_number_key"),
    )
    op.execute("ALTER TABLE public.guest_visits ENABLE ROW LEVEL SECURITY")
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
    op.drop_table("guest_visits")
