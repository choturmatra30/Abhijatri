"""Tours and TourMates tables (Verified Users Interface spec; architecture 5).

Invariants live in the database as well as in code (architecture 1.2): capacity is a CHECK on the seat
counter, one active membership and one pending request per person are partial unique indexes, one creator
per tour is a partial unique index, ``confirmed_at`` is set once (trigger), and expense shares must add up
to the expense (deferred constraint trigger). Enumerations are text columns with CHECK constraints.
Sensitive values (companions, emergency contacts, medical notes) are sealed with ``app.fieldcrypt``.
"""

import uuid
from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import (
    DDL,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

LIFECYCLES = ("DRAFT", "RECRUITING", "CONFIRMED", "ONGOING", "COMPLETED", "CANCELLED", "ARCHIVED")
RECRUITMENTS = ("OPEN", "PAUSED", "FULL", "CLOSED", "EXPIRED")
POLICIES = ("OPEN", "STUDENTS", "FAMILY", "WOMEN", "MEN", "INVITE_ONLY")
STYLES = ("BUDGET", "STANDARD", "COMFORT")
PACES = ("RELAXED", "BALANCED", "PACKED")
TRANSPORTS = ("BUS", "TRAIN", "LAUNCH", "PRIVATE_CAR", "MIXED")
ACTIVITIES = ("HIKING", "BEACH", "HERITAGE", "FOOD", "PHOTOGRAPHY", "WILDLIFE", "BOATING", "CAMPING", "RELIGIOUS_SITES", "CITY")
RULES = ("NO_SMOKING", "NO_ALCOHOL", "QUIET_HOURS")


def utcnow() -> datetime:
    return datetime.now(UTC)


def _in(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


class UserBlock(Base):
    """One member blocking another (Community.md). Checked both ways by every tour action (AC-11)."""

    __tablename__ = "user_blocks"
    __table_args__ = (
        PrimaryKeyConstraint("blocker_id", "blocked_id", name="user_blocks_pkey"),
        CheckConstraint("blocker_id <> blocked_id", name="ck_user_blocks_not_self"),
        Index("ix_user_blocks_blocked", "blocked_id"),
    )

    blocker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    blocked_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class Tour(Base):
    __tablename__ = "tours"
    __table_args__ = (
        CheckConstraint(f"lifecycle IN {_in(LIFECYCLES)}", name="ck_tours_lifecycle"),
        CheckConstraint(f"recruitment IN {_in(RECRUITMENTS)}", name="ck_tours_recruitment"),
        CheckConstraint("recruitment_choice IN ('OPEN', 'PAUSED', 'CLOSED')", name="ck_tours_recruitment_choice"),
        CheckConstraint(f"policy IN {_in(POLICIES)}", name="ck_tours_policy"),
        CheckConstraint("char_length(title) BETWEEN 8 AND 80", name="ck_tours_title"),
        CheckConstraint("char_length(description) <= 1000", name="ck_tours_description"),
        CheckConstraint("min_members BETWEEN 2 AND 30", name="ck_tours_min"),
        CheckConstraint("max_members BETWEEN 2 AND 30", name="ck_tours_max"),
        CheckConstraint("max_members >= min_members", name="ck_tours_max_ge_min"),
        CheckConstraint("seats_taken BETWEEN 0 AND max_members", name="ck_tours_capacity"),
        CheckConstraint("end_date >= start_date AND end_date - start_date <= 30", name="ck_tours_dates"),
        CheckConstraint(
            "recruit_deadline <= ((start_date::timestamp AT TIME ZONE 'Asia/Dhaka') - interval '24 hours')", name="ck_tours_deadline"
        ),
        CheckConstraint("budget_min_bdt IS NULL OR budget_max_bdt IS NULL OR budget_max_bdt >= budget_min_bdt", name="ck_tours_budget"),
        CheckConstraint("style IS NULL OR style IN " + _in(STYLES), name="ck_tours_style"),
        CheckConstraint("pace IS NULL OR pace IN " + _in(PACES), name="ck_tours_pace"),
        CheckConstraint("transport IS NULL OR transport IN " + _in(TRANSPORTS), name="ck_tours_transport"),
        Index("ix_tours_discovery", "lifecycle", "recruitment", "start_date", postgresql_where=text("suspended_at IS NULL")),
        Index("ix_tours_creator", "creator_id"),
        Index("ix_tours_activities", "activities", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    public_id: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    code: Mapped[str | None] = mapped_column(String(10), unique=True)
    code_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    creator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="", server_default="")
    lifecycle: Mapped[str] = mapped_column(String(12), nullable=False, default="DRAFT", server_default="DRAFT")
    recruitment: Mapped[str] = mapped_column(String(8), nullable=False, default="OPEN", server_default="OPEN")
    recruitment_choice: Mapped[str] = mapped_column(String(8), nullable=False, default="OPEN", server_default="OPEN")  # organiser's last choice
    is_at_risk: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy: Mapped[str] = mapped_column(String(12), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    recruit_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    min_members: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3, server_default="3")
    max_members: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=8, server_default="8")
    seats_taken: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default="1")
    budget_min_bdt: Mapped[int | None] = mapped_column(Integer)
    budget_max_bdt: Mapped[int | None] = mapped_column(Integer)
    budget_includes: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False, default=list, server_default=text("'{}'::varchar[]"))
    style: Mapped[str | None] = mapped_column(String(10))
    pace: Mapped[str | None] = mapped_column(String(10))
    transport: Mapped[str | None] = mapped_column(String(12))
    activities: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False, default=list, server_default=text("'{}'::varchar[]"))
    rules: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False, default=list, server_default=text("'{}'::varchar[]"))
    custom_rules: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False, default=list, server_default=text("'{}'::varchar[]"))
    join_question: Mapped[str | None] = mapped_column(String(200))
    departure_city: Mapped[str | None] = mapped_column(String(60))
    meeting_area: Mapped[str | None] = mapped_column(String(120))
    itinerary_outline: Mapped[str | None] = mapped_column(String(2000))
    accepted_rules_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_reason: Mapped[str | None] = mapped_column(String(60))
    cancelled_by: Mapped[str | None] = mapped_column(String(10))  # CREATOR, SYSTEM or STAFF
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_window_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # 72 h no-mark leave (7.6)
    safety_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


