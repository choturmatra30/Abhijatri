"""Envelope encryption for sensitive fields (sign-up form 9.3, architecture 10.4).

Every sealed value gets its own random 256-bit data key. The data key encrypts the value with
AES-256-GCM, and is itself encrypted ("wrapped") by a master key that never enters the database.
The sealed blob therefore holds only ciphertext:

    b"F1" | key_id length (1 byte) | key_id | wrapped data key (60 bytes) | nonce (12) | ciphertext+tag

A database dump alone reveals nothing. Destroying a value (crypto-shredding) is deleting its blob:
its data key exists nowhere else. ``aad`` (associated data) binds a blob to its row and field, so a
blob copied into another row or column fails to open.

Master keys come from ``FIELD_ENCRYPTION_KEYS`` (JSON ``{"k1": "<base64 32 bytes>"}``), with
``FIELD_ENCRYPTION_KEY_CURRENT`` naming the key for new values; older keys stay to open old values.
Outside production a key is derived from ``RECEIPT_PEPPER`` so development works without setup.
In production, a missing key makes every caller fail closed with ``SERVICE_UNAVAILABLE``.
"""

import base64
import hashlib
import json
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings
from app.errors import ApiError

MAGIC = b"F1"
_WRAPPED_LEN = 12 + 32 + 16  # nonce + data key + tag


class SealError(Exception):
    """A blob that cannot be opened: wrong row, damaged, or its key was retired."""


@lru_cache
def _keyring() -> tuple[str, dict[str, bytes]]:
    settings = get_settings()
    if settings.field_encryption_keys:
        raw = json.loads(settings.field_encryption_keys)
        ring = {str(k): base64.b64decode(v) for k, v in raw.items()}
        if any(len(key) != 32 for key in ring.values()):
            raise ValueError("every FIELD_ENCRYPTION_KEYS key must be 32 bytes, base64 encoded")
        if settings.field_encryption_key_current not in ring:
            raise ValueError("FIELD_ENCRYPTION_KEY_CURRENT must name a key in FIELD_ENCRYPTION_KEYS")
        return settings.field_encryption_key_current, ring
    if settings.is_production:
        return "", {}
    derived = hashlib.sha256(b"abhijatri:field-encryption:dev:" + settings.receipt_pepper.encode()).digest()
    return "dev", {"dev": derived}


def configured() -> bool:
    return bool(_keyring()[1])


def require_configured() -> None:
    if not configured():
        raise ApiError("SERVICE_UNAVAILABLE")


def seal(value: str | bytes, *, aad: str) -> bytes:
    key_id, ring = _keyring()
    if not ring:
        raise ApiError("SERVICE_UNAVAILABLE")
    plaintext = value.encode("utf-8") if isinstance(value, str) else value
    data_key = AESGCM.generate_key(bit_length=256)
    wrap_nonce = os.urandom(12)
    wrapped = wrap_nonce + AESGCM(ring[key_id]).encrypt(wrap_nonce, data_key, key_id.encode())
    nonce = os.urandom(12)
    ciphertext = AESGCM(data_key).encrypt(nonce, plaintext, aad.encode())
    kid = key_id.encode()
    return MAGIC + bytes([len(kid)]) + kid + wrapped + nonce + ciphertext


def open_bytes(blob: bytes, *, aad: str) -> bytes:
    if not blob.startswith(MAGIC):
        raise SealError("not a sealed value")
    _, ring = _keyring()
    try:
        kid_len = blob[2]
        key_id = blob[3 : 3 + kid_len].decode()
        offset = 3 + kid_len
        wrapped = blob[offset : offset + _WRAPPED_LEN]
        nonce = blob[offset + _WRAPPED_LEN : offset + _WRAPPED_LEN + 12]
        ciphertext = blob[offset + _WRAPPED_LEN + 12 :]
        master = ring[key_id]
        data_key = AESGCM(master).decrypt(wrapped[:12], wrapped[12:], key_id.encode())
        return AESGCM(data_key).decrypt(nonce, ciphertext, aad.encode())
    except (KeyError, IndexError, ValueError, UnicodeDecodeError) as error:
        raise SealError("cannot open") from error
    except Exception as error:  # cryptography.exceptions.InvalidTag
        raise SealError("cannot open") from error


def open_text(blob: bytes | None, *, aad: str) -> str | None:
    if blob is None:
        return None
    return open_bytes(blob, aad=aad).decode("utf-8")


def reset_for_tests() -> None:
    _keyring.cache_clear()
