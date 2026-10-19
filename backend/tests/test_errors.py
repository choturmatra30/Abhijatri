"""The standard error body (Docs/api/API.md section 2) on every failure path."""

import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.errors import CATALOGUE, ApiError, preferred_language
from app.limits import limiter
from app.main import create_app


class NoRowsSession:
    def scalar(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def get(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def rollback(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    limiter.reset()


def _client() -> TestClient:
    application = create_app()

    def override() -> Generator[Any, None, None]:
        yield NoRowsSession()

    application.dependency_overrides[get_session] = override
    return TestClient(application)


def _assert_standard(response: Any, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}
    error = body["error"]
    assert set(error) == {"code", "message", "request_id", "field_errors"}
    assert error["code"] == code
    assert error["request_id"] == response.headers["x-request-id"]
    uuid.UUID(error["request_id"])
    assert isinstance(error["field_errors"], list)
    return error  # type: ignore[no-any-return]


def test_every_catalogue_entry_has_both_languages_and_a_valid_status() -> None:
    for code, (status, bn, en) in CATALOGUE.items():
        assert 400 <= status <= 504, code
        assert bn.strip() and en.strip() and bn != en, code


def test_contract_codes_are_all_present() -> None:
    required = {
        "AUTH_REQUIRED", "FORBIDDEN", "SELF_MODERATION_FORBIDDEN", "CSRF_INVALID", "CHALLENGE_FAILED",
        "NOT_FOUND", "RECEIPT_NOT_FOUND", "REVIEW_VERSION_CONFLICT", "INVALID_TRANSITION",
        "DRAFT_ALREADY_SUBMITTED", "RESERVED_DISPLAY_NAME", "IDEMPOTENCY_KEY_REUSED",
        "DUPLICATE_OPEN_REPORT", "APPEAL_WINDOW_CLOSED", "PAYLOAD_TOO_LARGE", "VALIDATION_FAILED",
        "INVALID_CURSOR", "INVALID_RECEIPT_FORMAT", "RATE_LIMITED", "GUEST_WRITES_PAUSED",
        "INTERNAL_ERROR", "STAFF_AUTH_NOT_CONFIGURED", "SERVICE_UNAVAILABLE", "REQUEST_TIMEOUT",
    }  # fmt: skip
    assert required <= set(CATALOGUE)
    assert {c: CATALOGUE[c][0] for c in required} == {
        "AUTH_REQUIRED": 401, "FORBIDDEN": 403, "SELF_MODERATION_FORBIDDEN": 403, "CSRF_INVALID": 403,
        "CHALLENGE_FAILED": 403, "NOT_FOUND": 404, "RECEIPT_NOT_FOUND": 404, "REVIEW_VERSION_CONFLICT": 409,
        "INVALID_TRANSITION": 409, "DRAFT_ALREADY_SUBMITTED": 409, "RESERVED_DISPLAY_NAME": 409,
        "IDEMPOTENCY_KEY_REUSED": 409, "DUPLICATE_OPEN_REPORT": 409, "APPEAL_WINDOW_CLOSED": 409,
        "PAYLOAD_TOO_LARGE": 413, "VALIDATION_FAILED": 422, "INVALID_CURSOR": 422,
        "INVALID_RECEIPT_FORMAT": 422, "RATE_LIMITED": 429, "GUEST_WRITES_PAUSED": 503,
        "INTERNAL_ERROR": 500, "STAFF_AUTH_NOT_CONFIGURED": 501, "SERVICE_UNAVAILABLE": 503,
        "REQUEST_TIMEOUT": 504,
    }  # fmt: skip


def test_unknown_error_code_cannot_be_raised() -> None:
    with pytest.raises(ValueError):
        ApiError("MADE_UP")


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "bn"),
        ("", "bn"),
        ("en", "en"),
        ("en-US,en;q=0.9", "en"),
        ("bn-BD,bn;q=0.9,en;q=0.8", "bn"),
        ("en;q=0.9, bn;q=0.4", "en"),
        ("fr-FR", "bn"),
        ("en;q=0", "bn"),
        ("en;q=abc", "bn"),
    ],
)
def test_accept_language_negotiation(header: str | None, expected: str) -> None:
    assert preferred_language(header) == expected


