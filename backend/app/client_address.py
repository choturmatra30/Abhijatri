"""The one place the client network address is derived (Platform Foundation 14.2).

Uvicorn runs without ``--proxy-headers``, so ``request.client`` is the platform proxy. The real
client is the single provider-appended entry of one configured header, selected by position
(default: the right-most entry, which the edge appends). Left-most entries and every other
forwarding header are client-controlled and are never read.

The raw address lives only for the request. Callers store ``network_digest`` and nothing else.
"""

import ipaddress

from starlette.requests import Request

from app import crypto
from app.config import get_settings

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def _parse(value: str) -> IPAddress | None:
    candidate = value.strip().strip("[]")
    if candidate.count(":") == 1 and "." in candidate:  # IPv4 with a port, e.g. 203.0.113.7:4711
        candidate = candidate.rsplit(":", 1)[0]
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


def trusted_client_address(request: Request) -> IPAddress | None:
    settings = get_settings()
    header = settings.client_address_header
    if header:
        entries = [part for part in request.headers.get(header, "").split(",") if part.strip()]
        try:
            chosen = entries[settings.client_address_position]
        except IndexError:
            chosen = ""
        address = _parse(chosen)
        if address is not None:
            return address
        # A missing or malformed provider header must not fall back to a client-controlled value.
    peer = request.client.host if request.client else ""
    return _parse(peer)


def normalise(address: IPAddress | None) -> str:
    """IPv4 as-is; IPv6 truncated to its /64 prefix (one subscriber)."""
    if address is None:
        return "unknown"
    if isinstance(address, ipaddress.IPv6Address):
        return str(ipaddress.ip_network(f"{address}/64", strict=False).network_address) + "/64"
    return str(address)


def network_digest(request: Request) -> bytes:
    return crypto.digest(crypto.NETWORK_LABEL, crypto.current_key_id(), normalise(trusted_client_address(request)))


def rate_limit_key(request: Request) -> str:
    """Key for the in-memory burst pre-filter (never stored)."""
    return normalise(trusted_client_address(request))
