from slowapi import Limiter

from app.client_address import rate_limit_key
from app.config import get_settings

settings = get_settings()

# Burst pre-filter only. The authoritative limits are the durable counters in app.abuse.
limiter = Limiter(
    key_func=rate_limit_key,
    enabled=settings.rate_limit_enabled,
    storage_uri=settings.rate_limit_storage_uri,
)


def guest_submit_limit() -> str:
    return get_settings().rate_limit_guest_submit


def receipt_limit() -> str:
    return get_settings().rate_limit_receipt


def guest_visit_limit() -> str:
    return get_settings().rate_limit_guest_visit
