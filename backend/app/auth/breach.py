"""Refuse passwords known from public data breaches (Security.md, Supabase advisor "leaked password").

Supabase's own switch for this needs a paid plan, so the API checks the Have I Been Pwned range
service at sign-up and password reset, the only two routes that set a password.

k-anonymity: only the first five hex characters of the SHA-1 leave this server; the service answers
with every suffix in that range and the comparison happens here. ``Add-Padding`` makes every answer
the same size, and padded lines carry a count of zero, so they never match.

The check fails open. A timeout, an error or an unreadable answer counts ``breach_check.skipped`` and
lets the request continue: nobody is locked out because a third party is down, and the other
password rules still apply. The password and its hash are never logged.
"""

import hashlib
import logging
from collections.abc import Callable
from typing import Annotated

import httpx
from fastapi import Depends

from app.config import get_settings
from app.errors import ApiError
from app.ops import events

logger = logging.getLogger(__name__)

RANGE_URL = "https://api.pwnedpasswords.com/range/"
PREFIX_LENGTH = 5
SUFFIX_LENGTH = 35


def _sha1_hex(password: str) -> str:
    return hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()


def _listed(body: str, suffix: str) -> bool:
    """True when ``suffix`` appears with a real count. Malformed lines raise ValueError."""
    for line in body.splitlines():
        if not line.strip():
            continue
        candidate, _, count = line.strip().partition(":")
        if len(candidate) != SUFFIX_LENGTH:
            raise ValueError("unexpected range line")
        if candidate.upper() == suffix and int(count) > 0:
            return True
    return False


def is_breached(password: str, *, transport: httpx.BaseTransport | None = None) -> bool:
    """False when the password is not listed or the check could not run."""
    settings = get_settings()
    if not settings.password_breach_check_enabled:
        return False
    digest = _sha1_hex(password)
    prefix, suffix = digest[:PREFIX_LENGTH], digest[PREFIX_LENGTH:]
    try:
        with httpx.Client(timeout=settings.password_breach_timeout_seconds, transport=transport) as client:
            response = client.get(f"{RANGE_URL}{prefix}", headers={"Add-Padding": "true"})
            response.raise_for_status()
            return _listed(response.text, suffix)
    except (httpx.HTTPError, ValueError) as error:
        logger.warning("password breach check skipped: %s", type(error).__name__)
        events.count("breach_check.skipped")
        return False


def get_breach_checker() -> Callable[[str], bool]:
    """Dependency so tests can substitute the check."""
    return is_breached


BreachCheckDep = Annotated[Callable[[str], bool], Depends(get_breach_checker)]


def ensure_not_breached(password: str, check: Callable[[str], bool]) -> None:
    if check(password):
        events.count("breach_check.refused")
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "password", "code": "BREACHED"}])
