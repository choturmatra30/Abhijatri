"""R14 offline destination packs: the built pack, its versions and its SHA-256.

- ``destination_pack_versions`` holds the exact bytes of the newest pack of each published
  destination together with the pack version, content version (SHA-256 of the content only),
  integrity hash (SHA-256 of the bytes), generation time and expiry (PF 18.4).
- Row-level security is enabled and the Supabase client roles get no grants, like every table.

Downgrade drops the table. Packs are rebuilt on the next request, so nothing is lost.

Revision ID: 0021_destination_pack_versions
Revises: 0020_reports_mod_audit
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0021_destination_pack_versions"
down_revision: str | None = "0020_reports_mod_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "destination_pack_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "destination_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("destinations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pack_version", sa.Integer(), nullable=False),
        sa.Column("content_version", sa.CHAR(64), nullable=False),
        sa.Column("sha256", sa.CHAR(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.SmallInteger(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("body", sa.LargeBinary(), nullable=False),
        sa.UniqueConstraint("destination_id", "pack_version", name="uq_pack_versions_destination_version"),
        sa.CheckConstraint("pack_version > 0", name="ck_pack_versions_version_positive"),
        sa.CheckConstraint("size_bytes > 0", name="ck_pack_versions_size_positive"),
        sa.CheckConstraint("schema_version > 0", name="ck_pack_versions_schema_positive"),
        sa.CheckConstraint("expires_at > generated_at", name="ck_pack_versions_expiry_after_generation"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_pack_versions_sha256_hex"),
        sa.CheckConstraint("content_version ~ '^[0-9a-f]{64}$'", name="ck_pack_versions_content_hex"),
    )
    op.create_index(
        "ix_pack_versions_destination_latest",
        "destination_pack_versions",
        ["destination_id", sa.text("pack_version DESC")],
    )
    op.execute("ALTER TABLE public.destination_pack_versions ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        DECLARE r text;
        BEGIN
          FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
              EXECUTE format('REVOKE ALL ON public.destination_pack_versions FROM %I', r);
            END IF;
          END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_pack_versions_destination_latest", table_name="destination_pack_versions")
    op.drop_table("destination_pack_versions")
