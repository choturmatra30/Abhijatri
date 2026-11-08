"""``Idempotency-Key`` replay for retryable public and member writes (R16, API.md section 3, PF 12.4).

A client that lost a response retries with the same ``Idempotency-Key`` and gets the stored
response instead of a second effect. The flow in a route is:

1. ``key = parse_key(header)``: ``None`` when the header is absent (the write simply runs).
2. ``outcome = begin(session, key=..., scope=..., endpoint=..., request=...)``:
   - ``Replay``: a live row with the same request fingerprint exists. Return it with
     ``replay_response`` and do nothing else: no counters, no Turnstile, no write.
   - ``Claim``: this request reserved the key. The reservation row is inserted in the business
     transaction, so a concurrent twin waits on the primary key until this one commits (and then
     replays) or rolls back (and then runs itself).
   - Same key with a different fingerprint: ``409 IDEMPOTENCY_KEY_REUSED``.
3. Run the write, then ``finish(session, claim, status_code, body)`` before ``session.commit()``.

Only successful (2xx) responses are stored. Any error rolls the reservation back with the rest of
the transaction, so a retry after a failure runs again, exactly like the staff decisions in
``app/admin/idempotency.py``. Idempotency only replays recent responses; permanent duplicate
prevention for reviews stays the ``client_draft_id`` uniqueness (RV 4.1).

Privacy: the raw key is stored only as SHA-256, the caller only as a keyed HMAC digest, and the
request only as a fingerprint. Stored bodies are the public-safe success bodies (ids, status,
version), never a receipt or scope secret.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import delete, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import crypto
from app.config import get_settings
from app.errors import ApiError
from app.models import RequestIdempotency, utcnow

HEADER = "Idempotency-Key"
REPLAYED_HEADER = "Idempotent-Replayed"

KeyHeader = Annotated[
    str | None,
    Header(
        alias=HEADER,
        description="Optional UUID. A retry with the same key and body returns the stored response (API.md 3).",
    ),
]

# Request fields that legitimately differ between a request and its retry. A Turnstile token is
# single use, so a client that solved a fresh challenge must still get the replay.
VOLATILE_FIELDS = frozenset({"turnstile_token"})
PURGE_BATCH = 5000  # rows per retention statement

_MEMBER_LABEL = "abhijatri:idempotency-member:v1"
_GUEST_LABEL = crypto.GUEST_SCOPE_LABEL + ":idempotency"
_RECEIPT_LABEL = crypto.RECEIPT_LABEL + ":idempotency"


class Endpoint:
    """Stable operation names stored in ``request_idempotency.endpoint``. Never rename one."""

    GUEST_REVIEW_CREATE = "reviews.guest.create"
    MEMBER_REVIEW_CREATE = "reviews.member.create"
    REVIEW_WITHDRAW = "reviews.withdraw"
    REVIEW_EDIT_PENDING = "reviews.edit_pending"
    GUEST_APPEAL_CREATE = "review_receipts.appeal.create"
    VERIFICATION_SUBMIT = "verifications.submit"
    VERIFICATION_RESPOND = "verifications.respond"
    VERIFICATION_WITHDRAW = "verifications.withdraw"
    TOUR_CREATE = "tours.create"
    TOUR_REQUEST = "tours.request"
    TOUR_DECIDE = "tours.request.decide"
    TOUR_INVITE = "tours.invite"
    TOUR_INVITATION_ANSWER = "tours.invitation.answer"
    TOUR_EXPENSE = "tours.expense"
    TOUR_SOS = "tours.sos"


@dataclass(frozen=True)
class Claim:
    scope: bytes
    endpoint: str
    key_digest: str


@dataclass(frozen=True)
class Replay:
    status_code: int
    body: dict[str, Any]


def fingerprint(payload: Mapping[str, Any]) -> str:
    """SHA-256 of canonical JSON: sorted keys, no whitespace, non-JSON values as strings."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_key(value: str | None) -> str | None:
    """The header value as a canonical lower-case UUID, ``None`` when absent, 422 when malformed."""
    if value is None:
        return None
    try:
        parsed = uuid.UUID(value.strip())
    except ValueError:
        parsed = None
    if parsed is None or str(parsed) != value.strip().lower():
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": HEADER, "code": "INVALID_VALUE"}])
    return str(parsed)


def member_scope(user_id: uuid.UUID) -> bytes:
    return crypto.digest(_MEMBER_LABEL, crypto.current_key_id(), str(user_id))


def guest_scope(guest_scope_secret: str) -> bytes:
    return crypto.digest(_GUEST_LABEL, crypto.current_key_id(), guest_scope_secret)


def receipt_scope(receipt_secret: str) -> bytes:
    return crypto.digest(_RECEIPT_LABEL, crypto.current_key_id(), receipt_secret)


