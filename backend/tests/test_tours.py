"""Tours P0/P1 acceptance paths against real PostgreSQL."""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import pytest
import test_admin as admin
import test_auth as support
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Destination, DestinationStatus, OutboxEvent
from app.tours import policy, workspace
from app.tours.models import SafetyProfile, Tour, TourMember

auth_env = support.auth_env
fake = support.fake
redis_fake = support.redis_fake
client = support.client
_reset_limiter = support._reset_limiter  # noqa: SLF001
pytestmark = pytest.mark.integration


def verified(
    template: TestClient,
    session: Session,
    fake_auth: support.FakeGoTrue,
    email: str,
    ip: str,
    *,
    gender: str = "FEMALE",
    birth_year: int = 1995,
) -> TestClient:
    browser = admin.staff_client(template, session, fake_auth, email, None, ip, aal="aal1")
    user_id = uuid.UUID(str(fake_auth.users[email]["id"]))
    admin.make_verified(session, user_id, gender=gender, birth_year=birth_year)
    return browser


def destination(session: Session) -> Destination:
    item = Destination(status=DestinationStatus.PUBLISHED, name_bn="সাজেক", name_en="Sajek", region_en="Chattogram")
    session.add(item)
    session.commit()
    return item


def draft_body(place: Destination, *, minimum: int = 3, maximum: int = 5, policy_name: str = "OPEN") -> dict[str, Any]:
    start = date.today() + timedelta(days=14)
    deadline = datetime.combine(start - timedelta(days=3), time(hour=12), tzinfo=UTC)
    return {
        "title": "Sajek weekend explorers",
        "description": "A careful shared trip plan.",
        "destinations": [str(place.id)],
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=2)).isoformat(),
        "recruit_deadline": deadline.isoformat(),
        "min_members": minimum,
        "max_members": maximum,
        "policy": policy_name,
        "budget_min_bdt": 2500,
        "budget_max_bdt": 4000,
        "style": "BUDGET",
        "pace": "BALANCED",
        "activities": ["HIKING", "PHOTOGRAPHY"],
        "departure_city": "Dhaka",
    }


def create_and_publish(owner: TestClient, place: Destination, *, minimum: int = 3, maximum: int = 5, policy_name: str = "OPEN") -> dict[str, Any]:
    created = owner.post("/api/v1/tours", json=draft_body(place, minimum=minimum, maximum=maximum, policy_name=policy_name))
    assert created.status_code == 201, created.text
    public_id = created.json()["public_id"]
    published = owner.post(f"/api/v1/tours/{public_id}/publish", json={"accept_rules": True})
    assert published.status_code == 200, published.text
    return published.json()


def join_and_approve(owner: TestClient, member: TestClient, public_id: str) -> dict[str, Any]:
    requested = member.post(f"/api/v1/tours/{public_id}/requests", json={"accept_rules": True, "message": "I agree with the plan."})
    assert requested.status_code == 201, requested.text
    decided = owner.post(f"/api/v1/tours/{public_id}/requests/{requested.json()['id']}/approve")
    assert decided.status_code == 200, decided.text
    return decided.json()


def test_ac01_unverified_member_sees_landing_state_but_no_tour_data(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue
) -> None:
    member = admin.staff_client(client, postgres_session, fake, "member@example.com", None, "203.0.113.180", aal="aal1")
    state = member.get("/api/v1/tours/access")
    assert state.status_code == 200 and state.json() == {"access": False, "reason": "NOT_VERIFIED"}
    refused = member.get("/api/v1/me/tours")
    assert refused.status_code == 404 and refused.json()["error"]["code"] == "NOT_FOUND"


def test_tour_creation_idempotency_replays_and_rejects_key_reuse(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue
) -> None:
    place = destination(postgres_session)
    owner = verified(client, postgres_session, fake, "owner@example.com", "203.0.113.179")
    body = draft_body(place)
    key = str(uuid.uuid4())

    first = owner.post("/api/v1/tours", json=body, headers={"Idempotency-Key": key})
    replay = owner.post("/api/v1/tours", json=body, headers={"Idempotency-Key": key})

    assert first.status_code == replay.status_code == 201
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert replay.json() == first.json()
    assert postgres_session.scalar(select(func.count()).select_from(Tour)) == 1

    changed = owner.post("/api/v1/tours", json=body | {"title": "A different valid tour title"}, headers={"Idempotency-Key": key})
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_ac04_policy_uses_verified_attributes_not_request_data(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue
) -> None:
    place = destination(postgres_session)
    owner = verified(client, postgres_session, fake, "owner@example.com", "203.0.113.181", gender="FEMALE")
    man = verified(client, postgres_session, fake, "man@example.com", "203.0.113.182", gender="MALE")
    tour = create_and_publish(owner, place, policy_name="WOMEN")
    hidden = man.get("/api/v1/tours/search")
    assert hidden.status_code == 200 and hidden.json()["items"] == []
    direct = man.post(f"/api/v1/tours/{tour['public_id']}/requests", json={"accept_rules": True, "gender": "FEMALE"})
    assert direct.status_code == 409 and direct.json()["error"]["code"] == "POLICY_NOT_MET"


