"""Client-generated receipts and a versioned keyring (WP3).

Receipt digests gain a ``key_id`` and become unique per ``(key_id, digest)``. Guest scope
digests gain ``guest_scope_key_id``. Receipts issued under the old server-generated scheme
used an unlabelled pepper digest and cannot be verified under the new scheme, so they are
revoked and marked ``legacy``; existing guest scopes keep their stored digest as ``legacy``.

Revision ID: 0004_receipt_keyring
Revises: 0003_destination_content
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004_receipt_keyring"
down_revision: str | None = "0003_destination_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("review_receipts", sa.Column("key_id", sa.String(16)))
    op.execute("UPDATE review_receipts SET key_id = 'legacy', revoked_at = COALESCE(revoked_at, now())")
    op.alter_column("review_receipts", "key_id", nullable=False)
    op.drop_constraint("review_receipts_token_hash_key", "review_receipts", type_="unique")
    op.alter_column("review_receipts", "token_hash", new_column_name="digest")
    op.create_unique_constraint("uq_review_receipt_key_digest", "review_receipts", ["key_id", "digest"])

    op.add_column("reviews", sa.Column("guest_scope_key_id", sa.String(16)))
    op.execute("UPDATE reviews SET guest_scope_key_id = 'legacy' WHERE guest_scope_hash IS NOT NULL")
    op.create_check_constraint(
        "ck_review_scope_key_pair", "reviews", "(guest_scope_hash IS NULL) = (guest_scope_key_id IS NULL)"
    )


def downgrade() -> None:
    op.drop_constraint("ck_review_scope_key_pair", "reviews", type_="check")
    op.drop_column("reviews", "guest_scope_key_id")

    op.drop_constraint("uq_review_receipt_key_digest", "review_receipts", type_="unique")
    op.alter_column("review_receipts", "digest", new_column_name="token_hash")
    op.create_unique_constraint("review_receipts_token_hash_key", "review_receipts", ["token_hash"])
    op.drop_column("review_receipts", "key_id")
