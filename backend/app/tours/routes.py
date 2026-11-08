"""Member-facing Tours and TourMates HTTP API.

The service modules contain the invariants and locked transactions; this file
is deliberately a thin transport layer. Reads use the member session, writes
also require the synchronizer CSRF token, and every response is private.
"""

import uuid
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import idempotency as idem
from app.abuse import CounterSessions
from app.auth.sessions import MemberPrincipal, Principal, require_csrf
from app.db import get_session
from app.errors import ApiError
from app.tours import chat, invitations, policy, reports, safety, search, service, workspace
from app.tours.models import Tour

DbSession = Annotated[Session, Depends(get_session)]
Writer = Annotated[Principal, Depends(require_csrf)]
IfMatch = Annotated[str | None, Header(alias="If-Match")]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/api/v1", tags=["tours"], dependencies=[Depends(_private)])


def _commit[T](session: Session, work: Callable[[], T]) -> T:
    try:
        result = work()
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def _idempotent(
    session: Session,
    principal: Principal,
    key_header: str | None,
    endpoint: str,
    path: dict[str, Any],
    body: dict[str, Any] | None,
    work: Callable[[], dict[str, Any]],
    status_code: int = 200,
) -> dict[str, Any] | JSONResponse:
    """Reserve/replay one member action; absent keys retain compatibility with older clients."""
    key = idem.parse_key(key_header)
    try:
        claim = idem.begin(
            session,
            key=key,
            scope=idem.member_scope(principal.user.id),
            endpoint=endpoint,
            request_fingerprint=idem.fingerprint_json(method="POST", path=path, body=body),
        )
        if isinstance(claim, idem.Replay):
            session.rollback()
            return idem.replay_response(claim)
        result = work()
        idem.finish_json(session, claim, status_code, result)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def _viewer(session: Session, principal: Principal, feature: str = "tours_core") -> policy.Viewer:
    return policy.access(session, principal, feature)


def _expected(raw: str | None) -> int | None:
    if raw is None:
        return None
    value = raw.strip().strip('"')
    try:
        return int(value)
    except ValueError as error:
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "If-Match", "code": "INVALID_VALUE"}]) from error


def _tour(session: Session, viewer: policy.Viewer, public_id: str, *, via_code: bool = False) -> Tour:
    tour = service.find_by_public_id(session, public_id)
    service.settle(session, tour.id)  # lazy time transition; scheduler remains the normal path
    service.visible_or_404(session, viewer, tour, via_code=via_code)
    return tour


def _request_result(item: Any) -> dict[str, Any]:
    return {"id": str(item.id), "state": item.state, "tour_id": str(item.tour_id)}


# Access, dashboard, preferences and discovery


@router.get("/tours/access")
def access_state(principal: MemberPrincipal, session: DbSession) -> dict[str, object]:
    return policy.access_state(session, principal)


@router.get("/me/tours")
def my_tours(principal: MemberPrincipal, session: DbSession) -> dict[str, Any]:
    return service.dashboard(session, _viewer(session, principal))


