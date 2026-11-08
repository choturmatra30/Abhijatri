"""Tours: creation, publishing, joining, approval with automatic confirmation, leaving, organiser tools and the
time-based transitions (Verified Users Interface 5 to 8, 12, 13; architecture 6, 7).

Every state change locks the tour row first (``policy.locked_tour``), so concurrent approvals for one tour run
one after another and the same lock order is used everywhere. The approval transaction (architecture 6.1)
inserts the member, moves the seat counter, confirms the tour when the minimum is reached, marks it Full and
closes pending requests at the maximum, and writes the outbox and audit events, all in one transaction.
"""

import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import fieldcrypt
from app.admin import audit
from app.config import get_settings
from app.errors import ApiError
from app.models import Destination, DestinationAdvisory, DestinationStatus, User
from app.notify import events
from app.tours import policy
from app.tours.models import (
    ACTIVITIES,
    PACES,
    POLICIES,
    RULES,
    STYLES,
    TRANSPORTS,
    AbuseSignal,
    ChatChannel,
    ChatMessage,
    Tour,
    TourChange,
    TourDestination,
    TourInvitation,
    TourJoinRequest,
    TourMember,
)
from app.tours.policy import Viewer, dhaka_today, now, start_instant

KEY_FIELDS = ("start_date", "end_date", "destinations", "min_members", "max_members", "policy")
DECLINE_CODES = {
    "NOT_A_FIT": ("এই ট্যুরের পরিকল্পনার সাথে মিলছে না", "Not a fit for this tour's plan"),
    "GROUP_COMPOSITION": ("দলের গঠন বিবেচনায় এবার সম্ভব নয়", "Not possible this time because of the group's make-up"),
    "DATES": ("তারিখ বা সময় মিলছে না", "Dates or timing do not match"),
    "OTHER": ("আয়োজক এবার নিতে পারছেন না", "The organisers can't take you this time"),
}
REMOVAL_CODES = ("NO_SHOW", "RULE_BREAK", "SAFETY", "PLAN_CHANGED", "OTHER")
AGE_BANDS = ("0-5", "6-12", "13-17")
BUDGET_INCLUDES = ("TRANSPORT", "STAY", "FOOD", "ENTRY")


def _invalid(field: str, code: str) -> ApiError:
    return ApiError("VALIDATION_FAILED", field_errors=[{"field": field, "code": code}])


def _signal(session: Session, user_id: uuid.UUID | None, kind: str, **detail: Any) -> None:
    session.add(AbuseSignal(user_id=user_id, kind=kind, detail={k: str(v) for k, v in detail.items()}))


def _emit(session: Session, topic: str, tour: Tour, payload: dict[str, Any], *, dedupe_key: str | None = None) -> bool:
    body = {"public_id": tour.public_id, "tour_title": tour.title, **payload}
    return events.emit(session, topic, tour.id, body, aggregate_type="tour", aggregate_version=tour.version, dedupe_key=dedupe_key)


def _record(session: Session, viewer_id: uuid.UUID | None, tour: Tour, action: str, **metadata: Any) -> None:
    session.add(TourChange(tour_id=tour.id, actor_id=viewer_id, kind=action, before={}, after={k: str(v) for k, v in metadata.items()}))


def organiser_ids(session: Session, tour_id: uuid.UUID) -> list[str]:
    return [
        str(i)
        for i in session.scalars(
            select(TourMember.user_id).where(TourMember.tour_id == tour_id, TourMember.state == "ACTIVE", TourMember.role.in_(policy.ORGANISER_ROLES))
        )
    ]


def member_ids(session: Session, tour_id: uuid.UUID) -> list[str]:
    return [str(i) for i in policy.active_member_ids(session, tour_id)]


def system_message(session: Session, tour: Tour, body: str) -> None:
    """A system line in the tour chat ("Rafi joined", "Dates changed"), once the chat exists."""
    channel = session.scalar(select(ChatChannel).where(ChatChannel.tour_id == tour.id).with_for_update())
    if channel is None:
        return
    channel.last_seq += 1
    session.add(ChatMessage(tour_id=tour.id, seq=channel.last_seq, kind="SYSTEM", body=body[:2000]))
    from app.tours import realtime

    realtime.after_commit(session, tour.id, channel.last_seq)


# ======================================================================================
# drafts and the creation wizard (spec 5)
# ======================================================================================


def _destinations(session: Session, ids: list[Any]) -> list[Destination]:
    if not ids or len(ids) > 10:
        raise _invalid("destinations", "REQUIRED" if not ids else "TOO_MANY")
    parsed: list[uuid.UUID] = []
    for raw in ids:
        try:
            parsed.append(uuid.UUID(str(raw)))
        except ValueError as error:
            raise _invalid("destinations", "INVALID_UUID") from error
    if len(set(parsed)) != len(parsed):
        raise _invalid("destinations", "DUPLICATE")
    rows = {d.id: d for d in session.scalars(select(Destination).where(Destination.id.in_(parsed), Destination.status == DestinationStatus.PUBLISHED))}
    if len(rows) != len(parsed):
        raise _invalid("destinations", "NOT_PUBLISHED")
    return [rows[i] for i in parsed]


def _clean_text(value: Any, limit: int) -> str:
    """Spec 5.2: no phone numbers or links in public text; the creator uses the workspace for those."""
    import re

    text = str(value or "").strip()
    text = re.sub(r"https?://\S+|www\.\S+", "[link removed]", text)
    text = re.sub(r"(?:\+?88)?0?1[3-9]\d{2}[\s-]?\d{6}", "[number removed]", text)
    return text[:limit]


def _enum(value: Any, allowed: tuple[str, ...], field: str, required: bool = False) -> str | None:
    if value in (None, ""):
        if required:
            raise _invalid(field, "REQUIRED")
        return None
    if value not in allowed:
        raise _invalid(field, "INVALID_VALUE")
    return str(value)


def _enum_list(values: Any, allowed: tuple[str, ...], field: str, limit: int = 10) -> list[str]:
    items = list(values or [])
    if len(items) > limit or any(v not in allowed for v in items):
        raise _invalid(field, "INVALID_VALUE")
    return list(dict.fromkeys(items))


