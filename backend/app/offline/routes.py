"""Public offline-pack routes (R14): manifest, versioned pack bytes and the reconnect freshness check.

All three are GET-only CORS simple requests with no credentials. They are on the public cache
allowlist as "Versioned public destination packs" (Security 7.1): ``public, max-age=60`` with an
ETag, and the pack itself carries its version and maximum age. Errors stay ``no-store``.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session
from app.destination_api import _etag, public_cache_headers
from app.errors import ApiError
from app.limits import limiter, pack_download_limit, pack_freshness_limit, pack_manifest_limit
from app.offline.packs import (
    MAX_FRESHNESS_IDS,
    CurrentPack,
    PackNotFound,
    PackWithdrawn,
    content_digest,
    ensure_current_pack,
    freshness,
    manifest_of,
)
from app.schemas import PackDocument, PackFreshness, PackManifest

router = APIRouter(prefix="/api/v1")


def _opaque(tag: str) -> str:
    return tag.strip().removeprefix("W/")


def if_none_match(header: str | None, etag: str) -> bool:
    """Weak comparison, as RFC 9110 requires for ``If-None-Match``."""
    if not header:
        return False
    candidates = {_opaque(part) for part in header.split(",")}
    return "*" in candidates or _opaque(etag) in candidates


def _current(session: Session, destination_id: uuid.UUID) -> CurrentPack:
    try:
        return ensure_current_pack(session, destination_id)
    except PackNotFound as error:
        raise ApiError("NOT_FOUND") from error
    except PackWithdrawn as error:
        raise ApiError("PACK_WITHDRAWN") from error


def _public_json(request: Request, response: Response, payload: BaseModel) -> BaseModel | Response:
    headers = public_cache_headers(_etag(payload))
    if if_none_match(request.headers.get("if-none-match"), headers["ETag"]):
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return payload


@router.get(
    "/destinations/{destination_id}/pack/manifest",
    response_model=PackManifest,
    responses={404: {}, 410: {}},
)
@limiter.limit(pack_manifest_limit)
def pack_manifest(
    request: Request,
    response: Response,
    destination_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> BaseModel | Response:
    return _public_json(request, response, manifest_of(_current(session, destination_id)))


@router.get(
    "/destinations/{destination_id}/pack",
    response_model=PackDocument,
    responses={404: {}, 409: {}, 410: {}},
)
@limiter.limit(pack_download_limit)
def pack_download(
    request: Request,
    destination_id: uuid.UUID,
    version: int | None = Query(default=None, ge=1, le=2_147_483_647),
    session: Session = Depends(get_session),
) -> Response:
    """The stored bytes, byte for byte, so the device can check them against the manifest."""
    row = _current(session, destination_id).row
    if version is not None and version != row.pack_version:
        raise ApiError("PACK_VERSION_SUPERSEDED")
    headers = {
        **public_cache_headers(f'"{row.sha256}"'),
        "Content-Digest": content_digest(row.sha256),
    }
    if if_none_match(request.headers.get("if-none-match"), headers["ETag"]):
        return Response(status_code=304, headers=headers)
    return Response(content=row.body, media_type="application/json", headers=headers)


@router.get("/packs/freshness", response_model=PackFreshness)
@limiter.limit(pack_freshness_limit)
def pack_freshness(
    request: Request,
    response: Response,
    destination_id: list[uuid.UUID] = Query(min_length=1, max_length=MAX_FRESHNESS_IDS),
    session: Session = Depends(get_session),
) -> BaseModel | Response:
    if len(set(destination_id)) != len(destination_id):
        raise ApiError(
            "VALIDATION_FAILED", field_errors=[{"field": "destination_id", "code": "DUPLICATE"}]
        )
    return _public_json(request, response, freshness(session, destination_id))