CONFIRMED_ONCE = """
CREATE OR REPLACE FUNCTION tours_confirmed_at_once() RETURNS trigger LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
  IF OLD.confirmed_at IS NOT NULL AND NEW.confirmed_at IS DISTINCT FROM OLD.confirmed_at THEN
    RAISE EXCEPTION 'confirmed_at is set once' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER tours_confirmed_at_once BEFORE UPDATE OF confirmed_at ON tours
  FOR EACH ROW EXECUTE FUNCTION tours_confirmed_at_once();
"""
event.listen(Tour.__table__, "after_create", DDL(CONFIRMED_ONCE))  # type: ignore[no-untyped-call]


class TourDestination(Base):
    __tablename__ = "tour_destinations"
    __table_args__ = (PrimaryKeyConstraint("tour_id", "position", name="tour_destinations_pkey"), UniqueConstraint("tour_id", "destination_id", name="uq_tour_destinations_once"))

    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    destination_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=False)


class TourMember(Base):
    __tablename__ = "tour_members"
    __table_args__ = (
        CheckConstraint("role IN ('CREATOR', 'CO_ORGANIZER', 'TOURMATE')", name="ck_tour_members_role"),
        CheckConstraint("state IN ('ACTIVE', 'LEFT', 'REMOVED', 'INACTIVE')", name="ck_tour_members_state"),
        CheckConstraint("seats BETWEEN 1 AND 5", name="ck_tour_members_seats"),
        CheckConstraint("joined_via IN ('CREATED', 'REQUEST', 'INVITATION')", name="ck_tour_members_joined_via"),
        Index("one_active_membership", "tour_id", "user_id", unique=True, postgresql_where=text("state IN ('ACTIVE', 'INACTIVE')")),
        Index("one_creator", "tour_id", unique=True, postgresql_where=text("role = 'CREATOR' AND state = 'ACTIVE'")),
        Index("ix_tour_members_user", "user_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(14), nullable=False)
    state: Mapped[str] = mapped_column(String(10), nullable=False, default="ACTIVE", server_default="ACTIVE")
    seats: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default="1")
    companions_sealed: Mapped[bytes | None] = mapped_column(LargeBinary)  # family companions (8.3), sealed
    joined_via: Mapped[str] = mapped_column(String(12), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    left_reason: Mapped[str | None] = mapped_column(String(60))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TourJoinRequest(Base):
    __tablename__ = "tour_join_requests"
    __table_args__ = (
        CheckConstraint("state IN ('PENDING', 'APPROVED', 'DECLINED', 'WITHDRAWN', 'EXPIRED', 'CLOSED')", name="ck_tour_join_requests_state"),
        CheckConstraint("seats BETWEEN 1 AND 5", name="ck_tour_join_requests_seats"),
        Index("one_pending_request", "tour_id", "user_id", unique=True, postgresql_where=text("state = 'PENDING'")),
        Index("ix_tour_join_requests_user", "user_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    state: Mapped[str] = mapped_column(String(10), nullable=False, default="PENDING", server_default="PENDING")
    answer: Mapped[str | None] = mapped_column(String(500))
    message: Mapped[str | None] = mapped_column(String(300))
    seats: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default="1")
    companions_sealed: Mapped[bytes | None] = mapped_column(LargeBinary)
    via_code: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decline_code: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class TourChange(Base):
    """History of edits (spec 13.1 "recent changes log"; key-detail changes 7.6)."""

    __tablename__ = "tour_changes"
    __table_args__ = (Index("ix_tour_changes_tour", "tour_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    key_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    before: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    after: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class TourInvitation(Base):
    __tablename__ = "tour_invitations"
    __table_args__ = (
        CheckConstraint("state IN ('PENDING', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'CLOSED')", name="ck_tour_invitations_state"),
        Index("one_pending_invitation", "tour_id", "invitee_id", unique=True, postgresql_where=text("state = 'PENDING'")),
        Index("one_declined_invitation", "tour_id", "invitee_id", unique=True, postgresql_where=text("state = 'DECLINED'")),
        Index("ix_tour_invitations_invitee", "invitee_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False)
    invitee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    inviter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    state: Mapped[str] = mapped_column(String(10), nullable=False, default="PENDING", server_default="PENDING")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InvitationOptOut(Base):
    """"Don't invite me again" for one organiser (spec 11.6)."""

    __tablename__ = "invitation_optouts"
    __table_args__ = (PrimaryKeyConstraint("invitee_id", "organiser_id", name="invitation_optouts_pkey"),)

    invitee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organiser_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class TravelPreferences(Base):
    __tablename__ = "travel_preferences"
    __table_args__ = (
        CheckConstraint("style IS NULL OR style IN " + _in(STYLES), name="ck_travel_preferences_style"),
        CheckConstraint("pace IS NULL OR pace IN " + _in(PACES), name="ck_travel_preferences_pace"),
        CheckConstraint("smoking IS NULL OR smoking IN ('NO', 'OUTDOORS', 'YES')", name="ck_travel_preferences_smoking"),
        CheckConstraint("budget_min_bdt IS NULL OR budget_max_bdt IS NULL OR budget_max_bdt >= budget_min_bdt", name="ck_travel_preferences_budget"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    date_ranges: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False, default=list)  # up to 3 [{from, to}]
    flexible_dates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    budget_min_bdt: Mapped[int | None] = mapped_column(Integer)
    budget_max_bdt: Mapped[int | None] = mapped_column(Integer)
    destinations: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default=text("'{}'::uuid[]"))
    regions: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False, default=list, server_default=text("'{}'::varchar[]"))
    style: Mapped[str | None] = mapped_column(String(10))
    pace: Mapped[str | None] = mapped_column(String(10))
    activities: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False, default=list, server_default=text("'{}'::varchar[]"))
    languages: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False, default=list, server_default=text("'{}'::varchar[]"))
    smoking: Mapped[str | None] = mapped_column(String(10))
    must_no_smoking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class DiscoverySettings(Base):
    __tablename__ = "discovery_settings"
    __table_args__ = (CheckConstraint("audience IN ('ALL', 'WOMEN', 'MEN')", name="ck_discovery_settings_audience"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    discoverable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    audience: Mapped[str] = mapped_column(String(6), nullable=False, default="ALL", server_default="ALL")
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class AbuseSignal(Base):
    """A limit was hit or a pattern seen (architecture 10.3): shown in Tour Operations monitoring."""

    __tablename__ = "abuse_signals"
    __table_args__ = (Index("ix_abuse_signals_created", "created_at"), Index("ix_abuse_signals_user_kind", "user_id", "kind", "created_at"))

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


# ---- chat (14; architecture 5.4, 8) ----


class ChatChannel(Base):
    __tablename__ = "chat_channels"

    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), primary_key=True)
    last_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        PrimaryKeyConstraint("tour_id", "seq", name="chat_messages_pkey"),
        CheckConstraint("kind IN ('TEXT', 'SYSTEM', 'ANNOUNCEMENT')", name="ck_chat_messages_kind"),
        CheckConstraint("body IS NULL OR char_length(body) <= 2000", name="ck_chat_messages_body"),
        UniqueConstraint("id", name="uq_chat_messages_id"),
        Index("uq_chat_messages_client", "tour_id", "sender_id", "client_msg_id", unique=True, postgresql_where=text("client_msg_id IS NOT NULL")),
    )

    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    sender_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    client_msg_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(12), nullable=False, default="TEXT", server_default="TEXT")
    body: Mapped[str | None] = mapped_column(Text)
    reply_to: Mapped[int | None] = mapped_column(BigInteger)
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hidden_by_staff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    held_for_report: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ChatRead(Base):
    __tablename__ = "chat_reads"
    __table_args__ = (PrimaryKeyConstraint("tour_id", "user_id", name="chat_reads_pkey"),)

    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    last_read_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    muted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))