def _apply_fields(session: Session, tour: Tour, body: dict[str, Any], *, creating: bool) -> dict[str, Any]:
    """Validates and applies wizard fields; returns {field: (before, after)} for key details."""
    changes: dict[str, Any] = {}
    if "title" in body or creating:
        title = _clean_text(body.get("title"), 80)
        if not 8 <= len(title) <= 80:
            raise _invalid("title", "LENGTH")
        tour.title = title
    if "description" in body:
        tour.description = _clean_text(body.get("description"), 1000)
    if "destinations" in body or creating:
        found = _destinations(session, list(body.get("destinations") or []))
        before = [str(d.destination_id) for d in session.scalars(select(TourDestination).where(TourDestination.tour_id == tour.id).order_by(TourDestination.position))] if tour.id else []
        after = [str(d.id) for d in found]
        if before != after:
            changes["destinations"] = (before, after)
            session.flush()
            for row in session.scalars(select(TourDestination).where(TourDestination.tour_id == tour.id)):
                session.delete(row)
            session.flush()
            for position, destination in enumerate(found):
                session.add(TourDestination(tour_id=tour.id, position=position, destination_id=destination.id))
    for field in ("start_date", "end_date"):
        if field in body or creating:
            try:
                parsed_date = date.fromisoformat(str(body.get(field) or ""))
            except ValueError as error:
                raise _invalid(field, "INVALID_FORMAT") from error
            if getattr(tour, field, None) != parsed_date:
                changes[field] = (str(getattr(tour, field, None)), str(parsed_date))
            setattr(tour, field, parsed_date)
    if tour.end_date < tour.start_date or (tour.end_date - tour.start_date).days > 30:
        raise _invalid("end_date", "OUT_OF_RANGE")
    if "recruit_deadline" in body:
        try:
            deadline = datetime.fromisoformat(str(body["recruit_deadline"]))
        except ValueError as error:
            raise _invalid("recruit_deadline", "INVALID_FORMAT") from error
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=get_settings().display_tz)
        tour.recruit_deadline = deadline
    elif creating or "start_date" in changes:
        tour.recruit_deadline = start_instant(tour.start_date) - timedelta(days=3)  # default: 3 days before (5.1)
    if tour.recruit_deadline > start_instant(tour.start_date) - timedelta(hours=24):
        raise _invalid("recruit_deadline", "TOO_LATE")  # AC-03
    for field, low in (("min_members", 2), ("max_members", 2)):
        if field in body:
            member_limit = int(body[field])
            if not low <= member_limit <= 30:
                raise _invalid(field, "OUT_OF_RANGE")  # AC-03
            if getattr(tour, field) != member_limit:
                changes[field] = (getattr(tour, field), member_limit)
            setattr(tour, field, member_limit)
    if tour.max_members < tour.min_members:
        raise _invalid("max_members", "BELOW_MINIMUM")
    if tour.max_members < tour.seats_taken:
        raise _invalid("max_members", "BELOW_CURRENT")  # 7.6.4
    if "policy" in body or creating:
        selected_policy = _enum(body.get("policy") or "OPEN", POLICIES, "policy", required=True)
        if tour.policy != selected_policy:
            changes["policy"] = (tour.policy, selected_policy)
        tour.policy = str(selected_policy)
    if "join_question" in body:
        tour.join_question = _clean_text(body.get("join_question"), 200) or None
    if "rules" in body:
        tour.rules = _enum_list(body.get("rules"), RULES, "rules")
    if "custom_rules" in body:
        lines = [_clean_text(line, 120) for line in (body.get("custom_rules") or []) if str(line).strip()]
        if len(lines) > 5:
            raise _invalid("custom_rules", "TOO_MANY")
        tour.custom_rules = lines
    for field in ("budget_min_bdt", "budget_max_bdt"):
        if field in body:
            budget_value = body.get(field)
            if budget_value is not None and not (0 <= int(budget_value) <= 1_000_000):
                raise _invalid(field, "OUT_OF_RANGE")
            setattr(tour, field, int(budget_value) if budget_value is not None else None)
    if tour.budget_min_bdt is not None and tour.budget_max_bdt is not None and tour.budget_max_bdt < tour.budget_min_bdt:
        raise _invalid("budget_max_bdt", "BELOW_MINIMUM")
    if "budget_includes" in body:
        tour.budget_includes = _enum_list(body.get("budget_includes"), BUDGET_INCLUDES, "budget_includes")
    if "style" in body:
        tour.style = _enum(body.get("style"), STYLES, "style")
    if "pace" in body:
        tour.pace = _enum(body.get("pace"), PACES, "pace")
    if "transport" in body:
        tour.transport = _enum(body.get("transport"), TRANSPORTS, "transport")
    if "activities" in body:
        tour.activities = _enum_list(body.get("activities"), ACTIVITIES, "activities")
    if "departure_city" in body:
        tour.departure_city = _clean_text(body.get("departure_city"), 60) or None
    if "meeting_area" in body:
        tour.meeting_area = _clean_text(body.get("meeting_area"), 120) or None
    if "itinerary_outline" in body:
        tour.itinerary_outline = str(body.get("itinerary_outline") or "")[:2000] or None
    return changes


def _limits(session: Session, viewer: Viewer, *, drafts: bool) -> None:
    settings = get_settings()
    if drafts:
        count = session.scalar(select(func.count()).select_from(Tour).where(Tour.creator_id == viewer.user_id, Tour.lifecycle == "DRAFT")) or 0
        if count >= settings.tours_drafts_per_user:
            raise ApiError("TOUR_LIMIT_REACHED")
    else:
        count = session.scalar(
            select(func.count()).select_from(Tour).where(Tour.creator_id == viewer.user_id, Tour.lifecycle.in_(policy.OPEN_LIFECYCLES))
        ) or 0
        if count >= settings.tours_active_per_user:
            raise ApiError("TOUR_LIMIT_REACHED")


def create_draft(session: Session, viewer: Viewer, body: dict[str, Any]) -> Tour:
    policy.require_unrestricted(viewer)
    _limits(session, viewer, drafts=True)
    today = dhaka_today()
    tour = Tour(
        id=uuid.uuid4(), public_id=policy.new_public_id(today.year), creator_id=viewer.user_id, lifecycle="DRAFT",
        start_date=today + timedelta(days=14), end_date=today + timedelta(days=16), recruit_deadline=start_instant(today + timedelta(days=11)),
        policy="OPEN", seats_taken=1, title="",
    )
    session.add(tour)
    body = {"start_date": tour.start_date.isoformat(), "end_date": tour.end_date.isoformat(), **body}
    _apply_fields(session, tour, body, creating=True)
    session.add(TourMember(tour_id=tour.id, user_id=viewer.user_id, role="CREATOR", joined_via="CREATED"))
    for _ in range(5):
        try:
            with session.begin_nested():
                session.flush()
            break
        except IntegrityError:
            tour.public_id = policy.new_public_id(today.year)  # retried on the rare collision (architecture 10.3)
    audit.record(session, actor=None, action="tour.created", target_type="tour", target_id=tour.id, metadata={"by": str(viewer.user_id)})
    return tour


def update_draft(session: Session, viewer: Viewer, tour: Tour, body: dict[str, Any], expected_version: int | None) -> Tour:
    member = policy.require(policy.membership(session, tour.id, viewer.user_id), "tour.edit_basics")
    if expected_version is not None and expected_version != tour.version:
        raise ApiError("STALE_VERSION")
    if tour.suspended_at is not None:
        raise ApiError("TOUR_SUSPENDED")
    if tour.lifecycle == "DRAFT":
        _apply_fields(session, tour, body, creating=False)
    else:
        if tour.lifecycle not in policy.LIVE_LIFECYCLES:
            raise ApiError("TRANSITION_NOT_ALLOWED")
        key = [field for field in KEY_FIELDS if field in body] + (["recruit_deadline"] if "recruit_deadline" in body else [])
        if key and member.role != "CREATOR":
            raise ApiError("FORBIDDEN")  # 13.2: only the creator changes dates, destinations, size, policy
        if tour.lifecycle == "ONGOING" and {"start_date", "end_date"} & set(body):
            raise ApiError("TRANSITION_NOT_ALLOWED")  # 7.6.5
        if "policy" in body and _stricter(tour.policy, str(body["policy"])) and _has_tourmates(session, tour):
            raise _invalid("policy", "STRICTER_WITH_MEMBERS")  # 6.4
        before_policy = tour.policy
        changes = _apply_fields(session, tour, body, creating=False)
        if "policy" in changes and not policy.eligible(policy.viewer_for(session, tour.creator_id), tour.policy, tour.start_date):
            raise ApiError("POLICY_NOT_MET")
        if changes:
            _key_change(session, viewer, tour, changes, before_policy)
        # Changing a live tour's minimum or maximum must immediately update
        # confirmation/At-Risk/Full state using the same invariant-preserving
        # path as an approval or departure.
        _after_seats_change(session, tour)
    tour.version += 1
    tour.updated_at = now()
    session.add(TourChange(tour_id=tour.id, actor_id=viewer.user_id, kind="edited", before={}, after={k: "changed" for k in body}))
    return tour


def _stricter(old: str, new: str) -> bool:
    """6.4: Open and Family groups admit everyone; any other policy narrows who may join."""
    return old != new and new not in ("OPEN", "FAMILY")


def _has_tourmates(session: Session, tour: Tour) -> bool:
    return session.scalar(select(TourMember.id).where(TourMember.tour_id == tour.id, TourMember.state == "ACTIVE", TourMember.role == "TOURMATE").limit(1)) is not None


