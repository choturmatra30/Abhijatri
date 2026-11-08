# ruff: noqa: S608
"""Verified Member application (Features/Verified user sign-up form.md, sections 4 to 10).

- ``verification_cases`` gains the application fields (sealed legal names, birth date and document number;
  plain birth year, claimed gender, district and occupation), ``draft`` and ``expired`` states, a
  ``purpose`` (initial, renewal, student update), risk flags and clarification steps. The one-open-case
  index now also covers drafts; ``one_document_per_person`` stops one document approving two people.
- ``verification_evidence`` gains ``kind`` (existing rows become ``LEGACY``), hashes for reuse detection,
  the key of the sealed copy and flags.
- New: ``institutions`` (seeded starter list), ``phone_numbers`` (one verified number per person),
  ``verification_attributes`` (the only source of tour eligibility), ``emergency_contacts_default``,
  ``verification_bans`` and ``one_time_codes``.
- Row-level security on every new table; the Supabase client roles get no grants.

Downgrade drops the new tables and columns. Existing cases keep their rows; drafts and expired cases are
removed first so the old state check can be restored.

Revision ID: 0023_verification_application
Revises: 0022_request_idempotency
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_verification_application"
down_revision: str | None = "0022_request_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = ("institutions", "phone_numbers", "verification_attributes", "emergency_contacts_default", "verification_bans", "one_time_codes")

# A starter list; staff extend it. (name_en, name_bn, kind, email_domain)
INSTITUTIONS = [
    ("University of Dhaka", "ঢাকা বিশ্ববিদ্যালয়", "UNIVERSITY", "du.ac.bd"),
    ("Bangladesh University of Engineering and Technology", "বাংলাদেশ প্রকৌশল বিশ্ববিদ্যালয়", "UNIVERSITY", "buet.ac.bd"),
    ("University of Chittagong", "চট্টগ্রাম বিশ্ববিদ্যালয়", "UNIVERSITY", "cu.ac.bd"),
    ("University of Rajshahi", "রাজশাহী বিশ্ববিদ্যালয়", "UNIVERSITY", "ru.ac.bd"),
    ("Jahangirnagar University", "জাহাঙ্গীরনগর বিশ্ববিদ্যালয়", "UNIVERSITY", "juniv.edu"),
    ("Khulna University", "খুলনা বিশ্ববিদ্যালয়", "UNIVERSITY", "ku.ac.bd"),
    ("Khulna University of Engineering & Technology", "খুলনা প্রকৌশল ও প্রযুক্তি বিশ্ববিদ্যালয়", "UNIVERSITY", "kuet.ac.bd"),
    ("Rajshahi University of Engineering & Technology", "রাজশাহী প্রকৌশল ও প্রযুক্তি বিশ্ববিদ্যালয়", "UNIVERSITY", "ruet.ac.bd"),
    ("Chittagong University of Engineering & Technology", "চট্টগ্রাম প্রকৌশল ও প্রযুক্তি বিশ্ববিদ্যালয়", "UNIVERSITY", "cuet.ac.bd"),
    ("Shahjalal University of Science and Technology", "শাহজালাল বিজ্ঞান ও প্রযুক্তি বিশ্ববিদ্যালয়", "UNIVERSITY", "sust.edu"),
    ("Bangladesh Agricultural University", "বাংলাদেশ কৃষি বিশ্ববিদ্যালয়", "UNIVERSITY", "bau.edu.bd"),
    ("Jagannath University", "জগন্নাথ বিশ্ববিদ্যালয়", "UNIVERSITY", "jnu.ac.bd"),
    ("Comilla University", "কুমিল্লা বিশ্ববিদ্যালয়", "UNIVERSITY", "cou.ac.bd"),
    ("Islamic University, Kushtia", "ইসলামী বিশ্ববিদ্যালয়, কুষ্টিয়া", "UNIVERSITY", "iu.ac.bd"),
    ("Begum Rokeya University, Rangpur", "বেগম রোকেয়া বিশ্ববিদ্যালয়, রংপুর", "UNIVERSITY", "brur.ac.bd"),
    ("Bangladesh University of Professionals", "বাংলাদেশ ইউনিভার্সিটি অব প্রফেশনালস", "UNIVERSITY", "bup.edu.bd"),
    ("National University", "জাতীয় বিশ্ববিদ্যালয়", "UNIVERSITY", "nu.ac.bd"),
    ("Bangladesh Open University", "বাংলাদেশ উন্মুক্ত বিশ্ববিদ্যালয়", "UNIVERSITY", "bou.ac.bd"),
    ("Dhaka Medical College", "ঢাকা মেডিকেল কলেজ", "MEDICAL_COLLEGE", None),
    ("Chittagong Medical College", "চট্টগ্রাম মেডিকেল কলেজ", "MEDICAL_COLLEGE", None),
    ("North South University", "নর্থ সাউথ বিশ্ববিদ্যালয়", "UNIVERSITY", "northsouth.edu"),
    ("BRAC University", "ব্র্যাক বিশ্ববিদ্যালয়", "UNIVERSITY", "bracu.ac.bd"),
    ("Independent University, Bangladesh", "ইনডিপেনডেন্ট ইউনিভার্সিটি, বাংলাদেশ", "UNIVERSITY", "iub.edu.bd"),
    ("East West University", "ইস্ট ওয়েস্ট বিশ্ববিদ্যালয়", "UNIVERSITY", "ewubd.edu"),
    ("American International University-Bangladesh", "আমেরিকান ইন্টারন্যাশনাল ইউনিভার্সিটি-বাংলাদেশ", "UNIVERSITY", "aiub.edu"),
    ("United International University", "ইউনাইটেড ইন্টারন্যাশনাল ইউনিভার্সিটি", "UNIVERSITY", "uiu.ac.bd"),
    ("Daffodil International University", "ড্যাফোডিল ইন্টারন্যাশনাল ইউনিভার্সিটি", "UNIVERSITY", "diu.edu.bd"),
    ("Ahsanullah University of Science and Technology", "আহছানউল্লা বিজ্ঞান ও প্রযুক্তি বিশ্ববিদ্যালয়", "UNIVERSITY", "aust.edu"),
    ("Islamic University of Technology", "ইসলামিক ইউনিভার্সিটি অব টেকনোলজি", "UNIVERSITY", "iut-dhaka.edu"),
    ("University of Liberal Arts Bangladesh", "ইউনিভার্সিটি অব লিবারেল আর্টস বাংলাদেশ", "UNIVERSITY", "ulab.edu.bd"),
    ("Dhaka College", "ঢাকা কলেজ", "COLLEGE", None),
    ("Notre Dame College, Dhaka", "নটর ডেম কলেজ, ঢাকা", "COLLEGE", None),
    ("Rajshahi College", "রাজশাহী কলেজ", "COLLEGE", None),
    ("Chittagong College", "চট্টগ্রাম কলেজ", "COLLEGE", None),
    ("Eden Mohila College", "ইডেন মহিলা কলেজ", "COLLEGE", None),
    ("Carmichael College, Rangpur", "কারমাইকেল কলেজ, রংপুর", "COLLEGE", None),
    ("Murari Chand College, Sylhet", "মুরারিচাঁদ কলেজ, সিলেট", "COLLEGE", None),
    ("Islamic Arabic University", "ইসলামি আরবি বিশ্ববিদ্যালয়", "MADRASA", "iau.edu.bd"),
    ("Government Madrasah-e-Alia, Dhaka", "সরকারি মাদ্রাসা-ই-আলিয়া, ঢাকা", "MADRASA", None),
    ("Darul Uloom Moinul Islam, Hathazari", "দারুল উলুম মুঈনুল ইসলাম, হাটহাজারী", "MADRASA", None),
]


def _lock_down(table: str) -> None:
    op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        DO $$
        DECLARE r text;
        BEGIN
          FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
              EXECUTE format('REVOKE ALL ON public.{table} FROM %I', r);
            END IF;
          END LOOP;
        END $$;
        """
    )


