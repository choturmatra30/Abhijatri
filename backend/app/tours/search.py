"""Travel preferences, the compatibility score, Find Tours and Find People (spec 4, 9, 10).

The score is advice, never a gate. Each part is 0 to 1 times its weight; a part the user has not filled is
left out and the rest are scaled to 100, and the card says how many factors it used (9.1). The reasons are
built from the same numbers, so the explanation always matches the score.

Hard filters (9.2) run before scoring: policy eligibility, a date overlap with the user's tours, a block
with any member, and a "No smoking" must against a tour that allows smoking. Invite-only tours are never
listed (AC-05). Find People lists only people who opted in, with coarse fields (AC-16).
"""

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, exists, func, not_, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ApiError
from app.models import Destination, DestinationStatus, User, VerificationAttributes
from app.tours import policy
from app.tours.models import (
    ACTIVITIES,
    PACES,
    STYLES,
    DiscoverySettings,
    Tour,
    TourDestination,
    TourMember,
    TravelPreferences,
    UserBlock,
)
from app.tours.policy import Viewer, dhaka_today
from app.verification import geo

WEIGHTS = {"dates": 30, "budget": 25, "destinations": 20, "style": 15, "activities": 10}
LANGUAGES = ("BN", "EN", "HI", "UR", "AR", "OTHER")


def division_of_destination(destination: Destination) -> str | None:
    text = f"{destination.region_en or ''} {destination.name_en}"
    return next((division for division in geo.DIVISIONS if division in text), None)


# ---------------------------------------------------------------- preferences (spec 4)


def get_preferences(session: Session, user_id: uuid.UUID) -> dict[str, Any]:
    prefs = session.get(TravelPreferences, user_id)
    settings = session.get(DiscoverySettings, user_id)
    return {
        "date_ranges": prefs.date_ranges if prefs else [],
        "flexible_dates": prefs.flexible_dates if prefs else False,
        "budget_min_bdt": prefs.budget_min_bdt if prefs else None,
        "budget_max_bdt": prefs.budget_max_bdt if prefs else None,
        "destinations": [str(d) for d in prefs.destinations] if prefs else [],
        "regions": prefs.regions if prefs else [],
        "style": prefs.style if prefs else None,
        "pace": prefs.pace if prefs else None,
        "activities": prefs.activities if prefs else [],
        "languages": prefs.languages if prefs else [],
        "smoking": prefs.smoking if prefs else None,
        "must_no_smoking": prefs.must_no_smoking if prefs else False,
        "discoverable": settings.discoverable if settings else False,
        "audience": settings.audience if settings else "ALL",
        "completion": preferences_completion(session, user_id),
        "divisions": list(geo.DIVISIONS),
    }


def _bad(field: str, code: str = "INVALID_VALUE") -> ApiError:
    return ApiError("VALIDATION_FAILED", field_errors=[{"field": field, "code": code}])