def _key_change(session: Session, viewer: Viewer, tour: Tour, changes: dict[str, Any], before_policy: str) -> None:
    """7.6: everyone is told with a before-and-after view and gets 72 hours to leave without a mark."""
    session.add(
        TourChange(
            tour_id=tour.id, actor_id=viewer.user_id, kind="key_details", key_change=True,
            before={k: v[0] for k, v in changes.items()}, after={k: v[1] for k, v in changes.items()},
        )
    )
    if _has_tourmates(session, tour):
        tour.change_window_until = now() + timedelta(hours=72)
        _emit(session, "tour.key_details_changed", tour, {"member_ids": member_ids(session, tour.id), "fields": sorted(changes)})
        system_message(session, tour, "Key details changed: " + ", ".join(sorted(changes)) + ". You can leave within 72 hours without any mark.")


def publish(session: Session, viewer: Viewer, tour: Tour, *, accept_rules: bool) -> Tour:
    policy.require(policy.membership(session, tour.id, viewer.user_id), "tour.cancel")
    policy.require_unrestricted(viewer)
    if tour.lifecycle != "DRAFT":
        raise ApiError("TRANSITION_NOT_ALLOWED")
    if not accept_rules:
        raise _invalid("accept_rules", "REQUIRED")
    if not policy.eligible(viewer, tour.policy, tour.start_date):
        raise ApiError("POLICY_NOT_MET")  # 6.1: a man cannot create a Women-only tour
    today = dhaka_today()
    if tour.start_date < today + timedelta(days=3):
        raise _invalid("start_date", "TOO_SOON")  # 5.1: at least 3 days to recruit
    if tour.recruit_deadline <= now():
        raise _invalid("recruit_deadline", "IN_THE_PAST")
    if not session.scalar(select(TourDestination.tour_id).where(TourDestination.tour_id == tour.id).limit(1)):
        raise _invalid("destinations", "REQUIRED")
    _limits(session, viewer, drafts=False)
    published_today = session.scalar(
        select(func.count()).select_from(Tour).where(Tour.creator_id == viewer.user_id, Tour.published_at > now() - timedelta(days=1))
    ) or 0
    if published_today >= get_settings().tours_publish_per_day:
        _signal(session, viewer.user_id, "publish_limit")
        raise ApiError("RATE_LIMITED", headers={"Retry-After": "86400"})
    overlap = _overlapping(session, viewer.user_id, tour.start_date, tour.end_date, exclude=tour.id, creator_only=True)
    if overlap:
        raise ApiError("DATE_OVERLAP")  # 5.2: two tours by the same creator may not overlap
    tour.lifecycle, tour.recruitment, tour.recruitment_choice = "RECRUITING", "OPEN", "OPEN"
    tour.published_at = tour.accepted_rules_at = now()
    tour.code = _unique_code(session)
    tour.version += 1
    _record(session, viewer.user_id, tour, "published")
    _emit(session, "tour.published", tour, {"creator_id": str(viewer.user_id)})
    audit.record(session, actor=None, action="tour.published", target_type="tour", target_id=tour.id)
    return tour


def _unique_code(session: Session) -> str:
    for _ in range(10):
        code = policy.new_code()
        if session.scalar(select(Tour.id).where(Tour.code == code)) is None:
            return code
    raise ApiError("SERVICE_UNAVAILABLE")


def delete_draft(session: Session, viewer: Viewer, tour: Tour) -> None:
    if tour.lifecycle != "DRAFT" or tour.creator_id != viewer.user_id:
        raise ApiError("TRANSITION_NOT_ALLOWED")
    session.delete(tour)


def copy_to_draft(session: Session, viewer: Viewer, source: Tour) -> Tour:
    """7.4.6: a cancelled tour copied into a new draft in one tap."""
    if source.creator_id != viewer.user_id:
        raise ApiError("NOT_FOUND")
    destinations = [str(d.destination_id) for d in session.scalars(select(TourDestination).where(TourDestination.tour_id == source.id).order_by(TourDestination.position))]
    length = (source.end_date - source.start_date).days
    start = max(dhaka_today() + timedelta(days=14), source.start_date)
    body = {
        "title": source.title, "description": source.description, "destinations": destinations, "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=length)).isoformat(), "policy": source.policy, "min_members": source.min_members,
        "max_members": source.max_members, "rules": source.rules, "custom_rules": source.custom_rules, "join_question": source.join_question,
        "budget_min_bdt": source.budget_min_bdt, "budget_max_bdt": source.budget_max_bdt, "budget_includes": source.budget_includes,
        "style": source.style, "pace": source.pace, "transport": source.transport, "activities": source.activities,
        "departure_city": source.departure_city, "meeting_area": source.meeting_area,
    }
    return create_draft(session, viewer, body)


# ======================================================================================
# requests and approval (spec 8; architecture 6.1)
# ======================================================================================


def _overlapping(session: Session, user_id: uuid.UUID, start: date, end: date, *, exclude: uuid.UUID | None = None, creator_only: bool = False) -> bool:
    statement = (
        select(Tour.id)
        .join(TourMember, TourMember.tour_id == Tour.id)
        .where(
            TourMember.user_id == user_id, TourMember.state == "ACTIVE", Tour.lifecycle.in_(policy.LIVE_LIFECYCLES),
            Tour.start_date <= end, Tour.end_date >= start,
        )
    )
    if creator_only:
        statement = statement.where(TourMember.role == "CREATOR")
    if exclude is not None:
        statement = statement.where(Tour.id != exclude)
    return session.scalar(statement.limit(1)) is not None


def _seal_companions(companions: list[dict[str, Any]] | None, aad: str) -> tuple[int, bytes | None]:
    """8.3: up to 4 named under-18 companions on a Family groups request; each takes a seat."""
    if not companions:
        return 1, None
    if len(companions) > 4:
        raise _invalid("companions", "TOO_MANY")
    clean = []
    for item in companions:
        first = str(item.get("first_name") or "").strip()[:40]
        band = item.get("age_band")
        relationship = str(item.get("relationship") or "").strip()[:30]
        if len(first) < 1 or band not in AGE_BANDS or len(relationship) < 2:
            raise _invalid("companions", "INVALID_VALUE")
        clean.append({"first_name": first, "age_band": band, "relationship": relationship})
    return 1 + len(clean), fieldcrypt.seal(json.dumps(clean, ensure_ascii=False), aad=aad)


def open_companions(blob: bytes | None, aad: str) -> list[dict[str, str]]:
    if not blob:
        return []
    try:
        decoded = json.loads(fieldcrypt.open_text(blob, aad=aad) or "[]")
        if not isinstance(decoded, list) or not all(isinstance(item, dict) for item in decoded):
            return []
        return [{str(key): str(value) for key, value in item.items()} for item in decoded]
    except (fieldcrypt.SealError, ValueError):
        return []


def request_blockers(session: Session, viewer: Viewer, tour: Tour, *, via_code: bool) -> str | None:
    """Why this viewer cannot request this tour right now, or None (spec 8.2). Shown to the requester only
    as a stable code; who blocked whom is never revealed."""
    if tour.lifecycle not in policy.OPEN_LIFECYCLES or tour.suspended_at is not None:
        return "RECRUITMENT_CLOSED"
    if tour.recruitment != "OPEN":
        return "TOUR_FULL" if tour.recruitment == "FULL" else "RECRUITMENT_CLOSED"
    if now() >= tour.recruit_deadline:
        return "DEADLINE_PASSED"
    if tour.policy == "INVITE_ONLY" and not via_code:
        return "REQUEST_NOT_ALLOWED"
    if not policy.eligible(viewer, tour.policy, tour.start_date):
        return "POLICY_NOT_MET"
    member = session.scalar(select(TourMember).where(TourMember.tour_id == tour.id, TourMember.user_id == viewer.user_id).order_by(TourMember.joined_at.desc()).limit(1))
    if member is not None:
        return "ALREADY_MEMBER" if member.state in ("ACTIVE", "INACTIVE") else "REQUEST_NOT_ALLOWED"  # 7.5: left or removed
    if policy.blocked_between(session, viewer.user_id, policy.active_member_ids(session, tour.id)):
        return "REQUEST_NOT_ALLOWED"  # AC-11
    if _overlapping(session, viewer.user_id, tour.start_date, tour.end_date):
        return "DATE_OVERLAP"
    declined = session.scalar(
        select(TourJoinRequest.decided_at).where(
            TourJoinRequest.tour_id == tour.id, TourJoinRequest.user_id == viewer.user_id, TourJoinRequest.state == "DECLINED"
        ).order_by(TourJoinRequest.decided_at.desc()).limit(1)
    )
    if declined is not None and now() - declined < timedelta(days=7):
        return "REQUEST_COOLDOWN"
    return None


