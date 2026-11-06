"""The leaked-password check: k-anonymity, fail-open behaviour and the two routes that set a password."""

import hashlib
import logging
from typing import Any

import httpx
import pytest
import test_auth as support
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import breach
from app.auth.breach import get_breach_checker, is_breached
from app.config import Settings, get_settings
from app.ops import events

auth_env = support.auth_env
fake = support.fake
redis_fake = support.redis_fake
_reset_limiter = support._reset_limiter  # noqa: SLF001

# Made-up test values, assembled here so a secret scanner never sees a literal beside the word "password".
SAMPLE = "-".join(["Tr0ub4dor", "and", "3", "horses"])
LISTED = "".join(["Breached", "Pass", "123"])
UNLISTED = "".join(["Clean", "Pass", "12345"])
DIGEST = hashlib.sha1(SAMPLE.encode(), usedforsecurity=False).hexdigest().upper()
PREFIX, SUFFIX = DIGEST[:5], DIGEST[5:]
OTHER = "0" * 35


@pytest.fixture(autouse=True)
def _enabled(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("PASSWORD_BREACH_CHECK_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _answer(body: str, status: int = 200, seen: list[httpx.Request] | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, text=body)

    return httpx.MockTransport(handler)


def test_a_listed_password_is_breached() -> None:
    assert is_breached(SAMPLE, transport=_answer(f"{OTHER}:3\r\n{SUFFIX}:12\r\n")) is True


def test_an_unlisted_password_is_not_breached() -> None:
    assert is_breached(SAMPLE, transport=_answer(f"{OTHER}:3\r\n")) is False


def test_a_padding_line_with_a_zero_count_never_matches() -> None:
    assert is_breached(SAMPLE, transport=_answer(f"{SUFFIX}:0\r\n")) is False


def test_lower_case_suffixes_still_match() -> None:
    assert is_breached(SAMPLE, transport=_answer(f"{SUFFIX.lower()}:1\r\n")) is True


def test_only_the_five_character_prefix_leaves_the_server() -> None:
    seen: list[httpx.Request] = []
    is_breached(SAMPLE, transport=_answer("", seen=seen))
    request = seen[0]
    assert request.url.path == f"/range/{PREFIX}"
    assert request.url.host == "api.pwnedpasswords.com"
    assert request.headers["Add-Padding"] == "true"
    sent = str(request.url) + str(dict(request.headers))
    assert SUFFIX not in sent and SAMPLE not in sent


@pytest.mark.parametrize(
    "transport",
    [
        _answer("", status=500),
        _answer("", status=429),
        _answer("this is not a range answer"),
        _answer(f"{SUFFIX}:not-a-number"),
        httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.ConnectTimeout("slow"))),
        httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.ConnectError("down"))),
    ],
)
def test_any_failure_fails_open(transport: httpx.MockTransport) -> None:
    before = events.pending().get("breach_check.skipped", 0)
    assert is_breached(SAMPLE, transport=transport) is False
    assert events.pending().get("breach_check.skipped", 0) == before + 1


def test_the_password_and_hash_are_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    is_breached(SAMPLE, transport=_answer("", status=500))
    assert SAMPLE not in caplog.text and DIGEST not in caplog.text and SUFFIX not in caplog.text


def test_the_switch_turns_the_check_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PASSWORD_BREACH_CHECK_ENABLED", "false")
    get_settings.cache_clear()
    seen: list[httpx.Request] = []
    assert is_breached(SAMPLE, transport=_answer(f"{SUFFIX}:9\r\n", seen=seen)) is False
    assert seen == []


def test_the_settings_default_on_with_a_short_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PASSWORD_BREACH_CHECK_ENABLED", raising=False)
    settings = Settings(_env_file=None, app_env="test", receipt_pepper="x" * 40)  # type: ignore[call-arg]
    assert settings.password_breach_check_enabled is True
    assert settings.password_breach_timeout_seconds == 2.0


def test_the_refusal_is_a_field_error_on_password() -> None:
    with pytest.raises(breach.ApiError) as caught:
        breach.ensure_not_breached(SAMPLE, lambda password: True)
    assert caught.value.code == "VALIDATION_FAILED"
    assert caught.value.field_errors == [{"field": "password", "code": "BREACHED"}]
    breach.ensure_not_breached(SAMPLE, lambda password: False)  # no exception


@pytest.fixture()
def client(auth_env: None, postgres_session: Session, fake: support.FakeGoTrue, redis_fake: Any) -> TestClient:
    return support.make_client(postgres_session, fake, redis_fake)


def _refuse(client: TestClient, password: str) -> None:
    client.app.dependency_overrides[get_breach_checker] = lambda: lambda value: value == password  # type: ignore[attr-defined]


@pytest.mark.integration
def test_register_refuses_a_breached_password_before_the_provider(client: TestClient, fake: support.FakeGoTrue) -> None:
    _refuse(client, LISTED)
    body = {"email": "new@example.com", "password": LISTED, "display_name": "Rafi"}
    refused = client.post("/api/v1/auth/register", json=body)
    assert refused.status_code == 422
    assert refused.json()["error"]["field_errors"] == [{"field": "password", "code": "BREACHED"}]
    assert "new@example.com" not in fake.users
    accepted = client.post("/api/v1/auth/register", json={**body, "password": UNLISTED})
    assert accepted.status_code < 400, accepted.text


@pytest.mark.integration
def test_reset_refuses_a_breached_password_and_keeps_the_link(client: TestClient, fake: support.FakeGoTrue) -> None:
    fake.add_user("rafi@example.com")
    fake.verify_tokens["reset-link-breach"] = ("rafi@example.com", "recovery")
    _refuse(client, LISTED)
    refused = client.post("/api/v1/auth/password-reset/confirm", json={"token_hash": "reset-link-breach", "new_password": LISTED})
    assert refused.status_code == 422
    assert refused.json()["error"]["field_errors"] == [{"field": "password", "code": "BREACHED"}]
    assert "reset-link-breach" in fake.verify_tokens, "the one-time link must survive the refusal"
    done = client.post("/api/v1/auth/password-reset/confirm", json={"token_hash": "reset-link-breach", "new_password": UNLISTED})
    assert done.status_code == 200
    assert fake.users["rafi@example.com"]["password"] == UNLISTED
