"""The trusted client address is derived in one place and cannot be forged (PF 14.2)."""

from collections.abc import Generator

import pytest
from starlette.requests import Request

from app import client_address, crypto
from app.config import get_settings


def _request(headers: dict[str, str], peer: str | None = "10.0.0.1") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (peer, 4711) if peer else None,
    }
    return Request(scope)


@pytest.fixture()
def provider_header(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("CLIENT_ADDRESS_HEADER", "X-Forwarded-For")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.usefixtures("provider_header")
def test_right_most_provider_entry_is_used_not_the_client_supplied_left_most() -> None:
    request = _request({"X-Forwarded-For": "1.2.3.4, 5.6.7.8, 203.0.113.9"})
    assert str(client_address.trusted_client_address(request)) == "203.0.113.9"


@pytest.mark.usefixtures("provider_header")
def test_forged_forwarding_headers_cannot_replace_the_provider_address() -> None:
    forged = {
        "X-Forwarded-For": "203.0.113.9",
        "Forwarded": "for=6.6.6.6",
        "X-Real-IP": "7.7.7.7",
        "CF-Connecting-IP": "8.8.8.8",
        "True-Client-IP": "9.9.9.9",
    }
    assert str(client_address.trusted_client_address(_request(forged))) == "203.0.113.9"


@pytest.mark.usefixtures("provider_header")
def test_other_headers_are_ignored_when_the_provider_header_is_missing() -> None:
    request = _request({"X-Real-IP": "7.7.7.7", "CF-Connecting-IP": "8.8.8.8"}, peer="10.0.0.1")
    assert str(client_address.trusted_client_address(request)) == "10.0.0.1"


@pytest.mark.usefixtures("provider_header")
@pytest.mark.parametrize("value", ["not-an-ip", "999.1.1.1", "", " , "])
def test_malformed_provider_value_never_falls_back_to_client_input(value: str) -> None:
    request = _request({"X-Forwarded-For": value}, peer="10.0.0.1")
    assert str(client_address.trusted_client_address(request)) == "10.0.0.1"


@pytest.mark.usefixtures("provider_header")
def test_ports_and_ipv6_brackets_are_stripped() -> None:
    assert str(client_address.trusted_client_address(_request({"X-Forwarded-For": "203.0.113.9:5555"}))) == "203.0.113.9"
    assert str(client_address.trusted_client_address(_request({"X-Forwarded-For": "[2001:db8::1]"}))) == "2001:db8::1"


def test_without_a_configured_header_forwarding_headers_are_ignored() -> None:
    request = _request({"X-Forwarded-For": "1.2.3.4", "X-Real-IP": "5.6.7.8"}, peer="10.0.0.1")
    assert str(client_address.trusted_client_address(request)) == "10.0.0.1"


def test_position_selects_another_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLIENT_ADDRESS_HEADER", "X-Forwarded-For")
    monkeypatch.setenv("CLIENT_ADDRESS_POSITION", "-2")
    get_settings.cache_clear()
    try:
        request = _request({"X-Forwarded-For": "1.1.1.1, 2.2.2.2, 3.3.3.3"})
        assert str(client_address.trusted_client_address(request)) == "2.2.2.2"
        short = _request({"X-Forwarded-For": "3.3.3.3"}, peer="10.0.0.1")
        assert str(client_address.trusted_client_address(short)) == "10.0.0.1"
    finally:
        get_settings.cache_clear()


def test_missing_peer_is_unknown_not_a_crash() -> None:
    assert client_address.normalise(client_address.trusted_client_address(_request({}, peer=None))) == "unknown"


def test_ipv6_is_truncated_to_its_slash_64() -> None:
    same_a = _request({}, peer="2001:db8:1:2:aaaa:bbbb:cccc:dddd")
    same_b = _request({}, peer="2001:db8:1:2::1")
    other = _request({}, peer="2001:db8:1:3::1")
    a, b, c = (client_address.network_digest(r) for r in (same_a, same_b, other))
    assert a == b
    assert a != c
    assert client_address.normalise(client_address.trusted_client_address(same_a)) == "2001:db8:1:2::/64"


def test_ipv4_is_used_as_is() -> None:
    assert client_address.normalise(client_address.trusted_client_address(_request({}, peer="203.0.113.9"))) == "203.0.113.9"


def test_network_digest_is_a_keyed_digest_never_the_address() -> None:
    request = _request({}, peer="203.0.113.9")
    value = client_address.network_digest(request)
    assert len(value) == 32
    assert b"203.0.113.9" not in value
    assert value == crypto.digest(crypto.NETWORK_LABEL, crypto.current_key_id(), "203.0.113.9")
    assert value != crypto.digest(crypto.RECEIPT_LABEL, crypto.current_key_id(), "203.0.113.9")
