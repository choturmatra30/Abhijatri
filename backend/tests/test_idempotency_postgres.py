"""R16: Idempotency-Key replay on PostgreSQL (API.md section 3, Gantt R16 acceptance:
"unique constraint and retry tests pass")."""

import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import test_auth as support
import test_review_crud as crud
from fastapi.testclient import TestClient
from pydantic import BaseModel
from receipts import new_receipt
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app import idempotency as idem
from app.errors import ApiError
from app.jobs import retention
from app.models import (
    Appeal,
    RateLimitBucket,
    RequestIdempotency,
    Review,
    ReviewRevision,
    ReviewStatus,
)

auth_env = support.auth_env
fake = support.fake
redis_fake = support.redis_fake
_reset_limiter = support._reset_limiter  # noqa: SLF001
pytestmark = pytest.mark.integration
API = "/api/v1"


@pytest.fixture()
def client(auth_env: None, postgres_session: Session, fake: support.FakeGoTrue, redis_fake: Any) -> TestClient:
    return support.make_client(postgres_session, fake, redis_fake)


def _key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


def _rows(session: Session) -> int:
    session.expire_all()
    return int(session.scalar(select(func.count()).select_from(RequestIdempotency)) or 0)


def _reviews(session: Session) -> int:
    session.expire_all()
    return int(session.scalar(select(func.count()).select_from(Review)) or 0)


def _guest_body(destination: Any, **overrides: Any) -> dict[str, Any]:
    return {
        **crud._body(destination),  # noqa: SLF001
        "guest_scope_secret": "q" * 43,
        "guest_display_name": "Rahim",
        "turnstile_token": "token-one",
        **overrides,
    }


# ============================ guest create ============================


def test_guest_create_with_a_key_stores_one_response_and_a_retry_creates_nothing(client: TestClient, postgres_session: Session) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    guest = crud._anonymous(client)  # noqa: SLF001
    body, key = _guest_body(destination), _key()

    first = guest.post(f"{API}/reviews/guest", json=body, headers=key)
    assert first.status_code == 201, first.text
    assert first.headers["cache-control"] == "no-store"
    # A retry with a fresh challenge token: the same draft is recovered (order of checks step 2).
    retry = guest.post(f"{API}/reviews/guest", json={**body, "turnstile_token": "token-two"}, headers=key)
    assert retry.status_code == 200 and retry.json()["review_id"] == first.json()["review_id"]
    assert retry.json()["duplicate_recovered"] is True
    assert _reviews(postgres_session) == 1
    assert _rows(postgres_session) == 1