def put_preferences(session: Session, user_id: uuid.UUID, body: dict[str, Any]) -> dict[str, Any]:
    ranges = []
    for item in (body.get("date_ranges") or [])[:3]:
        try:
            start, end = date.fromisoformat(str(item["from"])), date.fromisoformat(str(item["to"]))
        except (KeyError, ValueError) as error:
            raise _bad("date_ranges", "INVALID_FORMAT") from error
        if end < start or (end - start).days > 180:
            raise _bad("date_ranges", "OUT_OF_RANGE")
        ranges.append({"from": start.isoformat(), "to": end.isoformat()})
    low, high = body.get("budget_min_bdt"), body.get("budget_max_bdt")
    if low is not None and high is not None and int(high) < int(low):
        raise _bad("budget_max_bdt", "BELOW_MINIMUM")
    destinations = []
    for raw in (body.get("destinations") or [])[:10]:
        try:
            destinations.append(uuid.UUID(str(raw)))
        except ValueError as error:
            raise _bad("destinations", "INVALID_UUID") from error
    regions = [r for r in (body.get("regions") or []) if r in geo.DIVISIONS][:8]
    for field, allowed in (("style", STYLES), ("pace", PACES)):
        if body.get(field) not in (None, "", *allowed):
            raise _bad(field)
    if any(a not in ACTIVITIES for a in body.get("activities") or []):
        raise _bad("activities")
    if any(lang not in LANGUAGES for lang in body.get("languages") or []):
        raise _bad("languages")
    if body.get("smoking") not in (None, "", "NO", "OUTDOORS", "YES"):
        raise _bad("smoking")
    prefs = session.get(TravelPreferences, user_id) or TravelPreferences(user_id=user_id)
    prefs.date_ranges = ranges
    prefs.flexible_dates = bool(body.get("flexible_dates"))
    prefs.budget_min_bdt = int(low) if low is not None else None
    prefs.budget_max_bdt = int(high) if high is not None else None
    prefs.destinations = destinations
    prefs.regions = regions
    prefs.style = body.get("style") or None
    prefs.pace = body.get("pace") or None
    prefs.activities = list(dict.fromkeys(body.get("activities") or []))
    prefs.languages = list(dict.fromkeys(body.get("languages") or []))
    prefs.smoking = body.get("smoking") or None
    prefs.must_no_smoking = bool(body.get("must_no_smoking"))
    prefs.updated_at = policy.now()
    session.add(prefs)
    session.flush()
    return get_preferences(session, user_id)


def preferences_completion(session: Session, user_id: uuid.UUID) -> int:
    """D8: the share of the five scored factors the user has filled, as a percentage."""
    prefs = session.get(TravelPreferences, user_id)
    if prefs is None:
        return 0
    filled = [
        bool(prefs.date_ranges or prefs.flexible_dates),
        prefs.budget_min_bdt is not None and prefs.budget_max_bdt is not None,
        bool(prefs.destinations or prefs.regions),
        bool(prefs.style or prefs.pace),
        bool(prefs.activities),
    ]
    return round(100 * sum(filled) / len(filled))


def discoverable(session: Session, user_id: uuid.UUID) -> bool:
    row = session.get(DiscoverySettings, user_id)
    return bool(row and row.discoverable)


def put_discovery(session: Session, viewer: Viewer, body: dict[str, Any]) -> dict[str, Any]:
    """10.2.1: off by default; on only with a filled profile; "only to women/men" for the matching gender."""
    on = bool(body.get("discoverable"))
    audience = body.get("audience") or "ALL"
    if audience not in ("ALL", "WOMEN", "MEN"):
        raise _bad("audience")
    if audience == "WOMEN" and viewer.gender != "FEMALE" or audience == "MEN" and viewer.gender != "MALE":
        raise _bad("audience", "NOT_ALLOWED")
    if on and preferences_completion(session, viewer.user_id) < 40:
        raise _bad("discoverable", "PROFILE_REQUIRED")  # spec 4: required before turning on Find People
    row = session.get(DiscoverySettings, viewer.user_id) or DiscoverySettings(user_id=viewer.user_id)
    row.discoverable, row.audience, row.updated_at, row.last_active_at = on, audience, policy.now(), policy.now()
    session.add(row)
    session.flush()
    return {"discoverable": row.discoverable, "audience": row.audience}


# ---------------------------------------------------------------- the score (spec 9)


def _ordinal(value: str | None, scale: tuple[str, ...]) -> int | None:
    return scale.index(value) if value in scale else None


def _step_match(a: str | None, b: str | None, scale: tuple[str, ...]) -> float | None:
    x, y = _ordinal(a, scale), _ordinal(b, scale)
    if x is None or y is None:
        return None
    return {0: 1.0, 1: 0.5}.get(abs(x - y), 0.0)