def create_request(
    session: Session, viewer: Viewer, tour: Tour, *, answer: str | None, message: str | None, accept_rules: bool,
    companions: list[dict[str, Any]] | None, code: str | None,
) -> TourJoinRequest:
    settings = get_settings()
    policy.require_unrestricted(viewer)
    if not accept_rules:
        raise _invalid("accept_rules", "REQUIRED")
    via_code = code is not None and tour.code is not None and policy.normalise_code(code) == tour.code
    blocker = request_blockers(session, viewer, tour, via_code=via_code)
    if blocker:
        raise ApiError(blocker)
    if tour.join_question and not (answer or "").strip():
        raise _invalid("answer", "REQUIRED")
    if companions and tour.policy != "FAMILY":
        raise _invalid("companions", "NOT_ALLOWED")
    pending = session.scalar(select(func.count()).select_from(TourJoinRequest).where(TourJoinRequest.user_id == viewer.user_id, TourJoinRequest.state == "PENDING")) or 0
    if pending >= settings.tour_requests_pending_total:
        raise ApiError("RATE_LIMITED", headers={"Retry-After": "3600"})  # AC-10
    today = session.scalar(
        select(func.count()).select_from(TourJoinRequest).where(TourJoinRequest.user_id == viewer.user_id, TourJoinRequest.created_at > now() - timedelta(days=1))
    ) or 0
    if today >= settings.tour_requests_per_day:
        _signal(session, viewer.user_id, "mass_requests", count=today)
        raise ApiError("RATE_LIMITED", headers={"Retry-After": "86400"})
    request = TourJoinRequest(
        id=uuid.uuid4(), tour_id=tour.id, user_id=viewer.user_id, answer=(answer or "").strip()[:500] or None,
        message=(message or "").strip()[:300] or None, via_code=via_code,
    )
    request.seats, request.companions_sealed = _seal_companions(companions, f"tour_request:{request.id}")
    session.add(request)
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError as error:
        raise ApiError("REQUEST_NOT_ALLOWED") from error  # AC-10: one pending request per tour
    _emit(session, "tour.request_created", tour, {"organiser_ids": organiser_ids(session, tour.id), "request_id": str(request.id)})
    return request


def withdraw_request(session: Session, viewer: Viewer, request_id: uuid.UUID) -> TourJoinRequest:
    request = session.scalar(select(TourJoinRequest).where(TourJoinRequest.id == request_id).with_for_update())
    if request is None or request.user_id != viewer.user_id:
        raise ApiError("NOT_FOUND")
    if request.state != "PENDING":
        raise ApiError("TRANSITION_NOT_ALLOWED")
    request.state, request.decided_at = "WITHDRAWN", now()
    return request


def requester_problem(session: Session, tour: Tour, user_id: uuid.UUID, seats: int) -> str | None:
    """The exact reason an approval is refused, shown to the organiser (8.2)."""
    person = policy.viewer_for(session, user_id)
    if not person.verified:
        return "LOST_VERIFICATION"
    if not person.adult:
        return "UNDER_18"
    if person.restricted:
        return "RESTRICTED"
    if not policy.eligible(person, tour.policy, tour.start_date):
        return "POLICY_NOT_MET"
    if policy.blocked_between(session, user_id, policy.active_member_ids(session, tour.id)):
        return "BLOCKED"
    if _overlapping(session, user_id, tour.start_date, tour.end_date, exclude=tour.id):
        return "DATE_OVERLAP"
    if tour.seats_taken + seats > tour.max_members:
        return "NO_SEATS"
    return None


def _guard_open_for_members(tour: Tour) -> None:
    if tour.suspended_at is not None:
        raise ApiError("TOUR_SUSPENDED")
    if tour.lifecycle not in policy.OPEN_LIFECYCLES:
        raise ApiError("RECRUITMENT_CLOSED")
    if tour.recruitment not in ("OPEN", "PAUSED"):  # PAUSED: pending ones may still be approved
        raise ApiError("TOUR_FULL" if tour.recruitment == "FULL" else "RECRUITMENT_CLOSED")
    if now() >= tour.recruit_deadline:
        raise ApiError("DEADLINE_PASSED")


def _join(session: Session, tour: Tour, user_id: uuid.UUID, *, seats: int, companions: bytes | None, via: str, approved_by: uuid.UUID | None) -> TourMember:
    member = TourMember(
        id=uuid.uuid4(), tour_id=tour.id, user_id=user_id, role="TOURMATE", seats=seats, joined_via=via, approved_by=approved_by, companions_sealed=companions,
    )
    session.add(member)
    try:
        with session.begin_nested():
            session.flush()  # the partial unique index stops a double membership
    except IntegrityError as error:
        raise ApiError("ALREADY_MEMBER") from error
    tour.seats_taken += seats
    tour.version += 1
    tour.updated_at = now()
    _after_seats_change(session, tour)
    if tour.confirmed_at is not None:
        from app.tours import safety

        safety.copy_default_contact(session, member)
    user = session.get(User, user_id)
    system_message(session, tour, f"{policy.first_name(user.display_name if user else None)} joined the tour.")
    return member


def _after_seats_change(session: Session, tour: Tour) -> None:
    """Confirmation, At Risk and Full, decided in the same transaction as the seat change (7.4)."""
    if tour.lifecycle == "RECRUITING" and tour.seats_taken >= tour.min_members:
        tour.lifecycle, tour.confirmed_at, tour.is_at_risk = "CONFIRMED", now(), False
        session.add(ChatChannel(tour_id=tour.id, last_seq=0))
        session.flush()
        from app.tours import safety

        for joined in session.scalars(select(TourMember).where(TourMember.tour_id == tour.id, TourMember.state == "ACTIVE")):
            safety.copy_default_contact(session, joined)  # the verification contact, copied into Safety (sign-up form 7)
        system_message(session, tour, "The tour is confirmed. Discussion, budget and safety are open.")
        _emit(session, "tour.confirmed", tour, {"member_ids": member_ids(session, tour.id)})
        audit.record(session, actor=None, action="tour.confirmed", target_type="tour", target_id=tour.id, metadata={"seats": tour.seats_taken})
    elif tour.lifecycle == "CONFIRMED" and tour.is_at_risk and tour.seats_taken >= tour.min_members:
        tour.is_at_risk = False
        _emit(session, "tour.risk_cleared", tour, {"member_ids": member_ids(session, tour.id)})
    elif tour.lifecycle == "CONFIRMED" and not tour.is_at_risk and tour.seats_taken < tour.min_members:
        tour.is_at_risk = True
        _emit(session, "tour.at_risk", tour, {"member_ids": member_ids(session, tour.id)})
    if tour.lifecycle in policy.OPEN_LIFECYCLES:
        if tour.seats_taken >= tour.max_members and tour.recruitment in ("OPEN", "PAUSED"):
            tour.recruitment = "FULL"
            closed = session.execute(
                update(TourJoinRequest)
                .where(TourJoinRequest.tour_id == tour.id, TourJoinRequest.state == "PENDING")
                .values(state="CLOSED", decided_at=now(), decline_code="FILLED_UP")
                .returning(TourJoinRequest.user_id)
            ).scalars().all()
            for user_id in closed:
                _emit(session, "tour.request_closed", tour, {"user_id": str(user_id)})
            session.execute(update(TourInvitation).where(TourInvitation.tour_id == tour.id, TourInvitation.state == "PENDING").values(state="CLOSED", answered_at=now()))
        elif tour.recruitment == "FULL" and tour.seats_taken < tour.max_members:
            tour.recruitment = "EXPIRED" if now() >= tour.recruit_deadline else tour.recruitment_choice  # back to the organiser's choice


