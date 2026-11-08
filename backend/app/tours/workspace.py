"""Workspace modules: itinerary (13.1) and budget (13.3).

Budget amounts are integer paisa (1 taka = 100 paisa). Abhijatri never moves, holds or requests money and
never stores payment account numbers (SRS C3, C8): the balance view only says who owes whom, with the fewest
transfers, and members mark a transfer settled themselves after paying outside the app.
"""

import uuid
from datetime import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Destination, User
from app.tours import policy
from app.tours.models import (
    Expense,
    ExpenseHistory,
    ExpenseShare,
    ItineraryItem,
    ItinerarySuggestion,
    Settlement,
    Tour,
    TourMember,
)
from app.tours.policy import Viewer, now

CATEGORIES = ("TRANSPORT", "STAY", "FOOD", "ENTRY", "OTHER")
ITEM_KINDS = ("STOP", "TRANSPORT", "STAY", "NOTE")


def _bad(field: str, code: str = "INVALID_VALUE") -> ApiError:
    return ApiError("VALIDATION_FAILED", field_errors=[{"field": field, "code": code}])


def _active(session: Session, viewer: Viewer, tour: Tour) -> TourMember:
    member = policy.membership(session, tour.id, viewer.user_id)
    if member is None or member.state != "ACTIVE":
        raise ApiError("NOT_FOUND")
    return member


# ---------------------------------------------------------------- itinerary


def _clean_item(session: Session, tour: Tour, raw: dict[str, Any], position: int) -> dict[str, Any]:
    days = (tour.end_date - tour.start_date).days + 1
    try:
        day = int(raw.get("day") or 1)
    except (TypeError, ValueError) as error:
        raise _bad("day") from error
    if not 1 <= day <= days:
        raise _bad("day", "OUT_OF_RANGE")
    kind = raw.get("kind") or "STOP"
    if kind not in ITEM_KINDS:
        raise _bad("kind")
    title = str(raw.get("title") or "").strip()[:120]
    if len(title) < 2:
        raise _bad("title", "REQUIRED")
    destination_id = None
    if raw.get("destination_id"):
        try:
            destination_id = uuid.UUID(str(raw["destination_id"]))
        except ValueError as error:
            raise _bad("destination_id", "INVALID_UUID") from error
        if session.get(Destination, destination_id) is None:
            raise _bad("destination_id")
    starts_at = None
    if raw.get("starts_at"):
        try:
            starts_at = time.fromisoformat(str(raw["starts_at"]))
        except ValueError as error:
            raise _bad("starts_at", "INVALID_FORMAT") from error
    return {"day": day, "position": position, "kind": kind, "title": title, "destination_id": destination_id, "starts_at": starts_at, "notes": str(raw.get("notes") or "")[:500] or None}


def itinerary(session: Session, viewer: Viewer, tour: Tour) -> dict[str, Any]:
    member = _active(session, viewer, tour)
    items = session.scalars(select(ItineraryItem).where(ItineraryItem.tour_id == tour.id).order_by(ItineraryItem.day, ItineraryItem.position))
    suggestions = session.execute(
        select(ItinerarySuggestion, User).join(User, User.id == ItinerarySuggestion.author_id).where(ItinerarySuggestion.tour_id == tour.id, ItinerarySuggestion.state == "PENDING")
    ).all()
    return {
        "days": (tour.end_date - tour.start_date).days + 1,
        "start_date": tour.start_date.isoformat(),
        "can_edit": policy.can(member.role, "itinerary.edit") and tour.lifecycle in policy.LIVE_LIFECYCLES,
        "items": [
            {"id": str(i.id), "day": i.day, "position": i.position, "kind": i.kind, "title": i.title, "destination_id": str(i.destination_id) if i.destination_id else None,
             "starts_at": i.starts_at.isoformat(timespec="minutes") if i.starts_at else None, "notes": i.notes}
            for i in items
        ],
        "suggestions": [{"id": str(s.id), "by": policy.first_name(u.display_name), "proposal": s.proposal, "created_at": s.created_at.isoformat()} for s, u in suggestions],
    }


def replace_itinerary(session: Session, viewer: Viewer, tour: Tour, items: list[dict[str, Any]]) -> dict[str, Any]:
    tour = policy.locked_tour(session, tour.id)
    policy.require(policy.membership(session, tour.id, viewer.user_id), "itinerary.edit")
    if tour.lifecycle not in policy.LIVE_LIFECYCLES or tour.suspended_at is not None:
        raise ApiError("TRANSITION_NOT_ALLOWED")
    if len(items) > 200:
        raise _bad("items", "TOO_MANY")
    clean = [_clean_item(session, tour, raw, position) for position, raw in enumerate(items)]
    for row in session.scalars(select(ItineraryItem).where(ItineraryItem.tour_id == tour.id)):
        session.delete(row)
    session.flush()
    for values in clean:
        session.add(ItineraryItem(tour_id=tour.id, updated_by=viewer.user_id, updated_at=now(), **values))
    tour.version += 1
    session.flush()
    return itinerary(session, viewer, tour)


