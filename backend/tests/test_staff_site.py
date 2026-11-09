"""The staff dashboard served at /staff, and the same-host exemption in the Origin check."""

from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.auth import csrf
from app.errors import install_error_handlers
from app.staff_site import mount_staff_site


@pytest.fixture
def site(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>staff</title>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    return tmp_path


def test_staff_site_is_served_with_its_own_headers(site: Path) -> None:
    app = FastAPI()
    assert mount_staff_site(app, site) is True
    client = TestClient(app)
    page = client.get("/staff/")
    assert page.status_code == 200 and "staff" in page.text
    assert page.headers["content-security-policy"].startswith("default-src 'none'; script-src 'self'")
    assert "noindex" in page.headers["x-robots-tag"]
    assert client.get("/staff/assets/app.js").status_code == 200
    assert client.get("/staff/nothing").status_code == 404


def test_nothing_is_mounted_without_a_bundle(tmp_path: Path) -> None:
    app = FastAPI()
    assert mount_staff_site(app, tmp_path) is False
    assert TestClient(app).get("/staff/").status_code == 404


def _origin_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.post("/write")
    def write(request: Request) -> dict[str, str]:
        csrf.check_origin(request)
        return {"ok": "yes"}

    return app


def test_origin_of_the_api_own_host_is_accepted_and_foreign_is_refused() -> None:
    client = TestClient(_origin_app(), base_url="https://api.example.test")
    assert client.post("/write", headers={"Origin": "https://api.example.test"}).status_code == 200
    assert client.post("/write", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/write").status_code == 200  # no Origin header: the token check is the main layer
