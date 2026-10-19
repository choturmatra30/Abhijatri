"""Server-side Turnstile validation against a mocked siteverify endpoint (PF 14.1)."""

import json
from collections.abc import Generator
from urllib.parse import parse_qs

import httpx
import pytest

from app.config import get_settings
from app.errors import ApiError
from app.turnstile import ACTION_GUEST_REVIEW, verify_with_cloudflare

HOSTNAME = "app.example.test"


@pytest.fixture()
def enabled(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")
    monkeypatch.setenv("TURNSTILE_SECRET", "0x4AAAAAAA-test-secret")
    monkeypatch.setenv("TURNSTILE_HOSTNAME", HOSTNAME)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class Siteverify:
    """A mock Cloudflare endpoint that records every request it receives."""

    def __init__(self, *responses: httpx.Response | Exception) -> None:
        self._responses = list(responses)
        self.forms: list[dict[str, list[str]]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.forms.append(parse_qs(request.content.decode()))
        outcome = self._responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


def _ok(**overrides: object) -> httpx.Response:
    body = {"success": True, "hostname": HOSTNAME, "action": ACTION_GUEST_REVIEW}
    body.update(overrides)
    return httpx.Response(200, json=body)


def _verify(siteverify: Siteverify, response: str | None = "token-1", address: str | None = "203.0.113.9") -> None:
    verify_with_cloudflare(
        response, action=ACTION_GUEST_REVIEW, remote_address=address, transport=siteverify.transport()
    )


def _error_code(excinfo: pytest.ExceptionInfo[ApiError]) -> str:
    return excinfo.value.code


def test_disabled_verifier_does_nothing_and_never_calls_cloudflare() -> None:
    siteverify = Siteverify()
    _verify(siteverify, response=None)
    assert siteverify.forms == []


@pytest.mark.usefixtures("enabled")
def test_valid_token_is_accepted_and_the_form_is_complete() -> None:
    siteverify = Siteverify(_ok())
    _verify(siteverify)
    (form,) = siteverify.forms
    assert form["secret"] == ["0x4AAAAAAA-test-secret"]
    assert form["response"] == ["token-1"]
    assert form["remoteip"] == ["203.0.113.9"]
    assert len(form["idempotency_key"][0]) == 36


@pytest.mark.usefixtures("enabled")
@pytest.mark.parametrize("token", [None, ""])
def test_missing_token_fails_without_calling_cloudflare(token: str | None) -> None:
    siteverify = Siteverify()
    with pytest.raises(ApiError) as excinfo:
        _verify(siteverify, response=token)
    assert _error_code(excinfo) == "CHALLENGE_FAILED"
    assert siteverify.forms == []


@pytest.mark.usefixtures("enabled")
@pytest.mark.parametrize(
    "response",
    [
        _ok(success=False),
        _ok(hostname="evil.example.test"),
        _ok(action="guest-report"),
        httpx.Response(200, json={"success": True}),
    ],
)
def test_success_hostname_and_action_must_all_match(response: httpx.Response) -> None:
    with pytest.raises(ApiError) as excinfo:
        _verify(Siteverify(response))
    assert _error_code(excinfo) == "CHALLENGE_FAILED"


@pytest.mark.usefixtures("enabled")
def test_network_retry_reuses_the_same_idempotency_key() -> None:
    siteverify = Siteverify(httpx.ConnectError("boom"), _ok())
    _verify(siteverify)
    first, second = siteverify.forms
    assert first["idempotency_key"] == second["idempotency_key"]


@pytest.mark.usefixtures("enabled")
def test_server_error_is_retried_once_then_succeeds() -> None:
    siteverify = Siteverify(httpx.Response(500), _ok())
    _verify(siteverify)
    assert len(siteverify.forms) == 2


@pytest.mark.usefixtures("enabled")
@pytest.mark.parametrize(
    "outcomes",
    [
        (httpx.ConnectError("a"), httpx.ConnectError("b")),
        (httpx.Response(502), httpx.Response(503)),
        (httpx.Response(200, content=b"<html>not json"), httpx.Response(200, content=b"<html>")),
        (httpx.Response(200, content=json.dumps([1]).encode()), httpx.Response(200, content=b"[2]")),
    ],
)
def test_unreachable_cloudflare_is_a_503_never_a_pass_and_never_a_challenge_failure(
    outcomes: tuple[httpx.Response | Exception, ...],
) -> None:
    siteverify = Siteverify(*outcomes)
    with pytest.raises(ApiError) as excinfo:
        _verify(siteverify)
    assert _error_code(excinfo) == "SERVICE_UNAVAILABLE"
    assert excinfo.value.headers["Retry-After"] == "5"
    assert len(siteverify.forms) == 2


@pytest.mark.usefixtures("enabled")
def test_remote_address_is_optional() -> None:
    siteverify = Siteverify(_ok())
    _verify(siteverify, address=None)
    assert "remoteip" not in siteverify.forms[0]
