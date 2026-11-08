"""SMS one-time codes (sign-up form 3, 12): one interface, swappable gateways.

- ``mailpit`` (development only): the "SMS" arrives in the local Mailpit inbox, addressed to
  ``<number>@sms.local``, so the whole phone step can be tested with no gateway and no cost.
- ``none``: refuses with 503 ``SMS_NOT_CONFIGURED``. Production stays here until a Bangladeshi
  gateway (SSL Wireless or BulkSMSBD, Twilio Verify as fallback) is added behind this interface.

A provider only delivers text; codes are generated, hashed, limited and checked by the caller.
"""

import uuid
from typing import Protocol

from app.config import get_settings
from app.errors import ApiError
from app.notify.providers import Email, MailpitProvider, SendAmbiguous, SendFailed


class SmsProvider(Protocol):
    def send(self, e164: str, text: str) -> None: ...


class MailpitSms:
    def send(self, e164: str, text: str) -> None:
        email = Email(
            to=f"{e164.lstrip('+')}@sms.local",
            subject=f"SMS to {e164}",
            text=text,
            html=f"<p>{text}</p>",
            idempotency_key=f"sms-{uuid.uuid4()}",
        )
        try:
            MailpitProvider().send(email)
        except (SendFailed, SendAmbiguous) as error:
            raise ApiError("SERVICE_UNAVAILABLE") from error


class NoSms:
    def send(self, e164: str, text: str) -> None:
        raise ApiError("SMS_NOT_CONFIGURED")


_override: SmsProvider | None = None


def get_sms() -> SmsProvider:
    if _override is not None:
        return _override
    return MailpitSms() if get_settings().sms_provider == "mailpit" else NoSms()


def use_for_tests(provider: SmsProvider | None) -> None:
    global _override
    _override = provider