@router.get("/me/travel-preferences")
def my_preferences(principal: MemberPrincipal, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    return search.get_preferences(session, viewer.user_id)


@router.put("/me/travel-preferences")
def put_preferences(body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    return _commit(session, lambda: search.put_preferences(session, viewer.user_id, body))


@router.put("/me/discovery")
def put_discovery(body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_people")
    return _commit(session, lambda: search.put_discovery(session, viewer, body))


@router.get("/me/blocks")
def my_blocks(principal: MemberPrincipal, session: DbSession) -> dict[str, Any]:
    return {"items": reports.blocks(session, _viewer(session, principal))}


@router.post("/me/blocks/{user_id}")
def block_user(user_id: uuid.UUID, principal: Writer, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: reports.block(session, _viewer(session, principal), user_id))


@router.delete("/me/blocks/{user_id}")
def unblock_user(user_id: uuid.UUID, principal: Writer, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: reports.unblock(session, _viewer(session, principal), user_id))


# Discovery and identifiers (declared before the public-id catch-all routes)


@router.get("/tours/search")
def find_tours(
    principal: MemberPrincipal,
    session: DbSession,
    destination: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    policy_name: Annotated[str | None, Query(alias="policy")] = None,
    style: str | None = None,
    pace: str | None = None,
    activity: str | None = None,
    status: str | None = None,
    departure_city: str | None = None,
    sort: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    filters = {k: v for k, v in {
        "destination": destination, "date_from": date_from, "date_to": date_to,
        "policy": policy_name, "style": style, "pace": pace, "activity": activity,
        "status": status, "departure_city": departure_city, "sort": sort,
    }.items() if v not in (None, "")}
    return search.find_tours(session, _viewer(session, principal), filters, limit=limit, offset=offset)


@router.get("/people/search")
def find_people(
    principal: MemberPrincipal,
    session: DbSession,
    counters: CounterSessions,
    tour_id: str | None = None,
    destination: str | None = None,
    age_band: str | None = None,
    division: str | None = None,
    style: str | None = None,
    pace: str | None = None,
    activity: str | None = None,
    language: str | None = None,
    sort: str | None = None,
) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_people")
    selected = _tour(session, viewer, tour_id) if tour_id else None
    filters = {k: v for k, v in locals().items() if k in {"destination", "age_band", "division", "style", "pace", "activity", "language", "sort"} and v}
    return search.find_people(session, viewer, filters, tour=selected, factory=counters)


@router.get("/tours/by-code/{code}")
def by_code(code: str, principal: MemberPrincipal, session: DbSession, counters: CounterSessions) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    tour = service.lookup_code(session, viewer, code, counters)
    return service.summary_view(session, tour, viewer, via_code=True)


# Tour lifecycle, membership and requests


@router.post("/tours", status_code=201)
def create_tour(body: dict[str, Any], principal: Writer, session: DbSession, idempotency_key: idem.KeyHeader = None) -> Any:
    viewer = _viewer(session, principal)

    def work() -> dict[str, Any]:
        tour = service.create_draft(session, viewer, body)
        return service.workspace_view(session, tour, viewer)

    return _idempotent(session, principal, idempotency_key, idem.Endpoint.TOUR_CREATE, {}, body, work, 201)


@router.get("/tours/{public_id}/summary")
def tour_summary(public_id: str, principal: MemberPrincipal, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    return service.summary_view(session, _tour(session, viewer, public_id), viewer)


@router.get("/tours/{public_id}")
def tour_workspace(public_id: str, principal: MemberPrincipal, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    return service.workspace_view(session, _tour(session, viewer, public_id), viewer)


@router.patch("/tours/{public_id}")
def edit_tour(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession, if_match: IfMatch = None) -> dict[str, Any]:
    viewer = _viewer(session, principal)

    def work() -> dict[str, Any]:
        tour = _tour(session, viewer, public_id)
        service.update_draft(session, viewer, tour, body, _expected(if_match))
        return service.workspace_view(session, tour, viewer)

    return _commit(session, work)


@router.delete("/tours/{public_id}")
def delete_tour(public_id: str, principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)

    def work() -> dict[str, Any]:
        service.delete_draft(session, viewer, _tour(session, viewer, public_id))
        return {"deleted": True}

    return _commit(session, work)


@router.post("/tours/{public_id}/publish")
def publish_tour(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)

    def work() -> dict[str, Any]:
        tour = service.publish(session, viewer, _tour(session, viewer, public_id), accept_rules=bool(body.get("accept_rules")))
        return service.workspace_view(session, tour, viewer)

    return _commit(session, work)


@router.post("/tours/{public_id}/copy")
def copy_tour(public_id: str, principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    return _commit(session, lambda: service.workspace_view(session, service.copy_to_draft(session, viewer, _tour(session, viewer, public_id)), viewer))


@router.post("/tours/{public_id}/requests", status_code=201)
def request_join(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession, idempotency_key: idem.KeyHeader = None) -> Any:
    viewer = _viewer(session, principal)

    def work() -> dict[str, Any]:
        return _request_result(
            service.create_request(
                session,
                viewer,
                _tour(session, viewer, public_id, via_code=bool(body.get("code"))),
                answer=body.get("answer"),
                message=body.get("message"),
                accept_rules=bool(body.get("accept_rules")),
                companions=body.get("companions"),
                code=body.get("code"),
            )
        )

    return _idempotent(session, principal, idempotency_key, idem.Endpoint.TOUR_REQUEST, {"public_id": public_id}, body, work, 201)


@router.delete("/me/requests/{request_id}")
def withdraw_request(request_id: uuid.UUID, principal: Writer, session: DbSession) -> dict[str, Any]:
    return _commit(session, lambda: _request_result(service.withdraw_request(session, _viewer(session, principal), request_id)))


@router.post("/tours/{public_id}/requests/{request_id}/approve")
def approve_request(public_id: str, request_id: uuid.UUID, principal: Writer, session: DbSession, idempotency_key: idem.KeyHeader = None) -> Any:
    viewer = _viewer(session, principal)
    tour = _tour(session, viewer, public_id)
    return _idempotent(session, principal, idempotency_key, idem.Endpoint.TOUR_DECIDE, {"public_id": public_id, "request_id": request_id}, None, lambda: _request_result(service.approve_request(session, viewer, tour.id, request_id)))


@router.post("/tours/{public_id}/requests/{request_id}/decline")
def decline_request(public_id: str, request_id: uuid.UUID, body: dict[str, Any], principal: Writer, session: DbSession, idempotency_key: idem.KeyHeader = None) -> Any:
    viewer = _viewer(session, principal)
    tour = _tour(session, viewer, public_id)
    return _idempotent(session, principal, idempotency_key, idem.Endpoint.TOUR_DECIDE, {"public_id": public_id, "request_id": request_id}, body, lambda: _request_result(service.decline_request(session, viewer, tour.id, request_id, str(body.get("reason_code") or "OTHER"))))


@router.post("/tours/{public_id}/leave")
def leave_tour(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: service.card(session, service.leave(session, viewer, tour.id, safe_checkout=bool(body.get("safe_checkout")))))


@router.post("/tours/{public_id}/members/{member_id}/remove")
def remove_member(public_id: str, member_id: uuid.UUID, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: service.card(session, service.remove_member(session, viewer, tour.id, member_id, str(body.get("reason_code") or "OTHER"))))


@router.post("/tours/{public_id}/members/{member_id}/role")
def member_role(public_id: str, member_id: uuid.UUID, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    tour = _tour(session, viewer, public_id)

    def work() -> dict[str, Any]:
        item = service.set_role(session, viewer, tour.id, member_id, str(body.get("role") or "TOURMATE"))
        return {"id": str(item.id), "role": item.role}

    return _commit(session, work)


@router.post("/tours/{public_id}/ownership")
def transfer_ownership(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: service.card(session, service.transfer(session, viewer, tour.id, uuid.UUID(str(body["member_id"])))))


@router.post("/tours/{public_id}/recruitment")
def recruitment(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: service.card(session, service.set_recruitment(session, viewer, tour.id, str(body.get("state") or "OPEN"))))


@router.post("/tours/{public_id}/code/regenerate")
def regenerate_code(public_id: str, principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    tour = _tour(session, viewer, public_id)

    def work() -> dict[str, Any]:
        updated = service.regenerate_code(session, viewer, tour.id)
        return {"code": updated.code, "version": updated.version}

    return _commit(session, work)


@router.post("/tours/{public_id}/minimum")
def lower_minimum(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: service.card(session, service.lower_minimum(session, viewer, tour.id, int(body["min_members"]))))


@router.post("/tours/{public_id}/cancel")
def cancel_tour(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: service.card(session, service.cancel_by_creator(session, viewer, tour.id, str(body.get("reason") or "Cancelled by organiser"))))


# Invitations


@router.get("/me/invitations")
def my_invitations(principal: MemberPrincipal, session: DbSession) -> dict[str, Any]:
    return {"items": invitations.mine(session, _viewer(session, principal, "tours_people"))}


@router.post("/tours/{public_id}/invitations", status_code=201)
def invite(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession, counters: CounterSessions, idempotency_key: idem.KeyHeader = None) -> Any:
    viewer = _viewer(session, principal, "tours_people")
    tour = _tour(session, viewer, public_id)

    def work() -> dict[str, Any]:
        item = invitations.invite(session, viewer, tour.id, uuid.UUID(str(body["invitee_id"])), counters)
        return {"id": str(item.id), "state": item.state, "expires_at": item.expires_at.isoformat()}

    return _idempotent(session, principal, idempotency_key, idem.Endpoint.TOUR_INVITE, {"public_id": public_id}, body, work, 201)


@router.post("/me/invitations/{invitation_id}/accept")
def accept_invitation(invitation_id: uuid.UUID, principal: Writer, session: DbSession, idempotency_key: idem.KeyHeader = None) -> Any:
    viewer = _viewer(session, principal, "tours_people")
    return _idempotent(session, principal, idempotency_key, idem.Endpoint.TOUR_INVITATION_ANSWER, {"invitation_id": invitation_id}, {"answer": "accept"}, lambda: service.card(session, invitations.accept(session, viewer, invitation_id)))


@router.post("/me/invitations/{invitation_id}/decline")
def decline_invitation(invitation_id: uuid.UUID, body: dict[str, Any], principal: Writer, session: DbSession, idempotency_key: idem.KeyHeader = None) -> Any:
    viewer = _viewer(session, principal, "tours_people")

    def work() -> dict[str, Any]:
        item = invitations.decline(session, viewer, invitation_id, dont_invite_again=bool(body.get("dont_invite_again")))
        return {"id": str(item.id), "state": item.state}

    return _idempotent(session, principal, idempotency_key, idem.Endpoint.TOUR_INVITATION_ANSWER, {"invitation_id": invitation_id}, body, work)


# Itinerary and budget


@router.get("/tours/{public_id}/itinerary")
def get_itinerary(public_id: str, principal: MemberPrincipal, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    return workspace.itinerary(session, viewer, _tour(session, viewer, public_id))


@router.put("/tours/{public_id}/itinerary")
def put_itinerary(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: workspace.replace_itinerary(session, viewer, tour, list(body.get("items") or [])))


@router.post("/tours/{public_id}/itinerary/suggestions")
def suggest_itinerary(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: workspace.suggest(session, viewer, tour, body))


@router.post("/tours/{public_id}/itinerary/suggestions/{suggestion_id}")
def decide_itinerary(public_id: str, suggestion_id: uuid.UUID, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: workspace.decide_suggestion(session, viewer, tour, suggestion_id, bool(body.get("accept"))))


@router.get("/tours/{public_id}/budget")
def get_budget(public_id: str, principal: MemberPrincipal, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_budget")
    return workspace.budget(session, viewer, _tour(session, viewer, public_id))


@router.post("/tours/{public_id}/expenses", status_code=201)
def add_expense(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession, idempotency_key: idem.KeyHeader = None) -> Any:
    viewer = _viewer(session, principal, "tours_budget")
    tour = _tour(session, viewer, public_id)
    return _idempotent(session, principal, idempotency_key, idem.Endpoint.TOUR_EXPENSE, {"public_id": public_id}, body, lambda: workspace.add_expense(session, viewer, tour, body), 201)


@router.patch("/tours/{public_id}/expenses/{expense_id}")
def edit_expense(public_id: str, expense_id: uuid.UUID, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_budget")
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: workspace.edit_expense(session, viewer, tour, expense_id, body))


@router.post("/tours/{public_id}/settlements")
def settle_expense(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_budget")
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: workspace.settle(session, viewer, tour, uuid.UUID(str(body["to_user"])), int(body["amount_paisa"])))


# Safety


@router.get("/tours/{public_id}/safety")
def get_safety(public_id: str, principal: MemberPrincipal, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_safety")
    return safety.view(session, viewer, _tour(session, viewer, public_id))


@router.put("/tours/{public_id}/safety/me")
def put_safety(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_safety")
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: safety.put_mine(session, viewer, tour, body))


@router.post("/tours/{public_id}/safety/meeting-points", status_code=201)
def add_meeting_point(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_safety")
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: safety.add_meeting_point(session, viewer, tour, body))


@router.delete("/tours/{public_id}/safety/meeting-points/{point_id}")
def delete_meeting_point(public_id: str, point_id: uuid.UUID, principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_safety")
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: safety.delete_meeting_point(session, viewer, tour, point_id))


@router.post("/tours/{public_id}/checkins", status_code=201)
def request_checkin(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_safety")
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: safety.request_checkin(session, viewer, tour, str(body.get("message") or "Please check in")))


@router.post("/tours/{public_id}/checkins/{checkin_id}/answer")
def answer_checkin(public_id: str, checkin_id: uuid.UUID, principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_safety")
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: safety.answer_checkin(session, viewer, tour, checkin_id))


@router.post("/tours/{public_id}/sos", status_code=201)
def raise_sos(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession, idempotency_key: idem.KeyHeader = None) -> Any:
    viewer = _viewer(session, principal, "tours_safety")
    tour = _tour(session, viewer, public_id)
    return _idempotent(session, principal, idempotency_key, idem.Endpoint.TOUR_SOS, {"public_id": public_id}, body, lambda: safety.raise_sos(session, viewer, tour, body.get("message")), 201)


# Chat and reports


@router.get("/tours/{public_id}/messages")
def messages(public_id: str, principal: MemberPrincipal, session: DbSession, after_seq: int = 0, before_seq: int | None = None, limit: Annotated[int, Query(ge=1, le=200)] = 100) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_chat")
    return chat.history(session, viewer, _tour(session, viewer, public_id), after_seq=after_seq, before_seq=before_seq, limit=limit)


@router.post("/tours/{public_id}/messages", status_code=201)
def post_message(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_chat")
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: chat.post(session, viewer, tour, client_msg_id=uuid.UUID(str(body["client_msg_id"])), body=str(body.get("body") or ""), reply_to=body.get("reply_to"), announcement=bool(body.get("announcement"))))


@router.patch("/tours/{public_id}/messages/{seq}")
def edit_message(public_id: str, seq: int, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_chat")
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: chat.edit(session, viewer, tour, seq, str(body.get("body") or "")))


@router.delete("/tours/{public_id}/messages/{seq}")
def delete_message(public_id: str, seq: int, principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_chat")
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: chat.delete(session, viewer, tour, seq))


@router.post("/tours/{public_id}/messages/{seq}/pin")
def pin_message(public_id: str, seq: int, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_chat")
    tour = _tour(session, viewer, public_id)
    return _commit(session, lambda: chat.pin(session, viewer, tour, seq, bool(body.get("pinned", True))))


@router.post("/tours/{public_id}/messages/read")
def read_messages(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_chat")
    tour = _tour(session, viewer, public_id)
    def work() -> dict[str, Any]:
        chat.mark_read(session, viewer, tour, int(body.get("seq") or 0))
        return {"ok": True}

    return _commit(session, work)


@router.post("/tours/{public_id}/mute")
def mute_tour(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_chat")
    tour = _tour(session, viewer, public_id)
    def work() -> dict[str, Any]:
        chat.mute(session, viewer, tour, bool(body.get("muted")))
        return {"ok": True}

    return _commit(session, work)


@router.post("/tours/{public_id}/reports", status_code=201)
def report_tour(public_id: str, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal)
    tour = _tour(session, viewer, public_id)

    def work() -> dict[str, Any]:
        subject_id = uuid.UUID(str(body["subject_id"])) if body.get("subject_id") else None
        item = reports.report_tour(session, viewer, tour, subject_kind=str(body.get("subject_kind") or "TOUR"), subject_id=subject_id, reason_code=str(body.get("reason_code") or "OTHER"), details=body.get("details"))
        return {"id": str(item.id), "state": item.state}

    return _commit(session, work)


@router.post("/tours/{public_id}/messages/{seq}/report", status_code=201)
def report_message(public_id: str, seq: int, body: dict[str, Any], principal: Writer, session: DbSession) -> dict[str, Any]:
    viewer = _viewer(session, principal, "tours_chat")
    tour = _tour(session, viewer, public_id)

    def work() -> dict[str, Any]:
        item = chat.report(session, viewer, tour, seq, str(body.get("reason_code") or "OTHER"), body.get("details"))
        return {"id": str(item.id), "state": item.state}

    return _commit(session, work)