def suggest(session: Session, viewer: Viewer, tour: Tour, proposal: dict[str, Any]) -> dict[str, Any]:
    member = _active(session, viewer, tour)
    if member.role != "TOURMATE":
        raise ApiError("FORBIDDEN")  # organisers edit directly
    item = _clean_item(session, tour, proposal, 0)
    session.add(ItinerarySuggestion(tour_id=tour.id, author_id=viewer.user_id, proposal={k: (str(v) if v is not None else None) for k, v in item.items() if k != "position"}))
    session.flush()
    return itinerary(session, viewer, tour)


def decide_suggestion(session: Session, viewer: Viewer, tour: Tour, suggestion_id: uuid.UUID, accept: bool) -> dict[str, Any]:
    policy.require(policy.membership(session, tour.id, viewer.user_id), "itinerary.edit")
    suggestion = session.get(ItinerarySuggestion, suggestion_id)
    if suggestion is None or suggestion.tour_id != tour.id or suggestion.state != "PENDING":
        raise ApiError("NOT_FOUND")
    suggestion.state, suggestion.decided_by = ("ACCEPTED" if accept else "REJECTED"), viewer.user_id
    if accept:
        last = session.scalar(select(ItineraryItem.position).where(ItineraryItem.tour_id == tour.id).order_by(ItineraryItem.position.desc()).limit(1)) or 0
        values = _clean_item(session, tour, dict(suggestion.proposal), last + 1)
        session.add(ItineraryItem(tour_id=tour.id, updated_by=viewer.user_id, updated_at=now(), **values))
    session.flush()
    return itinerary(session, viewer, tour)


# ---------------------------------------------------------------- budget


def _budget_open(session: Session, viewer: Viewer, tour: Tour) -> TourMember:
    member = _active(session, viewer, tour)
    if not policy.feature_on("tours_budget") or tour.confirmed_at is None:
        raise ApiError("CHAT_LOCKED")  # Budget opens with confirmation (13.1)
    return member