# ---- workspace: itinerary and budget (13.1, 13.3) ----


class ItineraryItem(Base):
    __tablename__ = "itinerary_items"
    __table_args__ = (
        CheckConstraint("kind IN ('STOP', 'TRANSPORT', 'STAY', 'NOTE')", name="ck_itinerary_items_kind"),
        CheckConstraint("day BETWEEN 1 AND 31", name="ck_itinerary_items_day"),
        Index("ix_itinerary_items_tour", "tour_id", "day", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False)
    day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default="0")
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="STOP", server_default="STOP")
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("destinations.id", ondelete="SET NULL"))
    starts_at: Mapped[time | None] = mapped_column(Time)
    notes: Mapped[str | None] = mapped_column(String(500))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ItinerarySuggestion(Base):
    __tablename__ = "itinerary_suggestions"
    __table_args__ = (CheckConstraint("state IN ('PENDING', 'ACCEPTED', 'REJECTED')", name="ck_itinerary_suggestions_state"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    proposal: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(String(10), nullable=False, default="PENDING", server_default="PENDING")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class Expense(Base):
    """Amounts are integer paisa (1 taka = 100 paisa), never floats. No money moves (13.3, SRS C3)."""

    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount_paisa > 0", name="ck_expenses_amount"),
        CheckConstraint("category IN ('TRANSPORT', 'STAY', 'FOOD', 'ENTRY', 'OTHER')", name="ck_expenses_category"),
        Index("ix_expenses_tour", "tour_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    paid_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount_paisa: Mapped[int] = mapped_column(BigInteger, nullable=False)
    category: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    settled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ExpenseShare(Base):
    __tablename__ = "expense_shares"
    __table_args__ = (PrimaryKeyConstraint("expense_id", "user_id", name="expense_shares_pkey"), CheckConstraint("share_paisa >= 0", name="ck_expense_shares_share"))

    expense_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    share_paisa: Mapped[int] = mapped_column(BigInteger, nullable=False)


SHARES_SUM = """
CREATE OR REPLACE FUNCTION expense_shares_add_up() RETURNS trigger LANGUAGE plpgsql SET search_path = public AS $$
DECLARE target uuid; total bigint; amount bigint; gone timestamptz;
BEGIN
  target := COALESCE(NEW.expense_id, OLD.expense_id);
  SELECT e.amount_paisa, e.deleted_at INTO amount, gone FROM expenses e WHERE e.id = target;
  IF amount IS NULL OR gone IS NOT NULL THEN RETURN NULL; END IF;
  SELECT COALESCE(SUM(s.share_paisa), 0) INTO total FROM expense_shares s WHERE s.expense_id = target;
  IF total <> amount THEN
    -- SQLAlchemy DDL performs %-substitution before sending this block to
    -- PostgreSQL, so PL/pgSQL's RAISE placeholders must be escaped here.
    RAISE EXCEPTION 'expense shares (%%) must add up to the amount (%%)', total, amount USING ERRCODE = 'check_violation';
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER expense_shares_add_up AFTER INSERT OR UPDATE OR DELETE ON expense_shares
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION expense_shares_add_up();
"""
event.listen(ExpenseShare.__table__, "after_create", DDL(SHARES_SUM))  # type: ignore[no-untyped-call]


class ExpenseHistory(Base):
    __tablename__ = "expense_history"
    __table_args__ = (Index("ix_expense_history_expense", "expense_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expense_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    before: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    after: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class Settlement(Base):
    """A member marked a transfer as paid outside Abhijatri (bKash, cash)."""

    __tablename__ = "settlements"
    __table_args__ = (CheckConstraint("amount_paisa > 0", name="ck_settlements_amount"), CheckConstraint("from_user <> to_user", name="ck_settlements_parties"))

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False, index=True)
    from_user: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    to_user: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount_paisa: Mapped[int] = mapped_column(BigInteger, nullable=False)
    marked_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


# ---- safety (13.4) ----


class SafetyProfile(Base):
    """A member's emergency contact and medical notes for one tour, each sealed separately."""

    __tablename__ = "safety_profiles"

    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tour_members.id", ondelete="CASCADE"), primary_key=True)
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_sealed: Mapped[bytes | None] = mapped_column(LargeBinary)
    medical_sealed: Mapped[bytes | None] = mapped_column(LargeBinary)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class MeetingPoint(Base):
    __tablename__ = "meeting_points"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    meet_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    map_url: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class CheckIn(Base):
    __tablename__ = "checkins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    message: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class CheckInAnswer(Base):
    __tablename__ = "checkin_answers"
    __table_args__ = (PrimaryKeyConstraint("checkin_id", "user_id", name="checkin_answers_pkey"),)

    checkin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("checkins.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class SosEvent(Base):
    __tablename__ = "sos_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False, index=True)
    raised_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    message: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---- operations (16) ----


class TourReport(Base):
    """A report about a tour, a member, a request, an invitation or a chat message. Chat reports keep a
    snapshot of the message and the 20 around it, so evidence survives deletion (14.1.6, architecture 8.5)."""

    __tablename__ = "tour_reports"
    __table_args__ = (
        CheckConstraint("subject_kind IN ('TOUR', 'MEMBER', 'REQUEST', 'INVITATION', 'MESSAGE', 'REMOVAL', 'SAFETY')", name="ck_tour_reports_subject"),
        CheckConstraint("state IN ('open', 'in_review', 'actioned', 'dismissed')", name="ck_tour_reports_state"),
        Index("ix_tour_reports_tour", "tour_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False)
    reporter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    subject_kind: Mapped[str] = mapped_column(String(12), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reason_code: Mapped[str] = mapped_column(String(40), nullable=False)
    details: Mapped[str | None] = mapped_column(String(1000))
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String(12), nullable=False, default="open", server_default="open")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class BreakglassGrant(Base):
    """Time-limited staff access to a tour's private content (16.3): 60 minutes, or 24 hours after an SOS."""

    __tablename__ = "breakglass_grants"
    __table_args__ = (Index("ix_breakglass_grants_tour", "tour_id", "expires_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    scope: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False, default=list, server_default=text("'{}'::varchar[]"))
    via: Mapped[str] = mapped_column(String(10), nullable=False, default="request", server_default="request")
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    organisers_told_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TourStaffAction(Base):
    """A pending second approval for cancelling a Confirmed tour (architecture 10.6, two-person rule)."""

    __tablename__ = "tour_staff_actions"
    __table_args__ = (
        CheckConstraint("action IN ('cancel')", name="ck_tour_staff_actions_action"),
        CheckConstraint("state IN ('pending', 'done', 'refused')", name="ck_tour_staff_actions_state"),
        Index("one_pending_staff_action", "tour_id", "action", unique=True, postgresql_where=text("state = 'pending'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(60), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    state: Mapped[str] = mapped_column(String(8), nullable=False, default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
