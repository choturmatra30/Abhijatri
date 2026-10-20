"""Guest footprint keeps only a running number and a timestamp (scope owner, 20 Oct 2026).

`guest_visits` previously held a keyed digest per guest device. Who a guest is does not matter,
only how many come each day, so the table now has exactly two columns and nothing that could
identify or re-identify a guest. Existing rows (one test row) are discarded.

Revision ID: 0008_guest_visits_count_only
Revises: 0007_guest_visits
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008_guest_visits_count_only"
down_revision: str | None = "0007_guest_visits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVOKE_SUPABASE_ROLES = """
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


def upgrade() -> None:
    op.drop_table("guest_visits")
    op.create_table(
        "guest_visits",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_guest_visits_visited_at", "guest_visits", ["visited_at"])
    op.execute("ALTER TABLE public.guest_visits ENABLE ROW LEVEL SECURITY")
    op.execute(REVOKE_SUPABASE_ROLES)


def downgrade() -> None:
    op.drop_index("ix_guest_visits_visited_at", table_name="guest_visits")
    op.drop_table("guest_visits")
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
    op.execute(REVOKE_SUPABASE_ROLES)