def score(prefs: TravelPreferences | None, tour: Tour, main: Destination | None, all_destination_ids: list[uuid.UUID]) -> dict[str, Any]:
    parts: dict[str, float] = {}
    reasons: list[dict[str, str]] = []
    if prefs is not None:
        days = [tour.start_date + timedelta(days=i) for i in range((tour.end_date - tour.start_date).days + 1)]
        if prefs.date_ranges:
            spans = [(date.fromisoformat(r["from"]), date.fromisoformat(r["to"])) for r in prefs.date_ranges]
            inside = sum(1 for day in days if any(a <= day <= b for a, b in spans))
            parts["dates"] = inside / len(days)
            reasons.append({"part": "dates", "en": f"Dates: fits {inside} of {len(days)} days.", "bn": f"তারিখ: {len(days)} দিনের {inside} দিন মেলে।"})
        elif prefs.flexible_dates:
            parts["dates"] = 0.7
            reasons.append({"part": "dates", "en": "Dates: you are flexible.", "bn": "তারিখ: আপনি নমনীয়।"})
        if prefs.budget_min_bdt is not None and prefs.budget_max_bdt is not None and tour.budget_min_bdt is not None and tour.budget_max_bdt is not None:
            low, high = max(prefs.budget_min_bdt, tour.budget_min_bdt), min(prefs.budget_max_bdt, tour.budget_max_bdt)
            if prefs.budget_min_bdt <= tour.budget_min_bdt and tour.budget_max_bdt <= prefs.budget_max_bdt:
                fit = 1.0
            else:
                smaller = max(min(prefs.budget_max_bdt - prefs.budget_min_bdt, tour.budget_max_bdt - tour.budget_min_bdt), 1)
                fit = max(high - low, 0) / smaller
            parts["budget"] = min(fit, 1.0)
            words = "inside your range" if fit >= 1 else ("partly in your range" if fit > 0 else "outside your range")
            reasons.append({"part": "budget", "en": f"Budget: ৳{tour.budget_min_bdt:,} to ৳{tour.budget_max_bdt:,} a day, {words}.", "bn": f"বাজেট: দিনে ৳{tour.budget_min_bdt:,}–৳{tour.budget_max_bdt:,}, {'আপনার সীমার মধ্যে' if fit >= 1 else ('আংশিক মেলে' if fit > 0 else 'সীমার বাইরে')}।"})
        if (prefs.destinations or prefs.regions) and main is not None:
            if main.id in prefs.destinations:
                parts["destinations"] = 1.0
                reasons.append({"part": "destinations", "en": f"Destination: {main.name_en} is on your list.", "bn": f"গন্তব্য: {main.name_bn} আপনার তালিকায় আছে।"})
            elif division_of_destination(main) in prefs.regions:
                parts["destinations"] = 0.6
                reasons.append({"part": "destinations", "en": f"Destination: {main.name_en} is in a region you like.", "bn": f"গন্তব্য: {main.name_bn} আপনার পছন্দের বিভাগে।"})
            else:
                parts["destinations"] = 0.0
                reasons.append({"part": "destinations", "en": f"Destination: {main.name_en} is not on your list.", "bn": f"গন্তব্য: {main.name_bn} আপনার তালিকায় নেই।"})
        style, pace = _step_match(prefs.style, tour.style, STYLES), _step_match(prefs.pace, tour.pace, PACES)
        known = [v for v in (style, pace) if v is not None]
        if known:
            parts["style"] = sum(known) / len(known)
            reasons.append({"part": "style", "en": "Style: " + ("same pace" if pace == 1 else "a different pace" if pace is not None else "") + (", same comfort" if style == 1 else ", a different comfort level" if style is not None else ""), "bn": "ধরন: " + ("একই গতি" if pace == 1 else "ভিন্ন গতি" if pace is not None else "") + (", একই আরাম" if style == 1 else ", ভিন্ন আরাম" if style is not None else "")})
        if prefs.activities and tour.activities:
            shared = [a for a in tour.activities if a in prefs.activities]
            parts["activities"] = len(shared) / len(tour.activities)
            reasons.append({"part": "activities", "en": "Activities: you share " + (", ".join(a.title().replace("_", " ") for a in shared) or "none") + ".", "bn": f"কার্যকলাপ: {len(shared)}টি মেলে।"})
    used = list(parts)
    weight = sum(WEIGHTS[p] for p in used)
    value = round(sum(parts[p] * WEIGHTS[p] for p in used) * 100 / weight) if weight else None
    return {"score": value, "factors_used": len(used), "factors_total": len(WEIGHTS), "parts": {p: round(v, 2) for p, v in parts.items()}, "reasons": reasons}