def _split(amount: int, people: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Equal shares in paisa; the first people absorb the remainder so the shares add up exactly."""
    base, extra = divmod(amount, len(people))
    return {person: base + (1 if index < extra else 0) for index, person in enumerate(people)}


def _snapshot(expense: Expense, shares: dict[uuid.UUID, int]) -> dict[str, Any]:
    return {
        "amount_paisa": expense.amount_paisa, "category": expense.category, "description": expense.description, "paid_by": str(expense.paid_by),
        "shares": {str(k): v for k, v in shares.items()}, "settled": expense.settled,
    }


def _shares_from(session: Session, tour: Tour, amount: int, body: dict[str, Any]) -> dict[uuid.UUID, int]:
    members = set(policy.active_member_ids(session, tour.id))
    if body.get("shares"):
        shares = {}
        for user_id, share in dict(body["shares"]).items():
            uid = uuid.UUID(str(user_id))
            if uid not in members or int(share) < 0:
                raise _bad("shares")
            shares[uid] = int(share)
        if sum(shares.values()) != amount:
            raise _bad("shares", "MUST_ADD_UP")
        return shares
    chosen = [uuid.UUID(str(u)) for u in (body.get("shared_by") or [])] or sorted(members)
    if not chosen or any(u not in members for u in chosen):
        raise _bad("shared_by")
    return _split(amount, chosen)


def add_expense(session: Session, viewer: Viewer, tour: Tour, body: dict[str, Any]) -> dict[str, Any]:
    _budget_open(session, viewer, tour)
    if tour.lifecycle not in ("CONFIRMED", "ONGOING", "COMPLETED") or tour.suspended_at is not None:
        raise ApiError("TRANSITION_NOT_ALLOWED")
    try:
        raw_amount = body.get("amount_bdt")
        if raw_amount is None and body.get("amount_paisa") is None:
            raise _bad("amount_bdt", "REQUIRED")
        if body.get("amount_paisa") is None:
            assert raw_amount is not None
            amount = int(round(float(raw_amount) * 100))
        else:
            amount = int(body["amount_paisa"])
    except (TypeError, ValueError) as error:
        raise _bad("amount_bdt") from error
    if not 0 < amount <= 100_000_000:
        raise _bad("amount_bdt", "OUT_OF_RANGE")
    category = body.get("category") or "OTHER"
    if category not in CATEGORIES:
        raise _bad("category")
    description = str(body.get("description") or "").strip()[:200]
    if len(description) < 2:
        raise _bad("description", "REQUIRED")
    paid_by = uuid.UUID(str(body.get("paid_by") or viewer.user_id))
    if paid_by not in set(policy.active_member_ids(session, tour.id)):
        raise _bad("paid_by")
    shares = _shares_from(session, tour, amount, body)
    expense = Expense(tour_id=tour.id, author_id=viewer.user_id, paid_by=paid_by, amount_paisa=amount, category=category, description=description)
    session.add(expense)
    session.flush()
    for user_id, share in shares.items():
        session.add(ExpenseShare(expense_id=expense.id, user_id=user_id, share_paisa=share))
    session.add(ExpenseHistory(expense_id=expense.id, actor_id=viewer.user_id, before={}, after=_snapshot(expense, shares)))
    session.flush()
    return budget(session, viewer, tour)


def edit_expense(session: Session, viewer: Viewer, tour: Tour, expense_id: uuid.UUID, body: dict[str, Any]) -> dict[str, Any]:
    _budget_open(session, viewer, tour)
    expense = session.scalar(select(Expense).where(Expense.id == expense_id, Expense.tour_id == tour.id, Expense.deleted_at.is_(None)).with_for_update())
    if expense is None:
        raise ApiError("NOT_FOUND")
    if expense.author_id != viewer.user_id or expense.settled:
        raise ApiError("FORBIDDEN")  # 13.3.6: by its author, until settled
    if body.get("expected_version") is not None and int(body["expected_version"]) != expense.version:
        raise ApiError("STALE_VERSION")
    old_shares = {s.user_id: s.share_paisa for s in session.scalars(select(ExpenseShare).where(ExpenseShare.expense_id == expense.id))}
    before = _snapshot(expense, old_shares)
    if body.get("delete"):
        expense.deleted_at = now()
        session.add(ExpenseHistory(expense_id=expense.id, actor_id=viewer.user_id, before=before, after={"deleted": True}))
        session.flush()
        return budget(session, viewer, tour)
    if "amount_bdt" in body or "amount_paisa" in body:
        expense.amount_paisa = int(round(float(body["amount_bdt"]) * 100)) if "amount_bdt" in body else int(body["amount_paisa"])
        if expense.amount_paisa <= 0:
            raise _bad("amount_bdt", "OUT_OF_RANGE")
    if body.get("category"):
        if body["category"] not in CATEGORIES:
            raise _bad("category")
        expense.category = body["category"]
    if body.get("description"):
        expense.description = str(body["description"]).strip()[:200]
    shares = _shares_from(session, tour, expense.amount_paisa, body) if ("shares" in body or "shared_by" in body or "amount_bdt" in body or "amount_paisa" in body) else old_shares
    for row in session.scalars(select(ExpenseShare).where(ExpenseShare.expense_id == expense.id)):
        session.delete(row)
    session.flush()
    for user_id, share in shares.items():
        session.add(ExpenseShare(expense_id=expense.id, user_id=user_id, share_paisa=share))
    expense.version += 1
    expense.updated_at = now()
    session.add(ExpenseHistory(expense_id=expense.id, actor_id=viewer.user_id, before=before, after=_snapshot(expense, shares)))
    session.flush()
    return budget(session, viewer, tour)


def balances(session: Session, tour_id: uuid.UUID) -> tuple[dict[uuid.UUID, int], list[dict[str, Any]]]:
    """Net position per person (paid minus share, adjusted by settlements) and the fewest transfers."""
    net: dict[uuid.UUID, int] = {}
    for expense in session.scalars(select(Expense).where(Expense.tour_id == tour_id, Expense.deleted_at.is_(None))):
        net[expense.paid_by] = net.get(expense.paid_by, 0) + expense.amount_paisa
        for share in session.scalars(select(ExpenseShare).where(ExpenseShare.expense_id == expense.id)):
            net[share.user_id] = net.get(share.user_id, 0) - share.share_paisa
    for settlement in session.scalars(select(Settlement).where(Settlement.tour_id == tour_id)):
        net[settlement.from_user] = net.get(settlement.from_user, 0) + settlement.amount_paisa
        net[settlement.to_user] = net.get(settlement.to_user, 0) - settlement.amount_paisa
    assert sum(net.values()) == 0, "balances must sum to zero (AC-19)"
    creditors = sorted(((v, k) for k, v in net.items() if v > 0), reverse=True)
    debtors = sorted(((-v, k) for k, v in net.items() if v < 0), reverse=True)
    transfers: list[dict[str, Any]] = []
    i = j = 0
    owed: list[list[int | uuid.UUID]] = [[amount, user_id] for amount, user_id in creditors]
    owing: list[list[int | uuid.UUID]] = [[amount, user_id] for amount, user_id in debtors]
    while i < len(owing) and j < len(owed):
        owing_amount = int(owing[i][0])
        owed_amount = int(owed[j][0])
        amount = min(owing_amount, owed_amount)
        transfers.append({"from": owing[i][1], "to": owed[j][1], "amount_paisa": amount})
        owing[i][0] = owing_amount - amount
        owed[j][0] = owed_amount - amount
        if owing[i][0] == 0:
            i += 1
        if owed[j][0] == 0:
            j += 1
    return net, transfers


def budget(session: Session, viewer: Viewer, tour: Tour) -> dict[str, Any]:
    _budget_open(session, viewer, tour)
    names = {u: policy.first_name(n) for u, n in session.execute(select(TourMember.user_id, User.display_name).join(User, User.id == TourMember.user_id).where(TourMember.tour_id == tour.id))}
    expenses = []
    for expense in session.scalars(select(Expense).where(Expense.tour_id == tour.id, Expense.deleted_at.is_(None)).order_by(Expense.created_at.desc())):
        shares = {s.user_id: s.share_paisa for s in session.scalars(select(ExpenseShare).where(ExpenseShare.expense_id == expense.id))}
        history = session.scalars(select(ExpenseHistory).where(ExpenseHistory.expense_id == expense.id).order_by(ExpenseHistory.created_at))
        expenses.append({
            "id": str(expense.id), "description": expense.description, "category": expense.category, "amount_paisa": expense.amount_paisa,
            "paid_by": str(expense.paid_by), "paid_by_name": names.get(expense.paid_by), "author_is_you": expense.author_id == viewer.user_id,
            "shares": [{"user_id": str(u), "name": names.get(u), "share_paisa": v} for u, v in shares.items()], "settled": expense.settled,
            "version": expense.version, "created_at": expense.created_at.isoformat(), "history_count": len(list(history)),
        })
    net, transfers = balances(session, tour.id)
    planned = {"min_bdt": tour.budget_min_bdt, "max_bdt": tour.budget_max_bdt, "includes": tour.budget_includes}
    return {
        "planned": planned,
        "expenses": expenses,
        "total_paisa": sum(e["amount_paisa"] for e in expenses),
        "balances": [{"user_id": str(u), "name": names.get(u), "net_paisa": v} for u, v in net.items()],
        "transfers": [t | {"from": str(t["from"]), "to": str(t["to"]), "from_name": names.get(t["from"]), "to_name": names.get(t["to"]), "is_from_you": t["from"] == viewer.user_id} for t in transfers],
        "settlements": [
            {"from_name": names.get(s.from_user), "to_name": names.get(s.to_user), "amount_paisa": s.amount_paisa, "at": s.created_at.isoformat()}
            for s in session.scalars(select(Settlement).where(Settlement.tour_id == tour.id).order_by(Settlement.created_at.desc()))
        ],
        "notice": {
            "en": "Abhijatri never moves, holds or asks for money. Pay each other outside the app (bKash, cash) and mark it settled here.",
            "bn": "অভিযাত্রী কখনো টাকা লেনদেন, জমা বা চায় না। অ্যাপের বাইরে (বিকাশ, নগদ) পরিশোধ করে এখানে মিটে গেছে চিহ্নিত করুন।",
        },
    }


def settle(session: Session, viewer: Viewer, tour: Tour, to_user: uuid.UUID, amount_paisa: int) -> dict[str, Any]:
    """The payer marks a transfer as paid (13.3.4)."""
    _budget_open(session, viewer, tour)
    if to_user == viewer.user_id or to_user not in set(policy.active_member_ids(session, tour.id)) or amount_paisa <= 0:
        raise _bad("to_user")
    _, transfers = balances(session, tour.id)
    owed = sum(t["amount_paisa"] for t in transfers if t["from"] == viewer.user_id and t["to"] == to_user)
    if amount_paisa > owed:
        raise _bad("amount_paisa", "MORE_THAN_OWED")
    session.add(Settlement(tour_id=tour.id, from_user=viewer.user_id, to_user=to_user, amount_paisa=amount_paisa, marked_by=viewer.user_id))
    session.flush()
    return budget(session, viewer, tour)
