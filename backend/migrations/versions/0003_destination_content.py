"""Destination profile fields, guide items, advisories and contacts (R02).

Every new table carries the provenance columns required by Platform Foundation 17 and
enables row-level security itself, because 0002 only covered the tables that existed then.

Revision ID: 0003_destination_content
Revises: 0002_enable_rls
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_destination_content"
down_revision: str | None = "0002_enable_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name, create_type=False)


source_type = _enum("source_type", "OFFICIAL", "TEAM_RESEARCH", "OPEN_LICENCE", "VENDOR_LICENSED", "OTHER")
guide_category = _enum(
    "guide_category", "ATTRACTION", "ACCOMMODATION", "FOOD", "TRANSPORT", "LOCAL_PRACTICE"
)
advisory_severity = _enum("advisory_severity", "INFO", "CAUTION", "WARNING", "CRITICAL")
contact_kind = _enum(
    "contact_kind",
    "POLICE",
    "TOURIST_POLICE",
    "AMBULANCE",
    "FIRE",
    "HOSPITAL",
    "COAST_GUARD",
    "FOREST_OFFICE",
    "LOCAL_GUIDE",
    "OTHER",
)
ENUMS = (source_type, guide_category, advisory_severity, contact_kind)
NEW_TABLES = ("destination_guide_items", "destination_advisories", "destination_contacts")
NEW_DESTINATION_COLUMNS = (
    "region_bn",
    "region_en",
    "summary_bn",
    "summary_en",
    "seasonality_bn",
    "seasonality_en",
    "restrictions_bn",
    "restrictions_en",
    "latitude",
    "longitude",
    "content_licence",
    "content_verified_on",
)


def _provenance_columns() -> list[sa.Column]:
    return [
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(160), nullable=False),
        sa.Column("effective_on", sa.Date(), nullable=False),
        sa.Column("verified_on", sa.Date(), nullable=False),
        sa.Column("next_review_on", sa.Date()),
        sa.Column("licence", sa.String(160), nullable=False),
        sa.Column("researcher", sa.String(120), nullable=False),
        sa.Column("reviewer", sa.String(120)),
    ]


def _destination_fk() -> sa.Column:
    return sa.Column(
        "destination_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("destinations.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    bind = op.get_bind()
    for enum in ENUMS:
        enum.create(bind, checkfirst=True)

    op.add_column("destinations", sa.Column("region_bn", sa.String(160)))
    op.add_column("destinations", sa.Column("region_en", sa.String(160)))
    op.add_column("destinations", sa.Column("summary_bn", sa.Text()))
    op.add_column("destinations", sa.Column("summary_en", sa.Text()))
    op.add_column("destinations", sa.Column("seasonality_bn", sa.Text()))
    op.add_column("destinations", sa.Column("seasonality_en", sa.Text()))
    op.add_column("destinations", sa.Column("restrictions_bn", sa.Text()))
    op.add_column("destinations", sa.Column("restrictions_en", sa.Text()))
    op.add_column("destinations", sa.Column("latitude", sa.Numeric(9, 6)))
    op.add_column("destinations", sa.Column("longitude", sa.Numeric(9, 6)))
    op.add_column("destinations", sa.Column("content_licence", sa.String(160)))
    op.add_column("destinations", sa.Column("content_verified_on", sa.Date()))
    op.create_check_constraint(
        "ck_destination_latitude_range", "destinations", "latitude IS NULL OR latitude BETWEEN -90 AND 90"
    )
    op.create_check_constraint(
        "ck_destination_longitude_range",
        "destinations",
        "longitude IS NULL OR longitude BETWEEN -180 AND 180",
    )
    op.create_check_constraint(
        "ck_destination_coordinates_pair", "destinations", "(latitude IS NULL) = (longitude IS NULL)"
    )
    op.create_index(
        "ix_destinations_published_name",
        "destinations",
        ["name_en", "id"],
        postgresql_where=sa.text("status = 'PUBLISHED'"),
    )

    op.create_table(
        "destination_guide_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _destination_fk(),
        sa.Column("category", guide_category, nullable=False),
        sa.Column("title_bn", sa.String(160), nullable=False),
        sa.Column("title_en", sa.String(160), nullable=False),
        sa.Column("body_bn", sa.Text(), nullable=False),
        sa.Column("body_en", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *_provenance_columns(),
    )
    op.create_index(
        "ix_guide_items_destination_category",
        "destination_guide_items",
        ["destination_id", "category", "sort_order"],
    )

    op.create_table(
        "destination_advisories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _destination_fk(),
        sa.Column("severity", advisory_severity, nullable=False),
        sa.Column("title_bn", sa.String(160), nullable=False),
        sa.Column("title_en", sa.String(160), nullable=False),
        sa.Column("text_bn", sa.Text(), nullable=False),
        sa.Column("text_en", sa.Text(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *_provenance_columns(),
        sa.CheckConstraint("valid_until >= effective_on", name="ck_advisory_validity_window"),
    )
    op.create_index(
        "ix_advisories_destination_valid_until",
        "destination_advisories",
        ["destination_id", "valid_until"],
    )

    op.create_table(
        "destination_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _destination_fk(),
        sa.Column("kind", contact_kind, nullable=False),
        sa.Column("name_bn", sa.String(160), nullable=False),
        sa.Column("name_en", sa.String(160), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("address_bn", sa.String(300)),
        sa.Column("address_en", sa.String(300)),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *_provenance_columns(),
        sa.CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_contact_latitude_range"
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_contact_longitude_range"
        ),
        sa.CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="ck_contact_coordinates_pair"),
        sa.CheckConstraint(r"phone ~ '^\+?[0-9][0-9 -]{2,30}$'", name="ck_contact_phone_format"),
    )
    op.create_index("ix_contacts_destination_kind", "destination_contacts", ["destination_id", "kind"])

    for table in NEW_TABLES:
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
    op.drop_index("ix_contacts_destination_kind", table_name="destination_contacts")
    op.drop_table("destination_contacts")
    op.drop_index("ix_advisories_destination_valid_until", table_name="destination_advisories")
    op.drop_table("destination_advisories")
    op.drop_index("ix_guide_items_destination_category", table_name="destination_guide_items")
    op.drop_table("destination_guide_items")

    op.drop_index("ix_destinations_published_name", table_name="destinations")
    op.drop_constraint("ck_destination_coordinates_pair", "destinations", type_="check")
    op.drop_constraint("ck_destination_longitude_range", "destinations", type_="check")
    op.drop_constraint("ck_destination_latitude_range", "destinations", type_="check")
    for column in reversed(NEW_DESTINATION_COLUMNS):
        op.drop_column("destinations", column)

    bind = op.get_bind()
    for enum in reversed(ENUMS):
        enum.drop(bind, checkfirst=True)