def test_message_follows_accept_language_and_defaults_to_bangla() -> None:
    client = _client()
    url = f"/api/v1/destinations/{uuid.uuid4()}"
    default = _assert_standard(client.get(url), 404, "NOT_FOUND")
    english = _assert_standard(client.get(url, headers={"Accept-Language": "en"}), 404, "NOT_FOUND")
    assert default["message"] == CATALOGUE["NOT_FOUND"][1]
    assert english["message"] == CATALOGUE["NOT_FOUND"][2]


def test_unknown_route_and_wrong_method_use_the_standard_body() -> None:
    client = _client()
    _assert_standard(client.get("/api/v1/nothing-here"), 404, "NOT_FOUND")
    _assert_standard(client.delete("/api/v1/health"), 405, "METHOD_NOT_ALLOWED")


def test_validation_errors_list_field_codes_and_never_echo_values() -> None:
    secret = "S3CRET-" + "x" * 50
    response = _client().post(
        "/api/v1/reviews/guest",
        json={
            "destination_id": "not-a-uuid",
            "guest_scope_secret": secret,
            "overall_rating": 9,
            "title": "x",
        },
    )
    error = _assert_standard(response, 422, "VALIDATION_FAILED")
    fields = {item["field"]: item["code"] for item in error["field_errors"]}
    assert fields["destination_id"] == "INVALID_UUID"
    assert fields["overall_rating"] == "TOO_LARGE"
    assert fields["title"] == "TOO_SHORT"
    assert fields["body"] == "REQUIRED"
    assert secret not in response.text
    assert "not-a-uuid" not in response.text


def test_future_visit_month_has_a_specific_field_code() -> None:
    payload = {
        "destination_id": str(uuid.uuid4()),
        "client_draft_id": str(uuid.uuid4()),
        "guest_scope_secret": "s" * 43,
        "guest_display_name": "Sadia",
        "language": "BN",
        "traveller_type": "SOLO",
        "comfort_tier": "STANDARD",
        "visit_month": "2999-01-01",
        "title": "A fine trip",
        "body": "At least twenty characters of text.",
        "overall_rating": 4,
        "consent_version": "2026-10-01",
    }
    error = _assert_standard(_client().post("/api/v1/reviews/guest", json=payload), 422, "VALIDATION_FAILED")
    assert {"field": "visit_month", "code": "FUTURE_MONTH"} in error["field_errors"]


def test_malformed_json_body_is_a_validation_error() -> None:
    response = _client().post(
        "/api/v1/reviews/guest", content=b"{not json", headers={"content-type": "application/json"}
    )
    error = _assert_standard(response, 422, "VALIDATION_FAILED")
    assert error["field_errors"][0]["code"] == "INVALID_JSON"


def test_invalid_cursor_has_its_own_code() -> None:
    client = _client()
    _assert_standard(client.get("/api/v1/destinations", params={"after": "nope"}), 422, "INVALID_CURSOR")
    reviews = f"/api/v1/destinations/{uuid.uuid4()}/reviews"
    _assert_standard(client.get(reviews, params={"after": "nope"}), 422, "INVALID_CURSOR")


def test_oversized_body_uses_the_standard_body() -> None:
    response = _client().post(
        "/api/v1/reviews/guest", content=b"{}", headers={"content-length": "99999999"}
    )
    _assert_standard(response, 413, "PAYLOAD_TOO_LARGE")


def test_staff_routes_use_standard_codes() -> None:
    client = _client()
    _assert_standard(client.get("/api/v1/staff/moderation/reviews"), 501, "STAFF_AUTH_NOT_CONFIGURED")