def _main_destination(session: Session, tour_id: uuid.UUID) -> tuple[Destination | None, list[uuid.UUID]]:
    rows = list(session.scalars(select(Destination).join(TourDestination, TourDestination.destination_id == Destination.id).where(TourDestination.tour_id == tour_id).order_by(TourDestination.position)))
    return (rows[0] if rows else None), [d.id for d in rows]


def score_for(session: Session, user_id: uuid.UUID, tour: Tour) -> dict[str, Any]:
    main, ids = _main_destination(session, tour.id)
    return score(session.get(TravelPreferences, user_id), tour, main, ids)


# ---------------------------------------------------------------- Find Tours (10.1)


def _eligible_policies(viewer: Viewer, start_floor: date) -> list[str]:
    allowed = ["OPEN", "FAMILY"]
    if viewer.gender == "FEMALE":
        allowed.append("WOMEN")
    if viewer.gender == "MALE":
        allowed.append("MEN")
    if viewer.is_student and viewer.student_until is not None:
        allowed.append("STUDENTS")  # end date checked per tour below
    return allowed


def find_tours(session: Session, viewer: Viewer, filters: dict[str, Any], *, limit: int = 20, offset: int = 0) -> dict[str, Any]:
    today = dhaka_today()
    me = viewer.user_id
    members = TourMember
    blocked_pairs = select(UserBlock.blocked_id).where(UserBlock.blocker_id == me).union(select(UserBlock.blocker_id).where(UserBlock.blocked_id == me))
    statement = select(Tour).where(
        Tour.suspended_at.is_(None),
        Tour.policy != "INVITE_ONLY",  # never listed (AC-05)
        Tour.policy.in_(_eligible_policies(viewer, today)),  # AC-04
        or_(Tour.lifecycle == "RECRUITING", and_(Tour.lifecycle == "CONFIRMED", Tour.seats_taken < Tour.max_members)),
        Tour.recruitment == "OPEN",
        Tour.recruit_deadline > policy.now(),
        not_(exists().where(members.tour_id == Tour.id, members.user_id == me, members.state.in_(("ACTIVE", "INACTIVE", "LEFT", "REMOVED")))),
        not_(exists().where(members.tour_id == Tour.id, members.state == "ACTIVE", members.user_id.in_(blocked_pairs))),
    )
    # no date overlap with a tour the user is already in (9.2)
    mine = select(Tour.start_date, Tour.end_date).join(members, members.tour_id == Tour.id).where(members.user_id == me, members.state == "ACTIVE", Tour.lifecycle.in_(policy.LIVE_LIFECYCLES)).subquery()
    statement = statement.where(not_(exists().where(mine.c.start_date <= Tour.end_date, mine.c.end_date >= Tour.start_date)))
    if viewer.is_student and viewer.student_until is not None:
        statement = statement.where(or_(Tour.policy != "STUDENTS", Tour.start_date <= viewer.student_until))
    if filters.get("destination"):
        statement = statement.where(exists().where(TourDestination.tour_id == Tour.id, TourDestination.destination_id == filters["destination"]))
    if filters.get("date_from"):
        statement = statement.where(Tour.end_date >= filters["date_from"])
    if filters.get("date_to"):
        statement = statement.where(Tour.start_date <= filters["date_to"])
    if filters.get("budget_max") is not None:
        statement = statement.where(or_(Tour.budget_min_bdt.is_(None), Tour.budget_min_bdt <= filters["budget_max"]))
    if filters.get("budget_min") is not None:
        statement = statement.where(or_(Tour.budget_max_bdt.is_(None), Tour.budget_max_bdt >= filters["budget_min"]))
    size = filters.get("size")
    if size == "SMALL":
        statement = statement.where(Tour.max_members <= 5)
    elif size == "MEDIUM":
        statement = statement.where(Tour.max_members.between(6, 12))
    elif size == "LARGE":
        statement = statement.where(Tour.max_members >= 13)
    if filters.get("policy"):
        statement = statement.where(Tour.policy == filters["policy"])
    if filters.get("style"):
        statement = statement.where(Tour.style == filters["style"])
    if filters.get("pace"):
        statement = statement.where(Tour.pace == filters["pace"])
    if filters.get("activities"):
        statement = statement.where(Tour.activities.overlap(list(filters["activities"])))
    if filters.get("status") == "RECRUITING":
        statement = statement.where(Tour.lifecycle == "RECRUITING")
    elif filters.get("status") == "CONFIRMED":
        statement = statement.where(Tour.lifecycle == "CONFIRMED")
    if filters.get("starts_within"):
        statement = statement.where(Tour.start_date <= today + timedelta(days=int(filters["starts_within"])))
    if filters.get("seats_left"):
        statement = statement.where(Tour.max_members - Tour.seats_taken >= int(filters["seats_left"]))
    if filters.get("departure_city"):
        statement = statement.where(func.lower(Tour.departure_city) == str(filters["departure_city"]).lower())
    if filters.get("q"):
        statement = statement.where(Tour.title.ilike(f"%{filters['q']}%"))
    candidates = list(session.scalars(statement.limit(500)))
    prefs = session.get(TravelPreferences, me)
    from app.tours import service

    scored = []
    for tour in candidates:
        if prefs is not None and prefs.must_no_smoking and "NO_SMOKING" not in tour.rules:
            continue  # 9.2: a hard preference
        main, ids = _main_destination(session, tour.id)
        match = score(prefs, tour, main, ids)
        scored.append((tour, match))
    sort = filters.get("sort") or "BEST"
    if sort == "SOONEST":
        scored.sort(key=lambda pair: pair[0].start_date)
    elif sort == "SEATS":
        scored.sort(key=lambda pair: pair[0].max_members - pair[0].seats_taken, reverse=True)
    elif sort == "NEWEST":
        scored.sort(key=lambda pair: pair[0].published_at or pair[0].created_at, reverse=True)
    else:
        scored.sort(key=lambda pair: (pair[1]["score"] if pair[1]["score"] is not None else -1, -pair[0].start_date.toordinal()), reverse=True)
    page = scored[offset : offset + limit]
    return {
        "items": [service.card(session, tour) | {"match": match} for tour, match in page],
        "total": len(scored),
        "next_offset": offset + limit if offset + limit < len(scored) else None,
        "preferences_completion": preferences_completion(session, me),
    }


