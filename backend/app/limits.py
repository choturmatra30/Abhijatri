from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

limiter = Limiter(key_func=get_remote_address, enabled=get_settings().rate_limit_enabled)


def guest_submit_limit() -> str:
    return get_settings().rate_limit_guest_submit


def receipt_limit() -> str:
    return get_settings().rate_limit_receipt