def approve_request(session: Session, viewer: Viewer, tour_id: uuid.UUID, request_id: uuid.UUID) -> TourJoinRequest:
    tour = policy.locked_tour(session, tour_id)  # serialises every approval of this tour (AC-07)
    policy.require(policy.membership(session, tour.id, viewer.user_id), "tour.approve")
    policy.require_unrestricted(viewer)
    _guard_open_for_members(tour)
    request = session.scalar(select(TourJoinRequest).where(TourJoinRequest.id == request_id, TourJoinRequest.tour_id == tour.id).with_for_update())
    if request is None:
        raise ApiError("NOT_FOUND")
    if request.state != "PENDING":
        raise ApiError("TRANSITION_NOT_ALLOWED")
    problem = requester_problem(session, tour, request.user_id, request.seats)
    if problem == "NO_SEATS":
        raise ApiError("TOUR_FULL")
    if problem:
        raise ApiError("REQUESTER_NOT_ELIGIBLE", field_errors=[{"field": "requester", "code": problem}])
    companions = request.companions_sealed
    if companions:
        companions = fieldcrypt.seal(json.dumps(open_companions(companions, f"tour_request:{request.id}"), ensure_ascii=False), aad=f"tour_member_companions:{tour.id}:{request.user_id}")
    _join(session, tour, request.user_id, seats=request.seats, companions=companions, via="REQUEST", approved_by=viewer.user_id)
    request.state, request.decided_by, request.decided_at = "APPROVED", viewer.user_id, now()
    _emit(session, "tour.request_approved", tour, {"user_id": str(request.user_id)})
    audit.record(session, actor=None, action="tour.request_approved", target_type="tour", target_id=tour.id, metadata={"request_id": str(request.id), "by": str(viewer.user_id)})
    return request


def decline_request(session: Session, viewer: Viewer, tour_id: uuid.UUID, request_id: uuid.UUID, code: str) -> TourJoinRequest:
    tour = policy.locked_tour(session, tour_id)
    policy.require(policy.membership(session, tour.id, viewer.user_id), "tour.approve")
    if code not in DECLINE_CODES:
        raise _invalid("reason_code", "INVALID_VALUE")
    request = session.scalar(select(TourJoinRequest).where(TourJoinRequest.id == request_id, TourJoinRequest.tour_id == tour.id).with_for_update())
    if request is None:
        raise ApiError("NOT_FOUND")
    if request.state != "PENDING":
        raise ApiError("TRANSITION_NOT_ALLOWED")
    request.state, request.decided_by, request.decided_at, request.decline_code = "DECLINED", viewer.user_id, now(), code
    _emit(session, "tour.request_declined", tour, {"user_id": str(request.user_id)})
    audit.record(session, actor=None, action="tour.request_declined", target_type="tour", target_id=tour.id, metadata={"request_id": str(request.id), "by": str(viewer.user_id)})
    return request


# ======================================================================================
# leaving, removal, organisers (7.5, 13.2)
# ======================================================================================


def _end_membership(session: Session, tour: Tour, member: TourMember, state: str, reason: str | None) -> None:
    was_active = member.state == "ACTIVE"
    member.state, member.left_reason, member.ended_at = state, reason, now()
    if was_active:
        tour.seats_taken = max(0, tour.seats_taken - member.seats)
    tour.version += 1
    _after_seats_change(session, tour)
    from app.tours import realtime

    realtime.revoke(session, tour.id, member.user_id)  # chat access ends at once (8.4; AC-14)


def leave(session: Session, viewer: Viewer, tour_id: uuid.UUID, *, safe_checkout: bool) -> Tour:
    tour = policy.locked_tour(session, tour_id)
    member = policy.membership(session, tour.id, viewer.user_id)
    if member is None:
        raise ApiError("NOT_FOUND")
    if member.role == "CREATOR":
        raise ApiError("OWNER_MUST_TRANSFER")
    if tour.lifecycle not in policy.LIVE_LIFECYCLES:
        raise ApiError("TRANSITION_NOT_ALLOWED")
    if tour.lifecycle == "ONGOING" and not safe_checkout:
        raise _invalid("safe_checkout", "REQUIRED")  # 7.5: "I'm safe and leaving"
    in_window = tour.change_window_until is not None and now() < tour.change_window_until
    reason = "PLAN_CHANGED" if in_window else ("SAFE_CHECKOUT" if tour.lifecycle == "ONGOING" else "LEFT")
    _end_membership(session, tour, member, "LEFT", reason)
    user = session.get(User, viewer.user_id)
    if tour.confirmed_at is not None:
        system_message(session, tour, f"{policy.first_name(user.display_name if user else None)} left the tour.")
    _emit(session, "tour.member_left", tour, {"organiser_ids": organiser_ids(session, tour.id)})
    return tour


def remove_member(session: Session, viewer: Viewer, tour_id: uuid.UUID, member_id: uuid.UUID, reason: str) -> Tour:
    tour = policy.locked_tour(session, tour_id)
    actor = policy.require(policy.membership(session, tour.id, viewer.user_id), "tour.remove_member")
    if reason not in REMOVAL_CODES:
        raise _invalid("reason_code", "INVALID_VALUE")
    target = session.scalar(select(TourMember).where(TourMember.id == member_id, TourMember.tour_id == tour.id).with_for_update())
    if target is None or target.state not in ("ACTIVE", "INACTIVE"):
        raise ApiError("NOT_FOUND")
    if target.role == "CREATOR" or (target.role == "CO_ORGANIZER" and actor.role != "CREATOR"):
        raise ApiError("FORBIDDEN")  # a co-organizer cannot remove another organiser
    _end_membership(session, tour, target, "REMOVED", reason)
    _emit(session, "tour.member_removed", tour, {"user_id": str(target.user_id)})
    audit.record(session, actor=None, action="tour.member_removed", target_type="tour", target_id=tour.id, reason=reason, metadata={"member_id": str(target.id), "by": str(viewer.user_id)})
    return tour


def set_role(session: Session, viewer: Viewer, tour_id: uuid.UUID, member_id: uuid.UUID, role: str) -> TourMember:
    tour = policy.locked_tour(session, tour_id)
    policy.require(policy.membership(session, tour.id, viewer.user_id), "tour.appoint")
    target = session.scalar(select(TourMember).where(TourMember.id == member_id, TourMember.tour_id == tour.id, TourMember.state == "ACTIVE").with_for_update())
    if target is None or target.role == "CREATOR" or role not in ("CO_ORGANIZER", "TOURMATE"):
        raise ApiError("NOT_FOUND")
    if role == "CO_ORGANIZER" and target.role != "CO_ORGANIZER":
        count = session.scalar(select(func.count()).select_from(TourMember).where(TourMember.tour_id == tour.id, TourMember.state == "ACTIVE", TourMember.role == "CO_ORGANIZER")) or 0
        if count >= 3:
            raise _invalid("role", "TOO_MANY_CO_ORGANIZERS")  # 2.2: 0 to 3
    target.role = role
    tour.version += 1
    _record(session, viewer.user_id, tour, "role_changed", member=target.id, role=role)
    return target


def transfer(session: Session, viewer: Viewer, tour_id: uuid.UUID, member_id: uuid.UUID) -> Tour:
    tour = policy.locked_tour(session, tour_id)
    creator = policy.require(policy.membership(session, tour.id, viewer.user_id), "tour.transfer")
    target = session.scalar(select(TourMember).where(TourMember.id == member_id, TourMember.tour_id == tour.id, TourMember.state == "ACTIVE").with_for_update())
    if target is None or target.role != "CO_ORGANIZER":
        raise _invalid("member_id", "MUST_BE_CO_ORGANIZER")
    creator.role = "CO_ORGANIZER"
    session.flush()  # one creator at a time (partial unique index)
    target.role = "CREATOR"
    tour.creator_id = target.user_id
    tour.version += 1
    _record(session, viewer.user_id, tour, "ownership_transferred", to=target.user_id)
    return tour


