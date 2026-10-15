"""Enable row-level security on every public table.

Supabase exposes the public schema through its Data API. The backend connects as the
table owner (bypasses RLS) and no policies are defined, so the Data API roles see nothing.

Revision ID: 0002_enable_rls
Revises: 0001_review_vertical_slice
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_enable_rls"
down_revision: str | None = "0001_review_vertical_slice"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FOR_EACH_TABLE = """
DO $$
DECLARE t record;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I {action} ROW LEVEL SECURITY', t.tablename);
  END LOOP;
END $$;
"""

_REVOKE_API_ROLES = """
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', r);
      EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', r);
    END IF;
  END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(_FOR_EACH_TABLE.format(action="ENABLE"))
    op.execute(_REVOKE_API_ROLES)


def downgrade() -> None:
    op.execute(_FOR_EACH_TABLE.format(action="DISABLE"))
