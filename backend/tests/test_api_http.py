"""HTTP-level behaviour: guardrails, error fallbacks, rate limits and receipt rotation."""

import time
import uuid
from collections.abc import Callable, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api import require_staff
from app.config import get_settings
from app.db import get_session
from app.limits import limiter
from app.main import create_app
from app.models import User

DESTINATION = uuid.uuid4()


class FakeSession:
    """Stands in for a Session so error paths run without a database."""

    def __init__(self, failure: Callable[[], Any] | None = None) -> None:
        self._failure = failure

    def execute(self, *_args: Any, **_kwargs: Any) -> Any:
        if self._failure is not None:
            return self._failure()
        raise AssertionError("unexpected query")

    def scalar(self, *_args: Any, **_kwargs: Any) -> None:
        if self._failure is not None:
            self._failure()
        return None

    def rollback(self) -> None:
        return None


def _client(session: Any, *, raise_server_exceptions: bool = False) -> TestClient:
    application = create_app()

    def override() -> Generator[Any, None, None]:
        yield session

    application.dependency_overrides[get_session] = override
    return TestClient(application, raise_server_exceptions=raise_server_exceptions)


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    limiter.reset()


def test_responses_carry_request_id_and_security_headers() -> None:
    response = _client(FakeSession()).get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert len(response.headers["x-request-id"]) == 36


def test_oversized_body_is_rejected_before_parsing() -> None:
    limit = get_settings().max_request_body_bytes
    response = _client(FakeSession()).post(
        "/api/v1/reviews/guest", content=b"{}", headers={"content-length": str(limit + 1)}
    )
    assert response.status_code == 413


def test_staff_endpoints_refuse_the_test_header_by_default() -> None:
    response = _client(FakeSession()).get(
        "/api/v1/staff/moderation/reviews", headers={"X-Test-Staff-Id": str(uuid.uuid4())}
    )
    assert response.status_code == 501


def test_unknown_moderation_decision_is_a_422() -> None:
    application = create_app()
    application.dependency_overrides[require_staff] = lambda: User(email="m@x.test", display_name="M")
    application.dependency_overrides[get_session] = lambda: FakeSession()
    response = TestClient(application).post(
        f"/api/v1/staff/moderation/reviews/{uuid.uuid4()}/decisions",
        json={"expected_version": 1, "decision": "DELETE_EVERYTHING", "reason_code": "spam"},
    )
    assert response.status_code == 422


def test_invalid_cursor_and_limit_are_422() -> None:
    client = _client(FakeSession())
    base = f"/api/v1/destinations/{DESTINATION}/reviews"
    assert client.get(base, params={"after": "not-a-cursor"}).status_code == 422
    assert client.get(base, params={"limit": 51}).status_code == 422
    assert client.get(base, params={"after": "x" * 201}).status_code == 422


def test_database_outage_becomes_503_with_retry_after() -> None:
    def fail() -> Any:
        raise OperationalError("SELECT 1", {}, Exception("server closed the connection"))

    response = _client(FakeSession(fail)).get(f"/api/v1/destinations/{DESTINATION}/reviews")
    assert response.status_code == 503
    body = response.json()["error"]
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert body["request_id"] == response.headers["x-request-id"]
    assert body["field_errors"] == []
    assert response.headers["retry-after"] == "5"


def test_unexpected_error_is_a_generic_500_without_internals() -> None:
    def boom() -> Any:
        raise RuntimeError("secret internal detail")

    response = _client(FakeSession(boom)).get(f"/api/v1/destinations/{DESTINATION}/reviews")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in response.text


def test_slow_request_times_out_with_504(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "1")
    get_settings.cache_clear()
    try:
        client = _client(FakeSession(lambda: time.sleep(2)))
        response = client.get(f"/api/v1/destinations/{DESTINATION}/reviews")
    finally:
        get_settings.cache_clear()
    assert response.status_code == 504