def request_fingerprint(*, method: str, path: Mapping[str, Any], body: BaseModel | None) -> str:
    """Fingerprint of what the caller asked for: method, path parameters and body minus volatile fields."""
    payload = body.model_dump(mode="json", exclude=set(VOLATILE_FIELDS)) if body is not None else None
    return fingerprint({"method": method, "path": dict(path), "body": payload})


def _key_digest(key: str) -> str:
    return hashlib.sha256(key.encode("ascii")).hexdigest()


def _is_lock_timeout(error: OperationalError) -> bool:
    return getattr(error.orig, "sqlstate", None) == "55P03"  # lock_not_available


def begin(
    session: Session,
    *,
    key: str | None,
    scope: bytes,
    endpoint: str,
    request_fingerprint: str,
) -> Claim | Replay | None:
    """Replay a stored response, reserve the key for this request, or ``None`` without a key."""
    if key is None:
        return None
    key_digest = _key_digest(key)
    identity = (
        RequestIdempotency.scope_digest == scope,
        RequestIdempotency.endpoint == endpoint,
        RequestIdempotency.key_digest == key_digest,
    )
    now = utcnow()
    ttl = timedelta(hours=get_settings().idempotency_ttl_hours)
    try:
        # An expired row no longer protects anything: clear it so the key can be used again.
        session.execute(delete(RequestIdempotency).where(*identity, RequestIdempotency.expires_at <= now))
        reserved = session.execute(
            insert(RequestIdempotency)
            .values(
                scope_digest=scope,
                endpoint=endpoint,
                key_digest=key_digest,
                fingerprint=request_fingerprint,
                status_code=200,  # placeholder; finish() writes the real result in this transaction
                response={},
                created_at=now,
                expires_at=now + ttl,
            )
            .on_conflict_do_nothing()
            .returning(RequestIdempotency.key_digest)
        ).first()
    except OperationalError as error:
        if _is_lock_timeout(error):  # a twin with this key is still running
            raise ApiError("IDEMPOTENCY_REQUEST_IN_PROGRESS", headers={"Retry-After": "1"}) from error
        raise
    if reserved is not None:
        return Claim(scope=scope, endpoint=endpoint, key_digest=key_digest)
    stored = session.execute(
        select(RequestIdempotency.fingerprint, RequestIdempotency.status_code, RequestIdempotency.response).where(
            *identity
        )
    ).first()
    if stored is None:  # removed between our insert and select (expiry purge): ask for a retry
        raise ApiError("IDEMPOTENCY_REQUEST_IN_PROGRESS", headers={"Retry-After": "1"})
    if stored.fingerprint != request_fingerprint:
        raise ApiError("IDEMPOTENCY_KEY_REUSED")
    return Replay(status_code=stored.status_code, body=dict(stored.response))


def finish(session: Session, claim: Claim | None, status_code: int, body: BaseModel) -> None:
    """Store the success response of a claimed request. Call before ``session.commit()``."""
    if claim is None:
        return
    if not 200 <= status_code <= 299:
        raise ValueError("only successful responses are stored")
    row = session.get(RequestIdempotency, (claim.scope, claim.endpoint, claim.key_digest))
    if row is None:  # pragma: no cover - the reservation is in this transaction
        raise RuntimeError("idempotency reservation vanished inside its own transaction")
    row.status_code = status_code
    row.response = body.model_dump(mode="json")


def replay_response(replay: Replay) -> JSONResponse:
    return JSONResponse(
        status_code=replay.status_code,
        content=replay.body,
        headers={REPLAYED_HEADER: "true", "Cache-Control": "no-store"},
    )


def purge_expired(session: Session, *, now: datetime | None = None, batch: int = PURGE_BATCH) -> int:
    """Delete up to ``batch`` expired rows in one statement; the caller commits. Returns the count."""
    moment = now or utcnow()
    columns = (RequestIdempotency.scope_digest, RequestIdempotency.endpoint, RequestIdempotency.key_digest)
    victims = select(*columns).where(RequestIdempotency.expires_at <= moment).limit(batch)
    result = session.execute(delete(RequestIdempotency).where(tuple_(*columns).in_(victims)))
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def finish_json(session: Session, claim: Claim | None, status_code: int, body: dict[str, Any]) -> None:
    """``finish`` for routes that answer with a plain JSON object (verification, tours)."""
    if claim is None:
        return
    if not 200 <= status_code <= 299:
        raise ValueError("only successful responses are stored")
    row = session.get(RequestIdempotency, (claim.scope, claim.endpoint, claim.key_digest))
    if row is None:  # pragma: no cover - the reservation is in this transaction
        raise RuntimeError("idempotency reservation vanished inside its own transaction")
    row.status_code = status_code
    row.response = json.loads(json.dumps(body, default=str))


def fingerprint_json(*, method: str, path: Mapping[str, Any], body: Mapping[str, Any] | None) -> str:
    payload = {k: v for k, v in (body or {}).items() if k not in VOLATILE_FIELDS}
    return fingerprint({"method": method, "path": {k: str(v) for k, v in path.items()}, "body": payload})
