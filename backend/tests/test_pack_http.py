"""HTTP behaviour of the R14 pack routes that needs no database."""

import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.limits import limiter
from app.main import create_app

DESTINATION = uuid.uuid4()
ROUTES = (
    f"/api/v1/destinations/{DESTINATION}/pack/manifest",
    f"/api/v1/destinations/{DESTINATION}/pack",
)


class EmptySession:
    """A session whose lookups find nothing, so every destination is unknown."""

    def scalar(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def get(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    limiter.reset()


def _client() -> TestClient:
    application = create_app()

    def override() -> Generator[Any, None, None]:
        yield EmptySession()

    application.dependency_overrides[get_session] = override
    return TestClient(application)


@pytest.mark.parametrize("path", ROUTES)
def test_unknown_destination_is_404_not_cacheable_and_bangla_by_default(path: str) -> None:
    response = _client().get(path)
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["message"] == "খুঁজে পাওয়া যায়নি।"
    assert "etag" not in response.headers


def test_error_message_follows_accept_language() -> None:
    response = _client().get(ROUTES[0], headers={"Accept-Language": "en"})
    assert response.json()["error"]["message"] == "Not found."


def test_freshness_of_unknown_ids_reports_not_found_in_request_order() -> None:
    first, second = uuid.uuid4(), uuid.uuid4()
    response = _client().get("/api/v1/packs/freshness", params=[("destination_id", str(first)), ("destination_id", str(second))])
    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("public, max-age=")
    assert response.headers["etag"].startswith('W/"')
    assert response.json() == {
        "items": [
            {"destination_id": str(first), "status": "NOT_FOUND", "pack_version": None, "content_version": None,
             "sha256": None, "size_bytes": None, "generated_at": None, "expires_at": None, "pack_url": None},
            {"destination_id": str(second), "status": "NOT_FOUND", "pack_version": None, "content_version": None,
             "sha256": None, "size_bytes": None, "generated_at": None, "expires_at": None, "pack_url": None},
        ]
    }  # fmt: skip


@pytest.mark.parametrize(
    ("path", "params", "field"),
    [
        ("/api/v1/destinations/not-a-uuid/pack/manifest", [], "destination_id"),
        ("/api/v1/destinations/not-a-uuid/pack", [], "destination_id"),
        (ROUTES[1], [("version", "0")], "version"),
        (ROUTES[1], [("version", "-3")], "version"),
        (ROUTES[1], [("version", "abc")], "version"),
        (ROUTES[1], [("version", "2147483648")], "version"),
        ("/api/v1/packs/freshness", [], "destination_id"),
        ("/api/v1/packs/freshness", [("destination_id", "nope")], "destination_id.0"),
        ("/api/v1/packs/freshness", [("destination_id", str(uuid.uuid4()))] * 2, "destination_id"),
        ("/api/v1/packs/freshness", [("destination_id", str(uuid.uuid4())) for _ in range(21)], "destination_id"),
    ],
)
def test_bad_input_is_422_without_echoing_values(path: str, params: list[tuple[str, str]], field: str) -> None:
    response = _client().get(path, params=params)
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    body = response.json()["error"]
    assert body["code"] == "VALIDATION_FAILED"
    assert field in {error["field"] for error in body["field_errors"]}
    assert "not-a-uuid" not in response.text and "nope" not in response.text


def test_twenty_ids_are_accepted() -> None:
    params = [("destination_id", str(uuid.uuid4())) for _ in range(20)]
    assert _client().get("/api/v1/packs/freshness", params=params).status_code == 200


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("path", [*ROUTES, "/api/v1/packs/freshness"])
def test_pack_routes_are_read_only(method: str, path: str) -> None:
    response = _client().request(method, path)
    assert response.status_code == 405
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "path",
    [f"{ROUTES[0]}/extra", f"{ROUTES[1]}/1", f"/api/v1/destinations/{DESTINATION}/pack/manifest.json", "/api/v1/packs"],
)
def test_unknown_pack_paths_are_404(path: str) -> None:
    response = _client().get(path)
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_pack_routes_carry_the_security_headers() -> None:
    response = _client().get(ROUTES[0])
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" in response.headers
    assert response.headers["x-request-id"] == response.json()["error"]["request_id"]
    assert "set-cookie" not in response.headers
