"""Durable counters, limits, pending ceilings, kill switch and the submission order (PF 14)."""

import logging
import uuid
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from receipts import new_receipt
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app import abuse
from app.abuse import Rule, get_counter_session_factory
from app.config import get_settings
from app.db import get_session
from app.errors import ApiError
from app.limits import limiter
from app.main import create_app
from app.models import Destination, DestinationStatus, RateLimitBucket, Review
from app.turnstile import ACTION_GUEST_REVIEW, get_turnstile_verifier

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    limiter.reset()


class FakeVerifier:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.failure: ApiError | None = None

    def __call__(self, token: str | None, *, action: str, remote_address: str | None) -> None:
        self.calls.append({"token": token, "action": action, "remote_address": remote_address})
        if self.failure is not None:
            raise self.failure


class Harness:
    def __init__(self, client: TestClient, session: Session, factory: sessionmaker[Session], verifier: FakeVerifier) -> None:
        self.client, self.session, self.factory, self.verifier = client, session, factory, verifier

    def destination(self, name: str = "Cox") -> Destination:
        destination = Destination(status=DestinationStatus.PUBLISHED, name_bn=f"{name} bn", name_en=name)
        self.session.add(destination)
        self.session.commit()
        return destination

    def bucket_total(self, rule_prefix: str) -> int:
        with self.factory() as session:
            return int(
                session.scalar(
                    select(func.coalesce(func.sum(RateLimitBucket.count), 0)).where(
                        RateLimitBucket.rule.like(f"{rule_prefix}%")
                    )
                )
                or 0
            )

    def payload(self, destination: Destination, **overrides: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "destination_id": str(destination.id),
            "client_draft_id": str(uuid.uuid4()),
            "guest_scope_secret": uuid.uuid4().hex + uuid.uuid4().hex[:12],
            "receipt_secret": new_receipt(),
            "turnstile_token": "tok",
            "guest_display_name": "Rahim",
            "language": "EN",
            "traveller_type": "SOLO",
            "comfort_tier": "STANDARD",
            "visit_month": date.today().replace(day=1).isoformat(),
            "title": "Lovely beach",
            "body": "A long enough review body for the validation rules.",
            "overall_rating": 5,
            "consent_version": "v1",
        }
        body.update(overrides)
        return body

    def submit(self, body: dict[str, Any], address: str | None = None) -> Any:
        headers = {"X-Forwarded-For": address} if address else {}
        return self.client.post("/api/v1/reviews/guest", json=body, headers=headers)