def test_ac06_confirmation_chat_budget_and_safety_are_transactional(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue
) -> None:
    place = destination(postgres_session)
    owner = verified(client, postgres_session, fake, "owner@example.com", "203.0.113.183")
    first = verified(client, postgres_session, fake, "first@example.com", "203.0.113.184")
    second = verified(client, postgres_session, fake, "second@example.com", "203.0.113.185")
    tour = create_and_publish(owner, place, minimum=3)
    join_and_approve(owner, first, tour["public_id"])
    before = owner.get(f"/api/v1/tours/{tour['public_id']}").json()
    assert before["lifecycle"] == "RECRUITING" and not before["modules"]["discussion"]
    join_and_approve(owner, second, tour["public_id"])
    confirmed = owner.get(f"/api/v1/tours/{tour['public_id']}")
    assert confirmed.status_code == 200, confirmed.text
    view = confirmed.json()
    assert view["lifecycle"] == "CONFIRMED" and view["confirmed_at"]
    assert view["modules"]["discussion"] and view["modules"]["budget"] and view["modules"]["safety"]
    assert postgres_session.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.topic == "tour.confirmed")) == 1

    sent = first.post(f"/api/v1/tours/{tour['public_id']}/messages", json={"client_msg_id": str(uuid.uuid4()), "body": "Hello tourmates"})
    assert sent.status_code == 201, sent.text
    history = second.get(f"/api/v1/tours/{tour['public_id']}/messages")
    assert history.status_code == 200 and any(item["body"] == "Hello tourmates" for item in history.json()["items"])

    user_ids = [str(fake.users[address]["id"]) for address in ("owner@example.com", "first@example.com", "second@example.com")]
    expense = owner.post(
        f"/api/v1/tours/{tour['public_id']}/expenses",
        json={"amount_paisa": 900, "description": "Tea", "category": "FOOD", "paid_by": user_ids[0], "shares": {value: 300 for value in user_ids}},
    )
    assert expense.status_code == 201, expense.text
    row = postgres_session.scalar(select(Tour).where(Tour.public_id == tour["public_id"]))
    assert row is not None
    net, transfers = workspace.balances(postgres_session, row.id)
    assert sum(net.values()) == 0 and sum(item["amount_paisa"] for item in transfers) == 600

    contact = first.put(f"/api/v1/tours/{tour['public_id']}/safety/me", json={"contact": {"name": "Mina", "relationship": "Sister", "phone": "+8801711000000"}, "medical_notes": "Peanut allergy"})
    assert contact.status_code == 200, contact.text
    profile = postgres_session.scalar(select(SafetyProfile).join(TourMember, TourMember.id == SafetyProfile.member_id).where(TourMember.user_id == uuid.UUID(str(fake.users["first@example.com"]["id"]))))
    assert profile is not None and b"Mina" not in (profile.contact_sealed or b"") and b"Peanut" not in (profile.medical_sealed or b"")


def test_ac13_code_rotation_and_staff_suspend_restore(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue
) -> None:
    place = destination(postgres_session)
    owner = verified(client, postgres_session, fake, "owner@example.com", "203.0.113.186")
    viewer = verified(client, postgres_session, fake, "viewer@example.com", "203.0.113.187")
    tour = create_and_publish(owner, place, minimum=2, policy_name="INVITE_ONLY")
    old_code = tour["code"]
    assert viewer.get(f"/api/v1/tours/by-code/{old_code}").status_code == 200
    rotated = owner.post(f"/api/v1/tours/{tour['public_id']}/code/regenerate")
    assert rotated.status_code == 200 and rotated.json()["code"] != old_code
    assert viewer.get(f"/api/v1/tours/by-code/{old_code}").status_code == 404

    moderator = admin.staff_client(client, postgres_session, fake, "mod@example.com", "moderator", "203.0.113.188")
    stopped = moderator.post(f"/api/v1/admin/tours/{tour['public_id']}/suspend", json={"reason_code": "safety", "note": "Safety report under review"})
    assert stopped.status_code == 200 and stopped.json()["suspended"]
    assert viewer.get(f"/api/v1/tours/by-code/{rotated.json()['code']}").status_code == 404
    restored = moderator.post(f"/api/v1/admin/tours/{tour['public_id']}/restore", json={"reason_code": "resolved"})
    assert restored.status_code == 200 and not restored.json()["suspended"]


def test_permission_matrix_matches_spec_table() -> None:
    assert policy.can("CREATOR", "tour.edit_key_details")
    assert not policy.can("CO_ORGANIZER", "tour.edit_key_details")
    assert policy.can("CO_ORGANIZER", "tour.approve")
    assert not policy.can("TOURMATE", "tour.approve")
    assert policy.can("TOURMATE", "expense.add")
    assert not policy.can("TOURMATE", "safety.meeting_points")