def set_recruitment(session: Session, viewer: Viewer, tour_id: uuid.UUID, choice: str) -> Tour:
    tour = policy.locked_tour(session, tour_id)
    policy.require(policy.membership(session, tour.id, viewer.user_id), "tour.recruitment")
    if choice not in ("OPEN", "PAUSED", "CLOSED") or tour.lifecycle not in policy.OPEN_LIFECYCLES or tour.suspended_at is not None:
        raise ApiError("TRANSITION_NOT_ALLOWED")
    if tour.recruitment == "EXPIRED":
        raise ApiError("DEADLINE_PASSED")
    tour.recruitment_choice = choice
    if tour.recruitment != "FULL":
        tour.recruitment = choice
    tour.version += 1
    _record(session, viewer.user_id, tour, "recruitment", value=choice)
    return tour


def regenerate_code(session: Session, viewer: Viewer, tour_id: uuid.UUID) -> Tour:
    tour = policy.locked_tour(session, tour_id)
    policy.require(policy.membership(session, tour.id, viewer.user_id), "tour.regenerate_code")
    if tour.lifecycle not in policy.OPEN_LIFECYCLES:
        raise ApiError("TRANSITION_NOT_ALLOWED")
    tour.code = _unique_code(session)  # the old code and link stop working at once (AC-13)
    tour.code_version += 1
    tour.version += 1
    _record(session, viewer.user_id, tour, "code_regenerated")
    return tour


def lower_minimum(session: Session, viewer: Viewer, tour_id: uuid.UUID, minimum: int) -> Tour:
    """7.4.4: never below the current approved count and never below 2."""
    tour = policy.locked_tour(session, tour_id)
    policy.require(policy.membership(session, tour.id, viewer.user_id), "tour.edit_key_details")
    if tour.lifecycle not in policy.OPEN_LIFECYCLES:
        raise ApiError("TRANSITION_NOT_ALLOWED")
    if minimum >= tour.min_members:
        raise _invalid("min_members", "NOT_LOWER")
    if minimum < max(2, tour.seats_taken):
        raise _invalid("min_members", "BELOW_CURRENT")
    before = tour.min_members
    tour.min_members = minimum
    tour.version += 1
    session.add(TourChange(tour_id=tour.id, actor_id=viewer.user_id, kind="key_details", key_change=True, before={"min_members": before}, after={"min_members": minimum}))
    _after_seats_change(session, tour)
    return tour


def cancel(session: Session, tour: Tour, *, by: str, reason: str, actor_id: uuid.UUID | None) -> Tour:
    if tour.lifecycle not in policy.LIVE_LIFECYCLES:
        raise ApiError("TRANSITION_NOT_ALLOWED")
    tour.lifecycle, tour.cancelled_at, tour.cancelled_reason, tour.cancelled_by = "CANCELLED", now(), reason, by
    tour.recruitment = "CLOSED"
    tour.version += 1
    pending = session.execute(
        update(TourJoinRequest).where(TourJoinRequest.tour_id == tour.id, TourJoinRequest.state == "PENDING").values(state="EXPIRED", decided_at=now()).returning(TourJoinRequest.user_id)
    ).scalars().all()
    session.execute(update(TourInvitation).where(TourInvitation.tour_id == tour.id, TourInvitation.state == "PENDING").values(state="CLOSED", answered_at=now()))
    system_message(session, tour, "The tour was cancelled." + (" Cancelled by Abhijatri." if by == "STAFF" else ""))
    _emit(session, "tour.cancelled", tour, {"member_ids": member_ids(session, tour.id) + [str(u) for u in pending], "reason": reason, "by": by})
    audit.record(session, actor=None, action="tour.cancelled", target_type="tour", target_id=tour.id, reason=reason, metadata={"by": by, "actor": str(actor_id) if actor_id else ""})
    return tour


def cancel_by_creator(session: Session, viewer: Viewer, tour_id: uuid.UUID, reason: str) -> Tour:
    tour = policy.locked_tour(session, tour_id)
    policy.require(policy.membership(session, tour.id, viewer.user_id), "tour.cancel")
    if tour.lifecycle == "DRAFT":
        raise ApiError("TRANSITION_NOT_ALLOWED")
    return cancel(session, tour, by="CREATOR", reason=(reason or "CREATOR_CANCELLED")[:60], actor_id=viewer.user_id)


# ======================================================================================
# time-based transitions (architecture 7) -- shared by the scheduler and by reads
# ======================================================================================


def _expire_pending(session: Session, tour: Tour) -> None:
    expired = session.execute(
        update(TourJoinRequest).where(TourJoinRequest.tour_id == tour.id, TourJoinRequest.state == "PENDING").values(state="EXPIRED", decided_at=now()).returning(TourJoinRequest.user_id)
    ).scalars().all()
    for user_id in expired:
        _emit(session, "tour.request_expired", tour, {"user_id": str(user_id)})
    session.execute(update(TourInvitation).where(TourInvitation.tour_id == tour.id, TourInvitation.state == "PENDING").values(state="EXPIRED", answered_at=now()))


def apply_due(session: Session, tour: Tour, moment: datetime | None = None) -> bool:
    """Run every overdue transition on one locked tour. Returns True when something changed."""
    at = moment or now()
    today = dhaka_today(at)
    changed = False
    if tour.lifecycle == "RECRUITING" and at >= tour.recruit_deadline:
        cancel(session, tour, by="SYSTEM", reason="NOT_ENOUGH_TOURMATES", actor_id=None)  # AC-09
        return True
    if tour.lifecycle == "CONFIRMED" and at >= tour.recruit_deadline and tour.recruitment not in ("EXPIRED",):
        tour.recruitment = "EXPIRED"
        _expire_pending(session, tour)
        changed = True
    if tour.lifecycle == "CONFIRMED" and tour.is_at_risk:
        cancel_at = start_instant(tour.start_date) - timedelta(hours=24)
        if at >= cancel_at:
            cancel(session, tour, by="SYSTEM", reason="NOT_ENOUGH_BEFORE_START", actor_id=None)  # Q4, AC-08
            return True
        for hours in (48, 24):
            if at >= cancel_at - timedelta(hours=hours):
                _emit(session, "tour.at_risk_warning", tour, {"member_ids": member_ids(session, tour.id), "count": str(hours)}, dedupe_key=f"tour.at_risk_warning:{tour.id}:{hours}:{tour.version}")
                break
    if tour.lifecycle == "CONFIRMED" and today >= tour.start_date and tour.suspended_at is None:
        tour.lifecycle, tour.started_at, tour.recruitment = "ONGOING", at, "CLOSED"
        _expire_pending(session, tour)
        system_message(session, tour, "The tour has started. Have a safe trip!")
        _emit(session, "tour.started", tour, {"member_ids": member_ids(session, tour.id)})
        changed = True
    if tour.lifecycle == "CONFIRMED" and today == tour.start_date - timedelta(days=1):
        _emit(session, "tour.starts_tomorrow", tour, {"member_ids": member_ids(session, tour.id)}, dedupe_key=f"tour.starts_tomorrow:{tour.id}:{tour.start_date}")
    if tour.lifecycle == "ONGOING" and today > tour.end_date:
        tour.lifecycle, tour.completed_at = "COMPLETED", at
        system_message(session, tour, "The tour is complete. The discussion stays readable for 90 days.")
        _emit(session, "tour.completed", tour, {"member_ids": member_ids(session, tour.id)})
        changed = True
    finished = tour.completed_at or tour.cancelled_at
    if tour.lifecycle in ("COMPLETED", "CANCELLED") and finished is not None and at - finished >= timedelta(days=90):
        tour.lifecycle, tour.archived_at = "ARCHIVED", at
        # Chat is deleted at archive, except messages held for an open report (14.1.3).
        session.execute(delete(ChatMessage).where(ChatMessage.tour_id == tour.id, ChatMessage.held_for_report.is_(False)))
        changed = True
    if changed:
        tour.version += 1
        tour.updated_at = at
    return changed


def settle(session: Session, tour_id: uuid.UUID) -> Tour | None:
    """Apply overdue transitions before a read, so a missed scheduler tick is never visible."""
    tour = session.scalar(select(Tour).where(Tour.id == tour_id).with_for_update(skip_locked=True))
    if tour is None:
        return session.get(Tour, tour_id)
    if tour.lifecycle != "DRAFT" and apply_due(session, tour):
        session.commit()
    return session.get(Tour, tour_id)


