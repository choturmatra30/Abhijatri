"""R16 Idempotency-Key replay for retryable public and member writes.

- ``request_idempotency`` stores the success response of a write per (caller scope digest,
  endpoint, key digest), the primary key and therefore the unique constraint of Gantt R16.
  The caller is a keyed HMAC digest, the key a SHA-256 and the request a fingerprint; no raw
  secret or key is stored. ``expires_at`` is creation plus ``IDEMPOTENCY_TTL_HOURS`` (72).
- Row-level security is enabled and the Supabase client roles get no grants, like every table.

The staff ``idempotency_keys`` table (Moderation spec 8.2) is unchanged.

Downgrade drops the table. Stored responses are short-lived replays; nothing permanent is lost.

Revision ID: 0022_request_idempotency
Revises: 0021_destination_pack_versions
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0022_request_idempotency"
down_revision: str | None = "0021_destination_pack_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "request_idempotency",
        sa.Column("scope_digest", sa.LargeBinary(32), nullable=False),
        sa.Column("endpoint", sa.String(80), nullable=False),
        sa.Column("key_digest", sa.CHAR(64), nullable=False),
        sa.Column("fingerprint", sa.CHAR(64), nullable=False),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("scope_digest", "endpoint", "key_digest", name="request_idempotency_pkey"),
        sa.CheckConstraint("key_digest ~ '^[0-9a-f]{64}$'", name="ck_request_idempotency_key_hex"),
        sa.CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name="ck_request_idempotency_fingerprint_hex"),
        sa.CheckConstraint("status_code BETWEEN 200 AND 299", name="ck_request_idempotency_success_only"),
        sa.CheckConstraint("expires_at > created_at", name="ck_request_idempotency_expiry_after_creation"),
    )
    op.create_index("ix_request_idempotency_expires_at", "request_idempotency", ["expires_at"])
    op.execute("ALTER TABLE public.request_idempotency ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        DECLARE r text;
        BEGIN
          FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
              EXECUTE format('REVOKE ALL ON public.request_idempotency FROM %I', r);
            END IF;
          END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_request_idempotency_expires_at", table_name="request_idempotency")
    op.drop_table("request_idempotency")
