"""The Gmail API provider (EMAIL_PROVIDER=gmail), against a fake Google endpoint."""

import base64
import email
from collections.abc import Generator

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.notify import providers
from app.notify.providers import Email, GmailProvider, SendAmbiguous, SendFailed

EMAIL = Email(to="nila@example.com", subject="Hello", text="plain", html="<p>html</p>", idempotency_key="delivery-1")


@pytest.fixture(autouse=True)
def gmail_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("EMAIL_PROVIDER", "gmail")
    monkeypatch.setenv("GMAIL_CLIENT_ID", "client-id")
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GMAIL_REFRESH_TOKEN", "refresh-token")
    monkeypatch.setenv("EMAIL_FROM", "Abhijatri <owner@gmail.com>")
    get_settings.cache_clear()
    GmailProvider._token = None
    yield
    GmailProvider._token = None
    get_settings.cache_clear()


def fake(send_status: int = 200, token_status: int = 200, send_error: Exception | None = None) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(token_status, json={"access_token": "access-1", "expires_in": 3599})
        if send_error is not None:
            raise send_error
        return httpx.Response(send_status, json={"id": "gmail-msg-1"})

    return httpx.MockTransport(handler), seen


def test_it_refreshes_the_token_once_and_sends_a_mime_message() -> None:
    transport, seen = fake()
    provider = GmailProvider(transport=transport)
    assert provider.send(EMAIL) == "gmail-msg-1"
    assert provider.send(EMAIL) == "gmail-msg-1"
    hosts = [r.url.host for r in seen]
    assert hosts.count("oauth2.googleapis.com") == 1, "the access token is reused"
    send = seen[-1]
    assert send.headers["Authorization"] == "Bearer access-1"
    raw = base64.urlsafe_b64decode(httpx.Response(200, content=send.content).json()["raw"])
    message = email.message_from_bytes(raw)
    assert message["To"] == "nila@example.com" and message["From"] == "Abhijatri <owner@gmail.com>"
    assert message["Date"] and message["Reply-To"] is None, "Reply-To equal to From only adds noise"
    assert message["Message-ID"] is None, "Gmail assigns its own; a made-up @gmail.com id looks forged"
    assert not [key for key in message if key.lower().startswith("x-")], "no custom headers"
    assert {part.get_content_type() for part in message.walk()} >= {"text/plain", "text/html"}
    assert b"refresh-token" not in send.content


def test_failures_are_classified() -> None:
    with pytest.raises(SendFailed) as caught:
        GmailProvider(transport=fake(send_status=400)[0]).send(EMAIL)
    assert caught.value.permanent and caught.value.code == "http_400"
    GmailProvider._token = None
    with pytest.raises(SendFailed) as caught:
        GmailProvider(transport=fake(send_status=503)[0]).send(EMAIL)
    assert not caught.value.permanent
    GmailProvider._token = None
    with pytest.raises(SendFailed) as caught:
        GmailProvider(transport=fake(token_status=400)[0]).send(EMAIL)
    assert caught.value.code == "gmail_token" and not caught.value.permanent, "fix the token, then retries work"
    GmailProvider._token = None
    with pytest.raises(SendAmbiguous):
        GmailProvider(transport=fake(send_error=httpx.ReadTimeout("slow"))[0]).send(EMAIL)


def test_the_provider_is_selected_and_production_needs_all_three_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    wrapped = providers.get_provider()
    assert isinstance(wrapped, providers.LinkGuard) and isinstance(wrapped._inner, GmailProvider)  # noqa: SLF001
    monkeypatch.delenv("GMAIL_REFRESH_TOKEN")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        Settings(app_env="production", _env_file=None)  # type: ignore[call-arg]


def test_real_providers_refuse_localhost_and_plain_http_links() -> None:
    """Such links in a real email are a strong spam signal and hurt the shared sender's reputation."""
    sent: list[Email] = []

    class Inner:
        name = "inner"

        def send(self, message: Email) -> str:
            sent.append(message)
            return "ok"

    guard = providers.LinkGuard(Inner())  # type: ignore[arg-type]
    for link in ("http://localhost:5173/verify-email?token_hash=x", "http://abhijatri.vercel.app/login", "https://127.0.0.1/x"):
        with pytest.raises(SendFailed) as caught:
            guard.send(Email(to="a@example.com", subject="s", text=f"open {link}", html="<p>x</p>", idempotency_key="k"))
        assert caught.value.permanent and caught.value.code == "unsafe_link"
    assert guard.send(Email(to="a@example.com", subject="s", text="https://abhijatri.vercel.app/login", html="<a href=\"https://abhijatri.vercel.app/login\">x</a>", idempotency_key="k")) == "ok"
    assert len(sent) == 1