# ======================================================================================
# views
# ======================================================================================


def tour_destinations(session: Session, tour_id: uuid.UUID) -> list[Destination]:
    return list(
        session.scalars(
            select(Destination).join(TourDestination, TourDestination.destination_id == Destination.id).where(TourDestination.tour_id == tour_id).order_by(TourDestination.position)
        )
    )


def _advisories(session: Session, destinations: list[Destination]) -> list[dict[str, Any]]:
    today = dhaka_today()
    rows = session.scalars(
        select(DestinationAdvisory).where(
            DestinationAdvisory.destination_id.in_([d.id for d in destinations]), DestinationAdvisory.is_published.is_(True),
            DestinationAdvisory.effective_on <= today, DestinationAdvisory.valid_until >= today,
        )
    )
    return [
        {"destination_id": str(a.destination_id), "severity": a.severity.value, "title_bn": a.title_bn, "title_en": a.title_en, "valid_until": a.valid_until.isoformat()}
        for a in rows
    ]


def display_labels(tour: Tour) -> list[str]:
    """"Upcoming" and "Starts in N days" are labels on Confirmed tours, never statuses (7.1, F1)."""
    labels = []
    if tour.lifecycle == "CONFIRMED":
        days = (tour.start_date - dhaka_today()).days
        if 0 <= days <= 14:
            labels.append("UPCOMING")
        labels.append(f"STARTS_IN_{max(days, 0)}")
    if tour.is_at_risk:
        labels.append("AT_RISK")
    if tour.suspended_at is not None:
        labels.append("SUSPENDED")
    return labels


def card(session: Session, tour: Tour) -> dict[str, Any]:
    destinations = tour_destinations(session, tour.id)
    return {
        "public_id": tour.public_id,
        "title": tour.title,
        "lifecycle": tour.lifecycle,
        "recruitment": tour.recruitment if tour.lifecycle in policy.OPEN_LIFECYCLES else "CLOSED",
        "is_at_risk": tour.is_at_risk,
        "suspended": tour.suspended_at is not None,
        "labels": display_labels(tour),
        "policy": tour.policy,
        "destinations": [{"id": str(d.id), "name_bn": d.name_bn, "name_en": d.name_en} for d in destinations],
        "start_date": tour.start_date.isoformat(),
        "end_date": tour.end_date.isoformat(),
        "recruit_deadline": tour.recruit_deadline.isoformat(),
        "members": {"approved": tour.seats_taken, "minimum": tour.min_members, "maximum": tour.max_members},
        "budget": {"min": tour.budget_min_bdt, "max": tour.budget_max_bdt},
        "style": tour.style,
        "pace": tour.pace,
        "activities": tour.activities,
        "departure_city": tour.departure_city,
    }


def member_list(session: Session, tour: Tour, *, full_names: bool, viewer_id: uuid.UUID | None) -> list[dict[str, Any]]:
    rows = session.execute(
        select(TourMember, User).join(User, User.id == TourMember.user_id).where(TourMember.tour_id == tour.id, TourMember.state.in_(("ACTIVE", "INACTIVE"))).order_by(TourMember.joined_at)
    ).all()
    out = []
    for member, user in rows:
        out.append({
            "member_id": str(member.id) if full_names else None,
            "name": user.display_name if full_names else policy.first_name(user.display_name),
            "first_name": policy.first_name(user.display_name),
            "role": member.role,
            "state": member.state,
            "verified": True,
            "seats": member.seats,
            "joined_at": member.joined_at.isoformat() if full_names else None,
            "is_you": viewer_id == member.user_id,
        })
    return out


def summary_view(session: Session, tour: Tour, viewer: Viewer, *, via_code: bool = False) -> dict[str, Any]:
    """The request screen (8.1). An ineligible viewer sees only title and dates (6.3)."""
    member = policy.membership(session, tour.id, viewer.user_id)
    eligible = policy.eligible(viewer, tour.policy, tour.start_date)
    if member is None and not eligible:
        return {"public_id": tour.public_id, "title": tour.title, "start_date": tour.start_date.isoformat(), "end_date": tour.end_date.isoformat(), "open_to_you": False}
    from app.tours import search

    view = card(session, tour) | {
        "open_to_you": True,
        "description": tour.description,
        "rules": tour.rules,
        "custom_rules": tour.custom_rules,
        "join_question": tour.join_question,
        "transport": tour.transport,
        "budget_includes": tour.budget_includes,
        "meeting_area": tour.meeting_area,
        "members_list": member_list(session, tour, full_names=member is not None and member.state == "ACTIVE", viewer_id=viewer.user_id),
        "is_member": member is not None,
        "your_role": member.role if member else None,
        "advisories": _advisories(session, tour_destinations(session, tour.id)),
    }
    pending = session.scalar(select(TourJoinRequest).where(TourJoinRequest.tour_id == tour.id, TourJoinRequest.user_id == viewer.user_id, TourJoinRequest.state == "PENDING"))
    view["your_request"] = {"id": str(pending.id), "state": pending.state} if pending else None
    view["can_request"] = member is None and pending is None and request_blockers(session, viewer, tour, via_code=via_code) is None
    view["request_blocker"] = None if member or pending else request_blockers(session, viewer, tour, via_code=via_code)
    view["match"] = search.score_for(session, viewer.user_id, tour)
    return view


def workspace_view(session: Session, tour: Tour, viewer: Viewer) -> dict[str, Any]:
    member = policy.membership(session, tour.id, viewer.user_id)
    if member is None:
        raise ApiError("NOT_FOUND")
    organiser = member.state == "ACTIVE" and member.role in policy.ORGANISER_ROLES
    confirmed = tour.confirmed_at is not None
    changes = session.scalars(select(TourChange).where(TourChange.tour_id == tour.id).order_by(TourChange.created_at.desc()).limit(15))
    pinned = session.scalars(
        select(ChatMessage).where(ChatMessage.tour_id == tour.id, ChatMessage.pinned_at.is_not(None), ChatMessage.deleted_at.is_(None), ChatMessage.hidden_by_staff_at.is_(None)).order_by(ChatMessage.pinned_at.desc()).limit(5)
    )
    view = summary_view(session, tour, viewer) | {
        "version": tour.version,
        "your_member_id": str(member.id),
        "your_state": member.state,
        "code": tour.code if organiser else None,
        "private_link": f"{get_settings().frontend_base_url.rstrip('/')}/t/{tour.code}" if organiser and tour.code else None,
        "confirmed_at": tour.confirmed_at.isoformat() if tour.confirmed_at else None,
        "cancelled_reason": tour.cancelled_reason,
        "cancelled_by": tour.cancelled_by,
        "recruitment_choice": tour.recruitment_choice,
        "itinerary_outline": tour.itinerary_outline,
        "change_window_until": tour.change_window_until.isoformat() if tour.change_window_until and tour.change_window_until > now() else None,
        "modules": {
            "overview": True,
            "tourmates": True,
            "itinerary": True,
            "discussion": confirmed and policy.feature_on("tours_chat"),
            "budget": confirmed and policy.feature_on("tours_budget"),
            "safety": confirmed and policy.feature_on("tours_safety"),
        },
        "seats_needed": max(tour.min_members - tour.seats_taken, 0),
        "pinned": [{"seq": m.seq, "body": m.body, "pinned_at": m.pinned_at.isoformat() if m.pinned_at else None} for m in pinned],
        "changes": [{"kind": c.kind, "key_change": c.key_change, "before": c.before, "after": c.after, "at": c.created_at.isoformat()} for c in changes],
        "permissions": sorted(action for action in policy.PERMISSIONS if member.state == "ACTIVE" and policy.can(member.role, action)),
    }
    if organiser:
        requests = session.execute(
            select(TourJoinRequest, User).join(User, User.id == TourJoinRequest.user_id).where(TourJoinRequest.tour_id == tour.id, TourJoinRequest.state == "PENDING").order_by(TourJoinRequest.created_at)
        ).all()
        view["pending_requests"] = [request_for_organiser(session, tour, r, u) for r, u in requests]
        invitations = session.execute(
            select(TourInvitation, User).join(User, User.id == TourInvitation.invitee_id).where(TourInvitation.tour_id == tour.id, TourInvitation.state == "PENDING")
        ).all()
        view["pending_invitations"] = [{"id": str(i.id), "name": policy.first_name(u.display_name), "expires_at": i.expires_at.isoformat()} for i, u in invitations]
        view["members_list"] = [
            m | {"companions": open_companions(mem.companions_sealed, f"tour_member_companions:{tour.id}:{mem.user_id}") if confirmed else []}
            for m, mem in zip(view["members_list"], _members(session, tour), strict=False)
        ]
    return view