def test_guest_create_replays_the_stored_response_when_the_draft_lookup_cannot(
    client: TestClient, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Step 3 on its own: with step 2 out of the way, the stored 201 is returned unchanged."""
    import app.api as api_module

    destination = crud._destination(postgres_session)  # noqa: SLF001
    guest = crud._anonymous(client)  # noqa: SLF001
    body, key = _guest_body(destination), _key()
    first = guest.post(f"{API}/reviews/guest", json=body, headers=key)
    assert first.status_code == 201

    monkeypatch.setattr(api_module, "find_recoverable_draft", lambda session, payload: None)
    replay = guest.post(f"{API}/reviews/guest", json={**body, "turnstile_token": "token-two"}, headers=key)
    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert replay.headers["idempotent-replayed"] == "true"
    assert _reviews(postgres_session) == 1


def test_a_key_reused_for_another_draft_is_refused(client: TestClient, postgres_session: Session) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    guest = crud._anonymous(client)  # noqa: SLF001
    key = _key()
    assert guest.post(f"{API}/reviews/guest", json=_guest_body(destination), headers=key).status_code == 201
    other = guest.post(f"{API}/reviews/guest", json=_guest_body(destination, title="Another trip entirely"), headers=key)
    assert other.status_code == 409
    assert other.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert _reviews(postgres_session) == 1


def test_a_malformed_key_is_refused_before_anything_is_written(client: TestClient, postgres_session: Session) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    guest = crud._anonymous(client)  # noqa: SLF001
    response = guest.post(f"{API}/reviews/guest", json=_guest_body(destination), headers={"Idempotency-Key": "abc"})
    assert response.status_code == 422
    assert response.json()["error"]["field_errors"] == [{"field": "Idempotency-Key", "code": "INVALID_VALUE"}]
    assert _reviews(postgres_session) == 0 and _rows(postgres_session) == 0


def test_without_a_key_nothing_is_stored(client: TestClient, postgres_session: Session) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    guest = crud._anonymous(client)  # noqa: SLF001
    assert guest.post(f"{API}/reviews/guest", json=_guest_body(destination)).status_code == 201
    assert _rows(postgres_session) == 0


def test_the_same_key_in_two_guest_scopes_is_two_requests(client: TestClient, postgres_session: Session) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    guest = crud._anonymous(client)  # noqa: SLF001
    key = _key()
    one = guest.post(f"{API}/reviews/guest", json=_guest_body(destination, guest_scope_secret="a" * 43), headers=key)
    two = guest.post(f"{API}/reviews/guest", json=_guest_body(destination, guest_scope_secret="b" * 43), headers=key)
    assert one.status_code == two.status_code == 201
    assert one.json()["review_id"] != two.json()["review_id"]
    assert _rows(postgres_session) == 2


# ============================ member create ============================


def test_member_create_replays_by_key(client: TestClient, postgres_session: Session, fake: support.FakeGoTrue) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    member = crud._member(client, postgres_session, fake, "idem-member@example.com", "203.0.113.90")  # noqa: SLF001
    body, key = crud._body(destination), _key()  # noqa: SLF001
    first = member.post(f"{API}/reviews/member", json=body, headers=key)
    assert first.status_code == 201, first.text
    replay = member.post(f"{API}/reviews/member", json=body, headers=key)
    assert replay.status_code == 201 and replay.json() == first.json()
    assert replay.headers["idempotent-replayed"] == "true"
    assert _reviews(postgres_session) == 1


def test_member_create_also_recovers_by_client_draft_id_without_a_key(
    client: TestClient, postgres_session: Session, fake: support.FakeGoTrue
) -> None:
    """Handoff R16: the member route has the same client_draft_id recovery as the guest route."""
    destination = crud._destination(postgres_session)  # noqa: SLF001
    member = crud._member(client, postgres_session, fake, "draft-member@example.com", "203.0.113.91")  # noqa: SLF001
    body = crud._body(destination)  # noqa: SLF001
    first = member.post(f"{API}/reviews/member", json=body)
    again = member.post(f"{API}/reviews/member", json=body)
    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["review_id"] == first.json()["review_id"] and again.json()["duplicate_recovered"] is True
    assert _reviews(postgres_session) == 1


def test_one_key_on_two_endpoints_is_two_requests(client: TestClient, postgres_session: Session, fake: support.FakeGoTrue) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    member = crud._member(client, postgres_session, fake, "two-endpoints@example.com", "203.0.113.92")  # noqa: SLF001
    key = _key()
    created = member.post(f"{API}/reviews/member", json=crud._body(destination), headers=key)  # noqa: SLF001
    assert created.status_code == 201
    review_id = created.json()["review_id"]
    withdrawn = member.post(f"{API}/reviews/{review_id}/withdraw", json={"expected_version": 1}, headers=key)
    assert withdrawn.status_code == 200 and withdrawn.json()["status"] == "WITHDRAWN"
    assert _rows(postgres_session) == 2


# ============================ edit ============================


def test_a_retried_member_edit_replays_instead_of_conflicting(client: TestClient, postgres_session: Session, fake: support.FakeGoTrue) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    member = crud._member(client, postgres_session, fake, "edit-member@example.com", "203.0.113.93")  # noqa: SLF001
    review_id = crud._member_review(member, destination)  # noqa: SLF001
    key = _key()
    first = member.patch(f"{API}/reviews/{review_id}/pending", json={"expected_version": 1, "title": "Edited title"}, headers=key)
    assert first.status_code == 200, first.text
    replay = member.patch(f"{API}/reviews/{review_id}/pending", json={"expected_version": 1, "title": "Edited title"}, headers=key)
    assert replay.status_code == 200 and replay.json() == first.json()
    assert replay.headers["idempotent-replayed"] == "true"
    without_key = member.patch(f"{API}/reviews/{review_id}/pending", json={"expected_version": 1, "title": "Edited title"})
    assert without_key.status_code == 409 and without_key.json()["error"]["code"] == "REVIEW_VERSION_CONFLICT"
    postgres_session.expire_all()
    revisions = postgres_session.scalar(select(func.count()).select_from(ReviewRevision).where(ReviewRevision.review_id == uuid.UUID(review_id)))
    assert revisions == 2, "one original revision and exactly one edit"


def test_a_retried_guest_edit_replays_with_the_receipt(client: TestClient, postgres_session: Session) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    receipt = new_receipt()
    review = crud._guest_review(postgres_session, destination, receipt)  # noqa: SLF001
    guest = crud._anonymous(client)  # noqa: SLF001
    key = _key()
    request = {"expected_version": 1, "receipt_secret": receipt, "body": "A corrected review body that is long enough."}
    first = guest.patch(f"{API}/reviews/{review.id}/pending", json=request, headers=key)
    replay = guest.patch(f"{API}/reviews/{review.id}/pending", json=request, headers=key)
    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json() and replay.headers["idempotent-replayed"] == "true"


def test_a_different_body_under_the_same_edit_key_is_refused(client: TestClient, postgres_session: Session, fake: support.FakeGoTrue) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    member = crud._member(client, postgres_session, fake, "edit-reuse@example.com", "203.0.113.94")  # noqa: SLF001
    review_id = crud._member_review(member, destination)  # noqa: SLF001
    key = _key()
    assert member.patch(f"{API}/reviews/{review_id}/pending", json={"expected_version": 1, "title": "First edit"}, headers=key).status_code == 200
    reused = member.patch(f"{API}/reviews/{review_id}/pending", json={"expected_version": 2, "title": "Second edit"}, headers=key)
    assert reused.status_code == 409 and reused.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


# ============================ withdraw ============================


def test_a_retried_guest_withdraw_replays_the_first_answer(client: TestClient, postgres_session: Session) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    receipt = new_receipt()
    review = crud._guest_review(postgres_session, destination, receipt)  # noqa: SLF001
    guest = crud._anonymous(client)  # noqa: SLF001
    key, request = _key(), {"expected_version": 1, "receipt_secret": receipt}
    first = guest.post(f"{API}/reviews/{review.id}/withdraw", json=request, headers=key)
    replay = guest.post(f"{API}/reviews/{review.id}/withdraw", json=request, headers=key)
    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json() and first.json()["status"] == "WITHDRAWN"
    assert replay.headers["idempotent-replayed"] == "true"


def test_a_wrong_receipt_never_reaches_a_stored_replay(client: TestClient, postgres_session: Session) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    receipt = new_receipt()
    review = crud._guest_review(postgres_session, destination, receipt)  # noqa: SLF001
    guest = crud._anonymous(client)  # noqa: SLF001
    key = _key()
    assert guest.post(f"{API}/reviews/{review.id}/withdraw", json={"expected_version": 1, "receipt_secret": receipt}, headers=key).status_code == 200
    stranger = guest.post(f"{API}/reviews/{review.id}/withdraw", json={"expected_version": 1, "receipt_secret": new_receipt()}, headers=key)
    assert stranger.status_code == 404 and stranger.json()["error"]["code"] == "RECEIPT_NOT_FOUND"


def test_a_failed_write_stores_nothing_and_the_retry_runs_again(client: TestClient, postgres_session: Session, fake: support.FakeGoTrue) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    member = crud._member(client, postgres_session, fake, "fail-then-ok@example.com", "203.0.113.95")  # noqa: SLF001
    review_id = crud._member_review(member, destination)  # noqa: SLF001
    key = _key()
    stale = member.post(f"{API}/reviews/{review_id}/withdraw", json={"expected_version": 9}, headers=key)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "REVIEW_VERSION_CONFLICT"
    assert _rows(postgres_session) == 0, "an error leaves no key behind"
    # The corrected request may reuse the key: the failed attempt left nothing to conflict with.
    ok = member.post(f"{API}/reviews/{review_id}/withdraw", json={"expected_version": 1}, headers=key)
    assert ok.status_code == 200 and ok.json()["status"] == "WITHDRAWN"
    assert _rows(postgres_session) == 1
    postgres_session.expire_all()
    assert postgres_session.get(Review, uuid.UUID(review_id)).status == ReviewStatus.WITHDRAWN  # type: ignore[union-attr]


# ============================ guest appeal ============================


def test_a_retried_guest_appeal_creates_one_appeal(client: TestClient, postgres_session: Session, fake: support.FakeGoTrue) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    receipt = new_receipt()
    review = crud._guest_review(postgres_session, destination, receipt)  # noqa: SLF001
    rejected = crud._moderate(client, postgres_session, fake, review.id, "REJECT", "idem-mod@example.com", "203.0.113.96", reason="spam")  # noqa: SLF001
    assert rejected.status_code == 200, rejected.text
    guest = crud._anonymous(client)  # noqa: SLF001
    key = _key()
    request = {"review_id": str(review.id), "receipt_secret": receipt, "statement": "Please look again at my honest review of the trip."}
    first = guest.post(f"{API}/review-receipts/appeals", json=request, headers=key)
    replay = guest.post(f"{API}/review-receipts/appeals", json=request, headers=key)
    assert first.status_code == replay.status_code == 201
    assert replay.json() == first.json() and replay.headers["idempotent-replayed"] == "true"
    postgres_session.expire_all()
    assert postgres_session.scalar(select(func.count()).select_from(Appeal)) == 1


# ============================ storage, expiry, concurrency ============================


def test_nothing_secret_is_stored(client: TestClient, postgres_session: Session) -> None:
    destination = crud._destination(postgres_session)  # noqa: SLF001
    guest = crud._anonymous(client)  # noqa: SLF001
    body, key = _guest_body(destination), _key()
    assert guest.post(f"{API}/reviews/guest", json=body, headers=key).status_code == 201
    postgres_session.expire_all()
    row = postgres_session.scalars(select(RequestIdempotency)).one()
    dumped = repr((row.scope_digest, row.endpoint, row.key_digest, row.fingerprint, row.response))
    for secret in (key["Idempotency-Key"], body["receipt_secret"], body["guest_scope_secret"]):
        assert secret not in dumped
    assert row.endpoint == idem.Endpoint.GUEST_REVIEW_CREATE
    assert set(row.response) == {"review_id", "status", "version", "duplicate_recovered"}
    assert timedelta(hours=71, minutes=59) < row.expires_at - row.created_at <= timedelta(hours=72)


def test_the_primary_key_is_the_unique_constraint(postgres_session: Session) -> None:
    now = datetime.now(UTC)
    values = {
        "scope_digest": b"s" * 32,
        "endpoint": "reviews.withdraw",
        "key_digest": "a" * 64,
        "fingerprint": "b" * 64,
        "status_code": 200,
        "response": {},
        "created_at": now,
        "expires_at": now + timedelta(hours=72),
    }
    postgres_session.add(RequestIdempotency(**values))
    postgres_session.commit()
    postgres_session.add(RequestIdempotency(**values))
    with pytest.raises(IntegrityError):
        postgres_session.commit()
    postgres_session.rollback()


def _begin(session: Session, key: str, fingerprint: str = "f" * 64) -> idem.Claim | idem.Replay | None:
    return idem.begin(session, key=key, scope=b"t" * 32, endpoint="test.endpoint", request_fingerprint=fingerprint)


class _Stored(BaseModel):
    value: int


def test_an_expired_row_is_replaced_and_purged(postgres_session: Session) -> None:
    key = str(uuid.uuid4())
    claim = _begin(postgres_session, key)
    assert isinstance(claim, idem.Claim)
    idem.finish(postgres_session, claim, 200, _Stored(value=1))
    postgres_session.commit()
    assert isinstance(_begin(postgres_session, key), idem.Replay)
    postgres_session.rollback()

    postgres_session.execute(text("UPDATE request_idempotency SET created_at = created_at - interval '80 hours', expires_at = expires_at - interval '80 hours'"))
    postgres_session.commit()
    again = _begin(postgres_session, key, fingerprint="e" * 64)
    assert isinstance(again, idem.Claim), "an expired key is free again, even with another body"
    postgres_session.rollback()

    factory = sessionmaker(bind=postgres_session.get_bind(), expire_on_commit=False)
    assert retention.purge_idempotency(factory, datetime.now(UTC)) == 1
    assert _rows(postgres_session) == 0


def test_a_concurrent_twin_waits_and_then_replays(postgres_session: Session) -> None:
    factory = sessionmaker(bind=postgres_session.get_bind(), expire_on_commit=False)
    key = str(uuid.uuid4())
    first = factory()
    claim = _begin(first, key)
    assert isinstance(claim, idem.Claim)
    outcome: dict[str, Any] = {}

    def twin() -> None:
        with factory() as second:
            outcome["result"] = _begin(second, key)
            second.rollback()

    thread = threading.Thread(target=twin)
    thread.start()
    thread.join(timeout=0.5)
    assert thread.is_alive(), "the twin waits on the reservation"
    idem.finish(first, claim, 201, _Stored(value=7))
    first.commit()
    first.close()
    thread.join(timeout=5)
    result = outcome["result"]
    assert isinstance(result, idem.Replay) and result.status_code == 201 and result.body == {"value": 7}


def test_a_twin_runs_itself_when_the_first_request_fails(postgres_session: Session) -> None:
    factory = sessionmaker(bind=postgres_session.get_bind(), expire_on_commit=False)
    key = str(uuid.uuid4())
    first = factory()
    assert isinstance(_begin(first, key), idem.Claim)
    outcome: dict[str, Any] = {}

    def twin() -> None:
        with factory() as second:
            outcome["result"] = _begin(second, key)
            second.rollback()

    thread = threading.Thread(target=twin)
    thread.start()
    thread.join(timeout=0.5)
    first.rollback()  # the first request failed
    first.close()
    thread.join(timeout=5)
    assert isinstance(outcome["result"], idem.Claim)


def test_a_twin_that_waits_too_long_is_told_to_retry(postgres_session: Session) -> None:
    factory = sessionmaker(bind=postgres_session.get_bind(), expire_on_commit=False)
    key = str(uuid.uuid4())
    first = factory()
    assert isinstance(_begin(first, key), idem.Claim)
    try:
        with factory() as second:
            second.execute(text("SET LOCAL lock_timeout = '200ms'"))
            with pytest.raises(ApiError) as caught:
                _begin(second, key)
            assert caught.value.code == "IDEMPOTENCY_REQUEST_IN_PROGRESS"
            assert caught.value.headers == {"Retry-After": "1"}
            second.rollback()
    finally:
        first.rollback()
        first.close()


def _bucket_total(session: Session, prefix: str) -> int:
    session.expire_all()
    return int(session.scalar(select(func.coalesce(func.sum(RateLimitBucket.count), 0)).where(RateLimitBucket.rule.like(f"{prefix}%"))) or 0)


def test_a_guest_replay_spends_no_durable_counter(client: TestClient, postgres_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api as api_module

    destination = crud._destination(postgres_session)  # noqa: SLF001
    guest = crud._anonymous(client)  # noqa: SLF001
    body, key = _guest_body(destination), _key()
    assert guest.post(f"{API}/reviews/guest", json=body, headers=key).status_code == 201
    counted = _bucket_total(postgres_session, "guest_submit")
    assert counted > 0
    monkeypatch.setattr(api_module, "find_recoverable_draft", lambda session, payload: None)
    replay = guest.post(f"{API}/reviews/guest", json=body, headers=key)
    assert replay.headers["idempotent-replayed"] == "true"
    assert _bucket_total(postgres_session, "guest_submit") == counted


def test_a_receipt_replay_still_counts_as_a_receipt_operation(client: TestClient, postgres_session: Session) -> None:
    """The receipt is proven before the lookup, so its limits keep guarding brute force (API.md section 3)."""
    destination = crud._destination(postgres_session)  # noqa: SLF001
    receipt = new_receipt()
    review = crud._guest_review(postgres_session, destination, receipt)  # noqa: SLF001
    guest = crud._anonymous(client)  # noqa: SLF001
    key, request = _key(), {"expected_version": 1, "receipt_secret": receipt}
    assert guest.post(f"{API}/reviews/{review.id}/withdraw", json=request, headers=key).status_code == 200
    counted = _bucket_total(postgres_session, "receipt")
    assert guest.post(f"{API}/reviews/{review.id}/withdraw", json=request, headers=key).headers["idempotent-replayed"] == "true"
    assert _bucket_total(postgres_session, "receipt") > counted
