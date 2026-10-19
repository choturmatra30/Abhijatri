"""HTTP behaviour of the public destination routes that needs no database."""

import uuid
from collections.abc import Generator
from typing import Any

from fastapi.testclient import TestClient

from app.db import get_session
from app.main import create_app

DESTINATION = uuid.uuid4()


class EmptySession:
    """A session whose queries find nothing, so every lookup is a 404."""

    def scalar(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def get(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _client() -> TestClient:
    application = create_app()

    def override() -> Generator[Any, None, None]:
        yield EmptySession()

    application.dependency_overrides[get_session] = override
    return TestClient(application)


def test_unknown_destination_is_404_and_not_cacheable() -> None:
    response = _client().get(f"/api/v1/destinations/{DESTINATION}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.headers["cache-control"] == "no-store"


def test_malformed_destination_id_is_422() -> None:
    assert _client().get("/api/v1/destinations/not-a-uuid").status_code == 422


def test_invalid_list_parameters_are_422() -> None:
    client = _client()
    assert client.get("/api/v1/destinations", params={"limit": 0}).status_code == 422
    assert client.get("/api/v1/destinations", params={"limit": 51}).status_code == 422
    assert client.get("/api/v1/destinations", params={"after": "not-a-cursor"}).status_code == 422
    assert client.get("/api/v1/destinations", params={"after": "x" * 301}).status_code == 422


def test_advisories_and_contacts_have_no_routes_of_their_own() -> None:
    client = _client()
    assert client.get(f"/api/v1/destinations/{DESTINATION}/advisories").status_code == 404
    assert client.get(f"/api/v1/destinations/{DESTINATION}/contacts").status_code == 404


def test_destination_routes_are_read_only() -> None:
    client = _client()
    assert client.post("/api/v1/destinations", json={}).status_code == 405
    assert client.delete(f"/api/v1/destinations/{DESTINATION}").status_code == 405
