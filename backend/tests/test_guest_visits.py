"""Guest footprint: a running number and a time per guest visit-day, nothing else."""

from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, sessionmaker

from app.abuse import get_counter_session_factory
from app.config import get_settings
from app.db import get_session
from app.guest_services import guest_visit_stats, record_guest_visit
from app.limits import limiter
from app.main import create_app
from app.models import GuestVisit


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    limiter.reset()


# ---- request guardrails (no database) ----


def _offline_client() -> TestClient:
    application = create_app()
    application.dependency_overrides[get_session] = lambda: None
    return TestClient(application)


@pytest.mark.parametrize(
    "body",
    [{"name": "Sadia"}, {"guest_scope_secret": "x" * 43}, {"device_id": "abc"}],
)
def test_nothing_about_the_guest_is_accepted(body: dict[str, str]) -> None:
    response = _offline_client().post("/api/v1/guest-visits", json=body)
    assert response.status_code == 422
    assert {e["code"] for e in response.json()["error"]["field_errors"]} == {"UNKNOWN_FIELD"}


@pytest.mark.parametrize("days", [0, 91])
def test_stats_window_is_bounded(days: int) -> None:
    assert _offline_client().get(f"/api/v1/guest-visits/stats?days={days}").status_code == 422


# ---- PostgreSQL ----


@pytest.mark.integration
def test_table_holds_only_a_number_and_a_time(postgres_session) -> None:
    columns = {c["name"] for c in inspect(postgres_session.get_bind()).get_columns("guest_visits")}
    assert columns == {"id", "visited_at"}


@pytest.mark.integration
def test_each_visit_adds_one_row_with_the_next_number(postgres_session) -> None:
    first = record_guest_visit(postgres_session)
    second = record_guest_visit(postgres_session)
    postgres_session.commit()
    assert second == first + 1
    assert len(postgres_session.scalars(select(GuestVisit)).all()) == 2


@pytest.mark.integration
def test_daily_counts_use_the_display_time_zone(postgres_session) -> None:
    # 20:30 UTC on 19 Oct is already 20 Oct in Dhaka (UTC+6).
    now = datetime(2026, 10, 19, 20, 30, tzinfo=UTC)
    postgres_session.add_all(
        [
            GuestVisit(visited_at=now),
            GuestVisit(visited_at=now - timedelta(minutes=10)),  # 20:20 UTC, still 20 Oct Dhaka
            GuestVisit(visited_at=datetime(2026, 10, 19, 17, 0, tzinfo=UTC)),  # 23:00 on 19 Oct Dhaka
            GuestVisit(visited_at=now - timedelta(days=40)),  # outside the window
        ]
    )
    postgres_session.commit()

    total, today, daily = guest_visit_stats(postgres_session, days=3, now=now)
    assert total == 4
    assert today == 2
    assert daily == [(date(2026, 10, 18), 0), (date(2026, 10, 19), 1), (date(2026, 10, 20), 2)]


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
    first = client.post("/api/v1/guest-visits", json={})
    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    second = client.post("/api/v1/guest-visits", json={}).json()
    assert second == {"visit_number": first.json()["visit_number"] + 1, "visits_today": 2}

    stats = client.get("/api/v1/guest-visits/stats?days=7")
    assert stats.status_code == 200
    assert stats.headers["cache-control"].startswith("public")
    body = stats.json()
    assert (body["total_visits"], body["visits_today"], len(body["daily"])) == (2, 2, 7)
    assert body["daily"][-1]["visits"] == 2


@pytest.mark.integration
def test_guest_visits_are_rate_limited_per_network(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUEST_VISITS_PER_NETWORK_PER_HOUR", "2")
    get_settings.cache_clear()
    codes = [client.post("/api/v1/guest-visits", json={}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