@pytest.fixture()
def harness(postgres_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[Harness, None, None]:
    monkeypatch.setenv("CLIENT_ADDRESS_HEADER", "X-Forwarded-For")
    # The in-memory burst pre-filter is exercised on its own; keep it out of the way elsewhere.
    monkeypatch.setenv("RATE_LIMIT_GUEST_SUBMIT", "1000/minute")
    monkeypatch.setenv("RATE_LIMIT_RECEIPT", "1000/minute")
    get_settings.cache_clear()
    application = create_app()
    factory = sessionmaker(bind=postgres_session.get_bind(), expire_on_commit=False)
    verifier = FakeVerifier()

    def session_override() -> Generator[Session, None, None]:
        yield postgres_session

    application.dependency_overrides[get_session] = session_override
    application.dependency_overrides[get_counter_session_factory] = lambda: factory
    application.dependency_overrides[get_turnstile_verifier] = lambda: verifier
    yield Harness(TestClient(application), postgres_session, factory, verifier)
    get_settings.cache_clear()


@pytest.fixture()
def configure(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    def apply(**env: str) -> None:
        for name, value in env.items():
            monkeypatch.setenv(name.upper(), value)
        get_settings.cache_clear()

    return apply


# ---------- the counter primitive ----------

NOW = datetime(2026, 10, 19, 10, 30, 15, tzinfo=UTC)


def test_hit_counts_and_reports_retry_after_only_over_the_limit(harness: Harness) -> None:
    rule, key = Rule("t:hour", 3600, 2), b"k" * 32
    assert abuse.hit(harness.factory, rule, key, now=NOW) == (1, None)
    assert abuse.hit(harness.factory, rule, key, now=NOW) == (2, None)
    count, wait = abuse.hit(harness.factory, rule, key, now=NOW)
    assert (count, wait) == (3, 1785)  # 10:30:15 -> window ends 11:00:00
    assert abuse.peek(harness.factory, rule, key, now=NOW) == 1785


def test_window_rollover_and_key_isolation(harness: Harness) -> None:
    rule = Rule("t:hour", 3600, 1)
    abuse.hit(harness.factory, rule, b"a" * 32, now=NOW)
    assert abuse.hit(harness.factory, rule, b"a" * 32, now=NOW)[1] is not None
    assert abuse.hit(harness.factory, rule, b"b" * 32, now=NOW) == (1, None)
    assert abuse.hit(harness.factory, rule, b"a" * 32, now=NOW + timedelta(hours=1)) == (1, None)


def test_concurrent_hits_are_all_counted_exactly_once(harness: Harness) -> None:
    rule, key = Rule("t:concurrent", 3600, 1000), b"c" * 32
    with ThreadPoolExecutor(max_workers=12) as pool:
        counts = list(pool.map(lambda _: abuse.hit(harness.factory, rule, key, now=NOW)[0], range(40)))
    assert sorted(counts) == list(range(1, 41))


def test_purge_removes_only_old_windows(harness: Harness) -> None:
    rule = Rule("t:purge", 3600, 5)
    abuse.hit(harness.factory, rule, b"o" * 32, now=NOW - timedelta(days=3))
    abuse.hit(harness.factory, rule, b"n" * 32, now=NOW)
    with harness.factory() as session:
        removed = abuse.purge_expired_buckets(session, now=NOW)
        session.commit()
    assert removed == 1
    assert harness.bucket_total("t:purge") == 1


# ---------- guest submission ----------


def test_third_new_draft_per_scope_passes_and_the_fourth_is_rate_limited(harness: Harness) -> None:
    destination = harness.destination()
    scope = "z" * 43
    for _ in range(3):
        assert harness.submit(harness.payload(destination, guest_scope_secret=scope)).status_code == 201
    blocked = harness.submit(harness.payload(destination, guest_scope_secret=scope))
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
    assert 1 <= int(blocked.headers["retry-after"]) <= 86400
    other_scope = harness.submit(harness.payload(destination, guest_scope_secret="y" * 43))
    assert other_scope.status_code == 201


def test_recovering_a_duplicate_is_free_of_counters_and_challenges(harness: Harness) -> None:
    destination = harness.destination()
    body = harness.payload(destination, guest_scope_secret="d" * 43)
    assert harness.submit(body).status_code == 201
    counted = harness.bucket_total("guest_submit")
    challenges = len(harness.verifier.calls)
    for _ in range(5):
        retry = harness.submit(body)
        assert retry.status_code == 200 and retry.json()["duplicate_recovered"] is True
    assert harness.bucket_total("guest_submit") == counted
    assert len(harness.verifier.calls) == challenges


def test_recovery_still_works_after_the_scope_limit_is_reached(harness: Harness) -> None:
    destination = harness.destination()
    scope = "e" * 43
    first = harness.payload(destination, guest_scope_secret=scope)
    assert harness.submit(first).status_code == 201
    for _ in range(2):
        assert harness.submit(harness.payload(destination, guest_scope_secret=scope)).status_code == 201
    assert harness.submit(harness.payload(destination, guest_scope_secret=scope)).status_code == 429
    assert harness.submit(first).status_code == 200


def test_network_hourly_limit_is_per_trusted_address(harness: Harness, configure: Callable[..., None]) -> None:
    configure(guest_submit_per_network_per_hour="2")
    destination = harness.destination()
    codes = [harness.submit(harness.payload(destination), address="203.0.113.10").status_code for _ in range(3)]
    assert codes == [201, 201, 429]
    assert harness.submit(harness.payload(destination), address="203.0.113.11").status_code == 201


def test_forged_left_most_address_does_not_evade_the_network_limit(
    harness: Harness, configure: Callable[..., None]
) -> None:
    configure(guest_submit_per_network_per_hour="1")
    destination = harness.destination()
    assert harness.submit(harness.payload(destination), address="1.1.1.1, 203.0.113.50").status_code == 201
    evade = harness.submit(harness.payload(destination), address="2.2.2.2, 203.0.113.50")
    assert evade.status_code == 429


def test_network_daily_limit(harness: Harness, configure: Callable[..., None]) -> None:
    configure(guest_submit_per_network_per_day="1", guest_submit_per_network_per_hour="50")
    destination = harness.destination()
    assert harness.submit(harness.payload(destination), address="203.0.113.20").status_code == 201
    assert harness.submit(harness.payload(destination), address="203.0.113.20").status_code == 429


def test_attempts_are_counted_even_when_the_business_transaction_fails(harness: Harness) -> None:
    ghost = Destination(id=uuid.uuid4(), status=DestinationStatus.PUBLISHED, name_bn="x", name_en="x")
    response = harness.submit(harness.payload(ghost))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert harness.bucket_total("guest_submit:scope:24h") == 1
    assert harness.session.scalars(select(Review)).all() == []


def test_invalid_receipt_is_rejected_before_anything_is_counted_or_challenged(harness: Harness) -> None:
    destination = harness.destination()
    response = harness.submit(harness.payload(destination, receipt_secret="abr1_nope"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_RECEIPT_FORMAT"
    assert harness.bucket_total("") == 0
    assert harness.verifier.calls == []


# ---------- Turnstile ordering ----------


def test_challenge_runs_once_per_new_draft_with_the_review_action(harness: Harness) -> None:
    destination = harness.destination()
    harness.submit(harness.payload(destination, turnstile_token="abc"), address="203.0.113.77")
    (call,) = harness.verifier.calls
    assert call == {"token": "abc", "action": ACTION_GUEST_REVIEW, "remote_address": "203.0.113.77"}


def test_failed_challenge_creates_nothing_and_counts_nothing(harness: Harness) -> None:
    destination = harness.destination()
    harness.verifier.failure = ApiError("CHALLENGE_FAILED")
    response = harness.submit(harness.payload(destination))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CHALLENGE_FAILED"
    assert harness.session.scalars(select(Review)).all() == []
    assert harness.bucket_total("guest_submit") == 0


# ---------- pending ceilings and the emergency switch ----------


def test_per_destination_pending_ceiling_pauses_only_that_destination(
    harness: Harness, configure: Callable[..., None]
) -> None:
    configure(guest_pending_per_destination="2")
    busy, quiet = harness.destination("Busy"), harness.destination("Quiet")
    assert [harness.submit(harness.payload(busy)).status_code for _ in range(2)] == [201, 201]
    paused = harness.submit(harness.payload(busy))
    assert paused.status_code == 503
    assert paused.json()["error"]["code"] == "GUEST_WRITES_PAUSED"
    assert harness.submit(harness.payload(quiet)).status_code == 201


def test_total_pending_ceiling_pauses_every_destination(harness: Harness, configure: Callable[..., None]) -> None:
    configure(guest_pending_total="2")
    one, two = harness.destination("One"), harness.destination("Two")
    assert harness.submit(harness.payload(one)).status_code == 201
    assert harness.submit(harness.payload(two)).status_code == 201
    assert harness.submit(harness.payload(one)).status_code == 503


def test_alert_is_logged_at_eighty_percent(
    harness: Harness, configure: Callable[..., None], caplog: pytest.LogCaptureFixture
) -> None:
    configure(guest_pending_per_destination="5")
    destination = harness.destination()
    with caplog.at_level(logging.WARNING, logger="app.abuse"):
        for _ in range(3):
            harness.submit(harness.payload(destination))
        assert not [r for r in caplog.records if "pending queue" in r.message]
        harness.submit(harness.payload(destination))  # 3 pending -> checking 4th sees 3 of 5 (60 percent)
        harness.submit(harness.payload(destination))  # sees 4 of 5 (80 percent)
    assert [r for r in caplog.records if "pending queue (destination) at 4 of 5" in r.message]


def test_emergency_switch_pauses_new_guest_writes_but_not_reads_or_recovery(
    harness: Harness, configure: Callable[..., None]
) -> None:
    destination = harness.destination()
    body = harness.payload(destination)
    review_id = harness.submit(body).json()["review_id"]

    configure(guest_writes_paused="true")
    paused = harness.submit(harness.payload(destination))
    assert paused.status_code == 503
    assert paused.json()["error"]["code"] == "GUEST_WRITES_PAUSED"
    assert harness.verifier.calls.__len__() == 1  # no challenge was spent while paused

    assert harness.submit(body).status_code == 200  # recovery is a read of the existing review
    status = harness.client.post(
        "/api/v1/review-receipts/status",
        json={"review_id": review_id, "receipt_secret": body["receipt_secret"]},
    )
    assert status.status_code == 200
    assert harness.client.get("/api/v1/destinations").status_code == 200
    assert harness.client.get(f"/api/v1/destinations/{destination.id}/reviews").status_code == 200


# ---------- receipt operations ----------


def _status(harness: Harness, review_id: str, receipt: str, address: str | None = None) -> Any:
    headers = {"X-Forwarded-For": address} if address else {}
    return harness.client.post(
        "/api/v1/review-receipts/status",
        json={"review_id": review_id, "receipt_secret": receipt},
        headers=headers,
    )


def _submitted(harness: Harness) -> tuple[str, str]:
    destination = harness.destination()
    body = harness.payload(destination)
    return harness.submit(body).json()["review_id"], body["receipt_secret"]


def test_per_receipt_hourly_limit(harness: Harness, configure: Callable[..., None]) -> None:
    configure(receipt_ops_per_receipt_per_hour="3")
    review_id, receipt = _submitted(harness)
    codes = [_status(harness, review_id, receipt, "203.0.113.30").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    limited = _status(harness, review_id, receipt, "203.0.113.31")
    assert limited.status_code == 429  # the receipt is the key, not the address
    assert limited.json()["error"]["code"] == "RATE_LIMITED"


def test_per_network_hourly_limit_across_different_receipts(
    harness: Harness, configure: Callable[..., None]
) -> None:
    configure(receipt_ops_per_network_per_hour="3")
    review_id, receipt = _submitted(harness)
    codes = [_status(harness, review_id, receipt, "203.0.113.40").status_code for _ in range(2)]
    codes.append(_status(harness, str(uuid.uuid4()), new_receipt(), "203.0.113.40").status_code)
    codes.append(_status(harness, review_id, receipt, "203.0.113.40").status_code)
    assert codes == [200, 200, 404, 429]
    assert _status(harness, review_id, receipt, "203.0.113.41").status_code == 200


def test_repeated_failures_trigger_a_progressive_block_even_for_the_right_receipt(
    harness: Harness, configure: Callable[..., None]
) -> None:
    configure(receipt_failures_short_limit="2")
    review_id, receipt = _submitted(harness)
    for _ in range(2):
        assert _status(harness, review_id, new_receipt(), "203.0.113.50").status_code == 404
    blocked = _status(harness, review_id, receipt, "203.0.113.50")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
    assert 1 <= int(blocked.headers["retry-after"]) <= 900
    # A different network is unaffected, so one guesser cannot lock the owner out everywhere.
    assert _status(harness, review_id, receipt, "203.0.113.51").status_code == 200


def test_failures_against_one_receipt_block_it_for_every_network(
    harness: Harness, configure: Callable[..., None]
) -> None:
    configure(receipt_failures_short_limit="2")
    review_id, _ = _submitted(harness)
    guessed = new_receipt()
    assert _status(harness, review_id, guessed, "203.0.113.60").status_code == 404
    assert _status(harness, review_id, guessed, "203.0.113.61").status_code == 404
    assert _status(harness, review_id, guessed, "203.0.113.62").status_code == 429


def test_withdraw_shares_the_receipt_protections(harness: Harness, configure: Callable[..., None]) -> None:
    configure(receipt_failures_short_limit="1")
    review_id, receipt = _submitted(harness)
    url = f"/api/v1/reviews/{review_id}/withdraw"
    wrong = harness.client.post(
        url, json={"receipt_secret": new_receipt(), "expected_version": 1}, headers={"X-Forwarded-For": "203.0.113.70"}
    )
    assert wrong.status_code == 404
    again = harness.client.post(
        url, json={"receipt_secret": receipt, "expected_version": 1}, headers={"X-Forwarded-For": "203.0.113.70"}
    )
    assert again.status_code == 429


def test_in_memory_prefilter_still_caps_bursts(harness: Harness, configure: Callable[..., None]) -> None:
    configure(
        receipt_ops_per_receipt_per_hour="1000",
        receipt_ops_per_network_per_hour="1000",
        rate_limit_receipt="10/minute",
    )
    review_id, receipt = _submitted(harness)
    codes = [_status(harness, review_id, receipt, "203.0.113.80").status_code for _ in range(12)]
    assert codes[:10] == [200] * 10
    assert codes[10:] == [429, 429]