def upgrade() -> None:
    op.create_table(
        "institutions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name_en", sa.String(160), nullable=False),
        sa.Column("name_bn", sa.String(160), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("email_domain", sa.String(80), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name_en"),
    )
    op.create_table(
        "phone_numbers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("phone_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("phone_enc", sa.LargeBinary(), nullable=False),
        sa.Column("last4", sa.String(4), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("one_verified_phone", "phone_numbers", ["phone_hash"], unique=True, postgresql_where=sa.text("verified_at IS NOT NULL"))
    op.create_index("ix_phone_numbers_user", "phone_numbers", ["user_id"])
    op.create_table(
        "verification_attributes",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("gender", sa.String(10), nullable=False),
        sa.Column("birth_year", sa.SmallInteger(), nullable=False),
        sa.Column("is_student", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("student_until", sa.Date(), nullable=True),
        sa.Column("home_district", sa.String(40), nullable=True),
        sa.Column("set_by", sa.UUID(), nullable=True),
        sa.Column("set_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("gender IN ('FEMALE', 'MALE', 'THIRD')", name="ck_verification_attributes_gender"),
        sa.CheckConstraint("birth_year BETWEEN 1900 AND 2100", name="ck_verification_attributes_birth_year"),
        sa.CheckConstraint("NOT is_student OR student_until IS NOT NULL", name="ck_verification_attributes_student_until"),
        sa.ForeignKeyConstraint(["set_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "emergency_contacts_default",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("sealed", sa.LargeBinary(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "verification_bans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("doc_hash", sa.LargeBinary(32), nullable=True),
        sa.Column("phone_hash", sa.LargeBinary(32), nullable=True),
        sa.Column("reason", sa.String(60), nullable=False),
        sa.Column("until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lifted_by", sa.UUID(), nullable=True),
        sa.Column("lifted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lifted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_verification_bans_user", "verification_bans", ["user_id"])
    op.create_index("ix_verification_bans_doc", "verification_bans", ["doc_hash"])
    op.create_index("ix_verification_bans_phone", "verification_bans", ["phone_hash"])

    # ---- verification_cases ----
    op.drop_constraint("ck_verification_cases_state", "verification_cases", type_="check")
    op.create_check_constraint(
        "ck_verification_cases_state", "verification_cases",
        "state IN ('draft', 'submitted', 'in_review', 'needs_clarification', 'approved', 'rejected', 'escalated', 'withdrawn', 'expired')",
    )
    op.drop_index("uq_verification_cases_one_open", table_name="verification_cases")
    op.create_index(
        "uq_verification_cases_one_open", "verification_cases", ["applicant_user_id"], unique=True,
        postgresql_where=sa.text("state IN ('draft', 'submitted', 'in_review', 'needs_clarification', 'escalated')"),
    )
    op.alter_column("verification_cases", "state", server_default="draft")
    columns = [
        sa.Column("purpose", sa.String(16), server_default="initial", nullable=False),
        sa.Column("age_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("legal_name_enc", sa.LargeBinary(), nullable=True),
        sa.Column("legal_name_bn_enc", sa.LargeBinary(), nullable=True),
        sa.Column("dob_enc", sa.LargeBinary(), nullable=True),
        sa.Column("birth_year", sa.SmallInteger(), nullable=True),
        sa.Column("gender_claimed", sa.String(10), nullable=True),
        sa.Column("home_district", sa.String(40), nullable=True),
        sa.Column("current_area", sa.String(60), nullable=True),
        sa.Column("occupation", sa.String(20), nullable=True),
        sa.Column("phone_id", sa.UUID(), nullable=True),
        sa.Column("doc_type", sa.String(20), nullable=True),
        sa.Column("doc_number_enc", sa.LargeBinary(), nullable=True),
        sa.Column("doc_last4", sa.String(4), nullable=True),
        sa.Column("doc_hash", sa.LargeBinary(32), nullable=True),
        sa.Column("doc_expiry", sa.Date(), nullable=True),
        sa.Column("is_student_claim", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("institution_id", sa.UUID(), nullable=True),
        sa.Column("institution_other", sa.String(120), nullable=True),
        sa.Column("institution_email_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("study_end_month", sa.Date(), nullable=True),
        sa.Column("liveness_code", sa.String(4), nullable=True),
        sa.Column("liveness_gesture", sa.String(40), nullable=True),
        sa.Column("liveness_issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declaration_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clarification_steps", postgresql.ARRAY(sa.String(20)), nullable=True),
        sa.Column("risk_flags", postgresql.ARRAY(sa.String(40)), server_default=sa.text("'{}'::varchar[]"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("draft_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clarification_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("network_hash", sa.LargeBinary(32), nullable=True),
    ]
    for column in columns:
        op.add_column("verification_cases", column)
    op.create_foreign_key("verification_cases_phone_id_fkey", "verification_cases", "phone_numbers", ["phone_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("verification_cases_institution_id_fkey", "verification_cases", "institutions", ["institution_id"], ["id"], ondelete="SET NULL")
    op.create_check_constraint("ck_verification_cases_purpose", "verification_cases", "purpose IN ('initial', 'renewal', 'student_update')")
    op.create_check_constraint("ck_verification_cases_birth_year", "verification_cases", "birth_year IS NULL OR birth_year BETWEEN 1900 AND 2100")
    op.create_check_constraint("ck_verification_cases_gender", "verification_cases", "gender_claimed IS NULL OR gender_claimed IN ('FEMALE', 'MALE', 'THIRD')")
    op.create_check_constraint("ck_verification_cases_doc_type", "verification_cases", "doc_type IS NULL OR doc_type IN ('NID', 'PASSPORT', 'DRIVING_LICENCE')")
    op.create_check_constraint(
        "ck_verification_cases_occupation", "verification_cases",
        "occupation IS NULL OR occupation IN ('STUDENT', 'EMPLOYED', 'SELF_EMPLOYED', 'NOT_WORKING', 'OTHER')",
    )
    op.create_index("one_document_per_person", "verification_cases", ["doc_hash"], unique=True, postgresql_where=sa.text("state = 'approved'"))
    op.create_index("ix_verification_cases_doc_hash", "verification_cases", ["doc_hash"])

    # ---- verification_evidence ----
    op.add_column("verification_evidence", sa.Column("kind", sa.String(16), server_default="LEGACY", nullable=False))
    op.add_column("verification_evidence", sa.Column("sha256", sa.LargeBinary(32), nullable=True))
    op.add_column("verification_evidence", sa.Column("phash", sa.LargeBinary(8), nullable=True))
    op.add_column("verification_evidence", sa.Column("sealed_key", sa.String(300), nullable=True))
    op.add_column("verification_evidence", sa.Column("challenge", sa.String(80), nullable=True))
    op.add_column("verification_evidence", sa.Column("flags", postgresql.ARRAY(sa.String(40)), server_default=sa.text("'{}'::varchar[]"), nullable=False))
    op.create_check_constraint(
        "ck_verification_evidence_kind", "verification_evidence", "kind IN ('DOC_FRONT', 'DOC_BACK', 'SELFIE', 'STUDENT_CARD', 'LEGACY')"
    )
    op.create_index("ix_verification_evidence_sha256", "verification_evidence", ["sha256"])

    op.create_table(
        "one_time_codes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=True),
        sa.Column("channel", sa.String(8), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("target_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("target_enc", sa.LargeBinary(), nullable=False),
        sa.Column("code_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("channel IN ('sms', 'email')", name="ck_one_time_codes_channel"),
        sa.ForeignKeyConstraint(["case_id"], ["verification_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_one_time_codes_user_created", "one_time_codes", ["user_id", "created_at"])
    op.create_index("ix_one_time_codes_target_created", "one_time_codes", ["target_hash", "created_at"])

    for table in NEW_TABLES:
        _lock_down(table)

    institutions = sa.table(
        "institutions", sa.column("id", sa.UUID()), sa.column("name_en", sa.String()), sa.column("name_bn", sa.String()),
        sa.column("kind", sa.String()), sa.column("email_domain", sa.String()), sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        institutions,
        [
            {"id": uuid.uuid5(uuid.NAMESPACE_URL, f"abhijatri:institution:{name_en}"), "name_en": name_en, "name_bn": name_bn, "kind": kind, "email_domain": domain, "active": True}
            for name_en, name_bn, kind, domain in INSTITUTIONS
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_one_time_codes_target_created", table_name="one_time_codes")
    op.drop_index("ix_one_time_codes_user_created", table_name="one_time_codes")
    op.drop_table("one_time_codes")
    op.drop_index("ix_verification_evidence_sha256", table_name="verification_evidence")
    op.drop_constraint("ck_verification_evidence_kind", "verification_evidence", type_="check")
    for name in ("flags", "challenge", "sealed_key", "phash", "sha256", "kind"):
        op.drop_column("verification_evidence", name)
    op.execute("DELETE FROM verification_cases WHERE state IN ('draft', 'expired')")
    op.drop_index("ix_verification_cases_doc_hash", table_name="verification_cases")
    op.drop_index("one_document_per_person", table_name="verification_cases")
    for name in ("occupation", "doc_type", "gender", "birth_year", "purpose"):
        op.drop_constraint(f"ck_verification_cases_{name}", "verification_cases", type_="check")
    op.drop_constraint("verification_cases_institution_id_fkey", "verification_cases", type_="foreignkey")
    op.drop_constraint("verification_cases_phone_id_fkey", "verification_cases", type_="foreignkey")
    for name in (
        "network_hash", "clarification_due_at", "draft_expires_at", "submitted_at", "risk_flags", "clarification_steps", "declaration_at",
        "liveness_issued_at", "liveness_gesture", "liveness_code", "study_end_month", "institution_email_verified", "institution_other",
        "institution_id", "is_student_claim", "doc_expiry", "doc_hash", "doc_last4", "doc_number_enc", "doc_type", "phone_id", "occupation",
        "current_area", "home_district", "gender_claimed", "birth_year", "dob_enc", "legal_name_bn_enc", "legal_name_enc", "consent_at",
        "age_confirmed_at", "purpose",
    ):
        op.drop_column("verification_cases", name)
    op.alter_column("verification_cases", "state", server_default="submitted")
    op.drop_index("uq_verification_cases_one_open", table_name="verification_cases")
    op.create_index(
        "uq_verification_cases_one_open", "verification_cases", ["applicant_user_id"], unique=True,
        postgresql_where=sa.text("state IN ('submitted', 'in_review', 'needs_clarification', 'escalated')"),
    )
    op.drop_constraint("ck_verification_cases_state", "verification_cases", type_="check")
    op.create_check_constraint(
        "ck_verification_cases_state", "verification_cases",
        "state IN ('submitted', 'in_review', 'needs_clarification', 'approved', 'rejected', 'escalated', 'withdrawn')",
    )
    for index, table in (("ix_verification_bans_phone", "verification_bans"), ("ix_verification_bans_doc", "verification_bans"), ("ix_verification_bans_user", "verification_bans")):
        op.drop_index(index, table_name=table)
    op.drop_table("verification_bans")
    op.drop_table("emergency_contacts_default")
    op.drop_table("verification_attributes")
    op.drop_index("ix_phone_numbers_user", table_name="phone_numbers")
    op.drop_index("one_verified_phone", table_name="phone_numbers")
    op.drop_table("phone_numbers")
    op.drop_table("institutions")