# ---------------------------------------------------------------- Find People (10.2)


AGE_BANDS = ((18, 24, "18-24"), (25, 34, "25-34"), (35, 44, "35-44"), (45, 200, "45+"))


def age_band(birth_year: int | None) -> str | None:
    if birth_year is None:
        return None
    age = dhaka_today().year - birth_year
    return next((label for low, high, label in AGE_BANDS if low <= age <= high), None)


def _window(prefs: TravelPreferences) -> str | None:
    """An approximate travel window ("Mid-December"), never exact dates (10.2.2)."""
    if not prefs.date_ranges:
        return "Flexible" if prefs.flexible_dates else None
    start = date.fromisoformat(prefs.date_ranges[0]["from"])
    part = "Early" if start.day <= 10 else ("Mid" if start.day <= 20 else "Late")
    return f"{part}-{start.strftime('%B')}"


def find_people(session: Session, viewer: Viewer, filters: dict[str, Any], *, tour: Tour | None, factory: Any) -> dict[str, Any]:
    from app.abuse import Rule, hit

    me = viewer.user_id
    blocked_pairs = select(UserBlock.blocked_id).where(UserBlock.blocker_id == me).union(select(UserBlock.blocker_id).where(UserBlock.blocked_id == me))
    statement = (
        select(User, TravelPreferences, VerificationAttributes, DiscoverySettings)
        .join(DiscoverySettings, DiscoverySettings.user_id == User.id)
        .join(TravelPreferences, TravelPreferences.user_id == User.id)
        .join(VerificationAttributes, VerificationAttributes.user_id == User.id)
        .where(DiscoverySettings.discoverable.is_(True), User.id != me, User.status == "active", User.id.not_in(blocked_pairs))  # AC-16, 10.2.4
    )
    # audience: "only women" / "only men" see me (10.2.3)
    visible_audiences = ["ALL"]
    if viewer.gender == "FEMALE":
        visible_audiences.append("WOMEN")
    elif viewer.gender == "MALE":
        visible_audiences.append("MEN")
    statement = statement.where(DiscoverySettings.audience.in_(visible_audiences))
    rows = session.execute(statement.limit(400)).all()
    from app.admin.cases import is_verified_member

    out: list[dict[str, Any]] = []
    for user, prefs, attributes, settings in rows:
        if not is_verified_member(session, user.id) or age_band(attributes.birth_year) is None:
            continue  # Q5: 18+ and verified only
        person = policy.viewer_for(session, user.id)
        if person.restricted:
            continue
        if tour is not None and not policy.eligible(person, tour.policy, tour.start_date):
            continue  # 10.2.3: people who could join the searcher's tour
        band = age_band(attributes.birth_year)
        division = geo.division_of(attributes.home_district)
        if filters.get("age_band") and band != filters["age_band"]:
            continue
        if filters.get("division") and division != filters["division"]:
            continue
        if filters.get("style") and prefs.style != filters["style"]:
            continue
        if filters.get("pace") and prefs.pace != filters["pace"]:
            continue
        if filters.get("activity") and filters["activity"] not in prefs.activities:
            continue
        if filters.get("language") and filters["language"] not in prefs.languages:
            continue
        if filters.get("destination"):
            try:
                if uuid.UUID(str(filters["destination"])) not in prefs.destinations:
                    continue
            except ValueError:
                continue
        destinations = [d.name_en for d in session.scalars(select(Destination).where(Destination.id.in_(prefs.destinations), Destination.status == DestinationStatus.PUBLISHED))]
        completed = session.scalar(
            select(func.count()).select_from(TourMember).join(Tour, Tour.id == TourMember.tour_id).where(TourMember.user_id == user.id, Tour.lifecycle.in_(("COMPLETED", "ARCHIVED")), TourMember.state != "REMOVED")
        ) or 0
        match = score(prefs, tour, *_main_destination(session, tour.id)) if tour is not None else None
        out.append({
            "user_id": str(user.id),
            "first_name": policy.first_name(user.display_name),
            "verified": True,
            "age_band": band,
            "division": division,
            "languages": prefs.languages,
            "style": prefs.style,
            "pace": prefs.pace,
            "activities": prefs.activities,
            "destinations": destinations,
            "travel_window": _window(prefs),
            "completed_tours": completed,
            "match": match,
            "last_active_at": settings.last_active_at.isoformat() if settings.last_active_at else None,
        })
    if filters.get("sort") == "RECENT":
        out.sort(key=lambda item: item["last_active_at"] or "", reverse=True)
    else:
        out.sort(key=lambda item: int((item["match"] or {}).get("score") or -1), reverse=True)
    page = out[:20]
    # 10.2.6: at most 100 person cards a day (counted per card shown)
    rule = Rule("tour_person_cards", 86400, get_settings().tour_people_cards_per_day)
    for _ in page:
        count, wait = hit(factory, rule, me.bytes)
        if wait is not None:
            raise ApiError("RATE_LIMITED", headers={"Retry-After": str(wait)})
    return {"items": page, "total": len(out)}
