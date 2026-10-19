"""Test helper: a client-style receipt (32 random bytes, base64url, prefix abr1_)."""

import base64
import secrets


def new_receipt() -> str:
    return "abr1_" + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")
