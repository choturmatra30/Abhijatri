from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.rate_limit_enabled,
    storage_uri=settings.rate_limit_storage_uri,
)


def guest_submit_limit() -> str:
    return get_settings().rate_limit_guest_submit


def receipt_limit() -> str:
    return get_settings().rate_limit_receipt
