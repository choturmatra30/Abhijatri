"""Durable rate-limit counters (WP5).

Revision ID: 0005_rate_limit_buckets
Revises: 0004_receipt_keyring
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_rate_limit_buckets"
down_revision: str | None = "0004_receipt_keyring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("rule", sa.String(60), primary_key=True),
        sa.Column("key_digest", sa.LargeBinary(32), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("count >= 0", name="ck_rate_limit_count_nonnegative"),
    )
    op.create_index("ix_rate_limit_buckets_window_start", "rate_limit_buckets", ["window_start"])
    op.execute("ALTER TABLE public.rate_limit_buckets ENABLE ROW LEVEL SECURITY")
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
    op.drop_index("ix_rate_limit_buckets_window_start", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
