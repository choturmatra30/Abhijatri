"""Anonymous guest counter behind the landing-page welcome (Review.md 3.2 step 1)."""

import secrets
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, sessionmaker

from app import crypto
from app.abuse import get_counter_session_factory
from app.config import get_settings
from app.db import get_session
from app.guest_services import guest_visit_stats, register_guest_visit
from app.limits import limiter
from app.main import create_app
from app.models import GuestVisit


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    limiter.reset()


def _secret() -> str:
    return secrets.token_urlsafe(32)  # 43 characters, like getGuestScopeSecret()


# ---- schema and HTTP guardrails (no database) ----


def _offline_client() -> TestClient:
    application = create_app()
    application.dependency_overrides[get_session] = lambda: None
    return TestClient(application)


def test_a_name_is_never_accepted() -> None:
    response = _offline_client().post(
        "/api/v1/guest-visits", json={"guest_scope_secret": _secret(), "name": "Sadia"}
    )
    assert response.status_code == 422
    assert {(e["field"], e["code"]) for e in response.json()["error"]["field_errors"]} == {
        ("name", "UNKNOWN_FIELD")
    }


@pytest.mark.parametrize("body", [{}, {"guest_scope_secret": "short"}, {"guest_scope_secret": "x" * 201}])
def test_secret_shape_is_validated(body: dict[str, str]) -> None:
    assert _offline_client().post("/api/v1/guest-visits", json=body).status_code == 422


def test_visit_digest_cannot_match_a_review_scope_digest() -> None:
    secret, key_id = _secret(), crypto.current_key_id()
    assert crypto.digest(crypto.GUEST_VISIT_LABEL, key_id, secret) != crypto.digest(
        crypto.GUEST_SCOPE_LABEL, key_id, secret
    )


# ---- PostgreSQL ----


@pytest.mark.integration
def test_same_device_keeps_its_number_and_new_devices_count_up(postgres_session) -> None:
    first = _secret()
    number, total = register_guest_visit(postgres_session, first)
    postgres_session.commit()
    again, total_again = register_guest_visit(postgres_session, first)
    postgres_session.commit()
    second, total_second = register_guest_visit(postgres_session, _secret())
    postgres_session.commit()

    assert again == number
    assert (total, total_again) == (1, 1)
    assert second == number + 1
    assert total_second == 2


@pytest.mark.integration
def test_table_stores_no_name_and_no_raw_secret(postgres_session) -> None:
    secret = _secret()
    register_guest_visit(postgres_session, secret)
    postgres_session.commit()
    columns = {column["name"] for column in inspect(postgres_session.get_bind()).get_columns("guest_visits")}
    assert columns == {"scope_hash", "key_id", "guest_number", "first_seen_at", "last_seen_at"}
    row = postgres_session.scalar(select(GuestVisit))
    assert row is not None and secret.encode() not in row.scope_hash


@pytest.mark.integration
def test_stats_count_today_in_the_display_time_zone(postgres_session) -> None:
    register_guest_visit(postgres_session, _secret())
    old = register_guest_visit(postgres_session, _secret())
    postgres_session.commit()
    row = postgres_session.scalar(select(GuestVisit).where(GuestVisit.guest_number == old[0]))
    assert row is not None
    row.first_seen_at = datetime.now(UTC) - timedelta(days=3)
    postgres_session.commit()
    assert guest_visit_stats(postgres_session) == (2, 1)


@pytest.fixture()
def client(postgres_session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("RATE_LIMIT_GUEST_VISIT", "1000/minute")
    get_settings.cache_clear()
    application = create_app()
    factory = sessionmaker(bind=postgres_session.get_bind(), expire_on_commit=False)

    def session_override() -> Generator[Session, None, None]:
        yield postgres_session

    application.dependency_overrides[get_session] = session_override
    application.dependency_overrides[get_counter_session_factory] = lambda: factory
    yield TestClient(application)
    get_settings.cache_clear()


@pytest.mark.integration
def test_guest_visit_routes_over_http(client: TestClient) -> None:
    secret = _secret()
    first = client.post("/api/v1/guest-visits", json={"guest_scope_secret": secret})
    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    assert first.json() == {"guest_number": first.json()["guest_number"], "total_guests": 1}
    repeat = client.post("/api/v1/guest-visits", json={"guest_scope_secret": secret})
    assert repeat.json() == first.json()

    stats = client.get("/api/v1/guest-visits/stats")
    assert stats.status_code == 200
    assert stats.json() == {"total_guests": 1, "guests_today": 1}
    assert stats.headers["cache-control"].startswith("public")


@pytest.mark.integration
def test_guest_visits_are_rate_limited_per_network(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUEST_VISITS_PER_NETWORK_PER_HOUR", "2")
    get_settings.cache_clear()
    codes = [
        client.post("/api/v1/guest-visits", json={"guest_scope_secret": _secret()}).status_code
        for _ in range(3)
    ]
    assert codes == [200, 200, 429]