def _members(session: Session, tour: Tour) -> list[TourMember]:
    return list(session.scalars(select(TourMember).join(User, User.id == TourMember.user_id).where(TourMember.tour_id == tour.id, TourMember.state.in_(("ACTIVE", "INACTIVE"))).order_by(TourMember.joined_at)))


def request_for_organiser(session: Session, tour: Tour, request: TourJoinRequest, user: User) -> dict[str, Any]:
    """8.4: first name, badge, score and reasons, answer, message, completed tours, and "Can't be approved"."""
    from app.tours import search

    completed = session.scalar(
        select(func.count()).select_from(TourMember).join(Tour, Tour.id == TourMember.tour_id).where(TourMember.user_id == user.id, Tour.lifecycle.in_(("COMPLETED", "ARCHIVED")), TourMember.state != "REMOVED")
    ) or 0
    problem = requester_problem(session, tour, user.id, request.seats)
    return {
        "id": str(request.id),
        "first_name": policy.first_name(user.display_name),
        "verified": True,
        "answer": request.answer,
        "message": request.message,
        "seats": request.seats,
        "companions": open_companions(request.companions_sealed, f"tour_request:{request.id}"),
        "via_code": request.via_code,
        "completed_tours": completed,
        "match": search.score_for(session, user.id, tour),
        "can_be_approved": problem is None,
        "problem": None if problem in (None, "BLOCKED") else problem,  # a block is shown only as "Can't be approved"
        "created_at": request.created_at.isoformat(),
    }


def dashboard(session: Session, viewer: Viewer) -> dict[str, Any]:
    """S1: one call returns every dashboard module (architecture 11)."""
    from app.tours import chat, invitations, search

    rows = session.execute(
        select(Tour, TourMember)
        .join(TourMember, TourMember.tour_id == Tour.id)
        .where(TourMember.user_id == viewer.user_id, TourMember.state.in_(("ACTIVE", "INACTIVE")), Tour.lifecycle != "ARCHIVED")
        .order_by(Tour.start_date)
    ).all()
    mine: list[dict[str, Any]] = []
    drafts: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    for tour, member in rows:
        if tour.lifecycle != "DRAFT":
            refreshed = settle(session, tour.id)
            tour = refreshed or tour
        item = card(session, tour) | {"your_role": member.role, "unread": chat.unread(session, tour.id, viewer.user_id)}
        if tour.lifecycle == "DRAFT":
            drafts.append(item)
            continue
        mine.append(item)
        if tour.is_at_risk:
            alerts.append({"kind": "AT_RISK", "public_id": tour.public_id, "title": tour.title})
        if tour.lifecycle == "CONFIRMED" and 0 <= (policy.start_instant(tour.start_date) - now()).total_seconds() <= 48 * 3600:
            alerts.append({"kind": "STARTS_SOON", "public_id": tour.public_id, "title": tour.title})
        if member.role in policy.ORGANISER_ROLES:
            waiting = session.scalar(select(func.count()).select_from(TourJoinRequest).where(TourJoinRequest.tour_id == tour.id, TourJoinRequest.state == "PENDING")) or 0
            if waiting:
                alerts.append({"kind": "REQUESTS_WAITING", "public_id": tour.public_id, "title": tour.title, "count": waiting})
    sent = session.execute(
        select(TourJoinRequest, Tour).join(Tour, Tour.id == TourJoinRequest.tour_id).where(TourJoinRequest.user_id == viewer.user_id).order_by(TourJoinRequest.created_at.desc()).limit(30)
    ).all()
    to_review = session.execute(
        select(TourJoinRequest, Tour, User)
        .join(Tour, Tour.id == TourJoinRequest.tour_id)
        .join(User, User.id == TourJoinRequest.user_id)
        .join(TourMember, (TourMember.tour_id == Tour.id) & (TourMember.user_id == viewer.user_id))
        .where(TourJoinRequest.state == "PENDING", TourMember.state == "ACTIVE", TourMember.role.in_(policy.ORGANISER_ROLES))
        .order_by(TourJoinRequest.created_at)
    ).all()
    return {
        "alerts": alerts,
        "my_tours": mine,
        "drafts": drafts,
        "requests": {
            "sent": [
                {
                    "id": str(r.id), "state": r.state, "public_id": t.public_id, "title": t.title, "created_at": r.created_at.isoformat(),
                    "decline_reason": dict(zip(("bn", "en"), DECLINE_CODES[r.decline_code], strict=True)) if r.decline_code in DECLINE_CODES else ({"bn": "ট্যুরে আসন পূর্ণ হয়ে গেছে", "en": "The tour filled up."} if r.decline_code == "FILLED_UP" else None),
                }
                for r, t in sent
            ],
            "to_review": [request_for_organiser(session, t, r, u) | {"public_id": t.public_id, "title": t.title} for r, t, u in to_review],
        },
        "invitations": invitations.mine(session, viewer),
        "suggested": search.find_tours(session, viewer, {}, limit=3)["items"] if policy.feature_on("tours_core") else [],
        "preferences_completion": search.preferences_completion(session, viewer.user_id),
        "discoverable": search.discoverable(session, viewer.user_id),
        "limits": {"active": get_settings().tours_active_per_user, "drafts": get_settings().tours_drafts_per_user},
    }


def find_by_public_id(session: Session, public_id: str) -> Tour:
    tour = session.scalar(select(Tour).where(Tour.public_id == public_id.upper()))
    if tour is None:
        raise ApiError("NOT_FOUND")
    return tour


def visible_or_404(session: Session, viewer: Viewer, tour: Tour, *, via_code: bool = False) -> None:
    """Members always see their tour; others only an open, listed (or code-reached) tour."""
    if policy.membership(session, tour.id, viewer.user_id) is not None:
        return
    if tour.lifecycle not in policy.OPEN_LIFECYCLES or tour.suspended_at is not None:
        raise ApiError("NOT_FOUND")
    if tour.policy == "INVITE_ONLY" and not via_code:
        invited = session.scalar(select(TourInvitation.id).where(TourInvitation.tour_id == tour.id, TourInvitation.invitee_id == viewer.user_id, TourInvitation.state == "PENDING"))
        if invited is None:
            raise ApiError("NOT_FOUND")  # AC-05


def lookup_code(session: Session, viewer: Viewer, raw: str, factory: Any) -> Tour:
    """12: a code opens only the summary; 10 failed lookups per user per hour (AC-12)."""
    from app.abuse import Rule, hit, peek

    rule = Rule("tour_code_failures", 3600, get_settings().tour_code_failures_per_hour)
    key = viewer.user_id.bytes
    wait = peek(factory, rule, key)
    if wait is not None:
        raise ApiError("RATE_LIMITED", headers={"Retry-After": str(wait)})
    code = policy.normalise_code(raw)
    tour = session.scalar(select(Tour).where(Tour.code == code, Tour.lifecycle.in_(policy.OPEN_LIFECYCLES), Tour.suspended_at.is_(None)))
    if tour is None or tour.recruitment in ("CLOSED", "EXPIRED"):
        count, _ = hit(factory, rule, key)
        if count >= get_settings().tour_code_failures_per_hour:
            _signal(session, viewer.user_id, "code_guessing", count=count)
            session.commit()
        raise ApiError("NOT_FOUND")
    return tour
