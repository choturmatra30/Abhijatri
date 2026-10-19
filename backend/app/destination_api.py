"""Public destination routes (R02): the list and the full bilingual profile.

These are the only routes that opt in to shared caching (Security 7.1): an exact route
allowlist with a short explicit TTL. Every other route keeps the global ``no-store``.
Advisories and contacts are part of the profile payload; they have no routes of their own.
"""

import hashlib
import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.destination_services import (
    DestinationNotFound,
    InvalidCursor,
    get_destination_profile,
    list_published_destinations,
)
from app.errors import ApiError
from app.schemas import DestinationList, DestinationProfile

router = APIRouter(prefix="/api/v1")


def _etag(payload: BaseModel) -> str:
    digest = hashlib.sha256(payload.model_dump_json().encode("utf-8")).hexdigest()[:32]
    return f'W/"{digest}"'


def _matches(header: str | None, etag: str) -> bool:
    if not header:
        return False
    candidates = {part.strip() for part in header.split(",")}
    return "*" in candidates or etag in candidates


def public_cache_headers(etag: str | None = None) -> dict[str, str]:
    headers = {"Cache-Control": f"public, max-age={get_settings().public_cache_max_age_seconds}"}
    if etag is not None:
        headers["ETag"] = etag
    return headers


def _public(request: Request, response: Response, payload: BaseModel) -> BaseModel | Response:
    """Attach the public cache headers and answer conditional requests with 304."""
    headers = public_cache_headers(_etag(payload))
    if _matches(request.headers.get("if-none-match"), headers["ETag"]):
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return payload


@router.get("/destinations", response_model=DestinationList)
def list_destinations(
    request: Request,
    response: Response,
    after: str | None = Query(default=None, max_length=300),
    limit: int = Query(default=20, ge=1, le=50),
    session: Session = Depends(get_session),
) -> BaseModel | Response:
    try:
        return _public(request, response, list_published_destinations(session, limit=limit, after=after))
    except InvalidCursor as error:
        raise ApiError("INVALID_CURSOR") from error


@router.get("/destinations/{destination_id}", response_model=DestinationProfile)
def destination_profile(
    request: Request,
    response: Response,
    destination_id: uuid.UUID,
    include_expired: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> BaseModel | Response:
    try:
        profile = get_destination_profile(session, destination_id, include_expired=include_expired)
    except DestinationNotFound as error:
        raise ApiError("NOT_FOUND") from error
    return _public(request, response, profile)
