"""Verification and password-reset emails sent by this API (AUTH_EMAIL_DELIVERY=app).

Supabase Auth only issues the one-time token (``admin/generate_link`` sends nothing); the email goes
out through the configured provider (Brevo, SMTP, Resend or the local Mailpit inbox). Sending runs
after the response is returned, so a known and an unknown address answer in the same time. The token
is never logged.
"""

import hashlib
import logging
from datetime import UTC, datetime
from html import escape
from urllib.parse import quote

from app.config import get_settings
from app.notify.providers import Email, SendAmbiguous, SendFailed, get_provider

logger = logging.getLogger(__name__)


def _link(path: str, token_hash: str, kind: str) -> str:
    return f"{get_settings().frontend_base_url.rstrip('/')}/{path}?token_hash={quote(token_hash)}&type={kind}"


WHY_EN = "You received this email because this address was entered on Abhijatri (abhijatri.vercel.app), a travel guide for Bangladesh."
WHY_BN = "এই ঠিকানাটি অভিযাত্রী (বাংলাদেশ ভ্রমণ গাইড) সাইটে দেওয়া হয়েছিল বলে আপনি এই ইমেইল পেয়েছেন।"


def _email(to: str, subject: str, heading_en: str, heading_bn: str, line_en: str, line_bn: str, link: str, footer_en: str, footer_bn: str, key: str) -> Email:
    """A small, well-formed bilingual message: plain-text and HTML parts with the same content, one button,
    the link written out once as a fallback, and a footer saying who sent it and why. Spam filters score
    malformed HTML, mismatched text and HTML parts, and unexplained senders; this avoids all three."""
    text = (
        f"{heading_en}\n\n{line_en}\n\n{link}\n\n{footer_en}\n\n"
        f"{heading_bn}\n\n{line_bn}\n\n{footer_bn}\n\n"
        f"--\nAbhijatri / অভিযাত্রী\n{WHY_EN}\n{WHY_BN}\n"
    )
    button = (
        f'<a href="{escape(link)}" style="display:inline-block;padding:12px 22px;background:#1b4d2b;color:#ffffff;'
        f'border-radius:8px;text-decoration:none;font-weight:bold">{escape(heading_en)} / {escape(heading_bn)}</a>'
    )
    html = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(subject)}</title></head>"
        '<body style="margin:0;padding:24px;background:#f6f7f5;font-family:Arial,Helvetica,sans-serif;color:#1d1d1d">'
        '<div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:12px;padding:24px">'
        '<p style="margin:0 0 16px;font-weight:bold;color:#1b4d2b">Abhijatri / অভিযাত্রী</p>'
        f'<h1 style="font-size:20px;margin:0 0 12px">{escape(heading_en)}</h1>'
        f'<p style="line-height:1.5">{escape(line_en)}</p>'
        f'<p lang="bn" style="line-height:1.6">{escape(line_bn)}</p>'
        f'<p style="margin:24px 0">{button}</p>'
        '<p style="font-size:12px;color:#555">If the button does not work, copy this address into your browser / বাটন কাজ না করলে এই ঠিকানাটি ব্রাউজারে খুলুন:<br>'
        f'<span style="word-break:break-all">{escape(link)}</span></p>'
        f'<p style="font-size:12px;color:#555">{escape(footer_en)}<br><span lang="bn">{escape(footer_bn)}</span></p>'
        '<hr style="border:none;border-top:1px solid #e5e5e5;margin:20px 0">'
        f'<p style="font-size:11px;color:#777">{escape(WHY_EN)}<br><span lang="bn">{escape(WHY_BN)}</span></p>'
        "</div></body></html>"
    )
    return Email(to=to, subject=subject, text=text, html=html, idempotency_key=key)


def verification_email(to: str, token_hash: str, name: str | None) -> Email:
    greeting = f"Hello {name}," if name else "Hello,"
    return _email(
        to,
        "Confirm your Abhijatri account",
        "Confirm your email", "ইমেইল নিশ্চিত করুন",
        f"{greeting} open this link to verify your email address. It works for 24 hours.",
        "আপনার ইমেইল যাচাই করতে লিংকটি খুলুন। এটি ২৪ ঘণ্টা কার্যকর।",
        _link("verify-email", token_hash, "signup"),
        "If you did not create an account, ignore this email.", "আপনি অ্যাকাউন্ট না খুললে এই ইমেইলটি উপেক্ষা করুন।",
        f"verify-{token_hash[:16]}",
    )


def reset_email(to: str, token_hash: str) -> Email:
    return _email(
        to,
        "Reset your Abhijatri password / পাসওয়ার্ড রিসেট করুন",
        "Choose a new password", "নতুন পাসওয়ার্ড দিন",
        "Open this link to choose a new password. It works for 1 hour.",
        "নতুন পাসওয়ার্ড দিতে লিংকটি খুলুন। এটি ১ ঘণ্টা কার্যকর।",
        _link("reset-password", token_hash, "recovery"),
        "If you did not ask for this, ignore this email; your password is unchanged.", "আপনি না চাইলে উপেক্ষা করুন; পাসওয়ার্ড বদলায়নি।",
        f"reset-{token_hash[:16]}",
    )


def existing_account_email(to: str) -> Email:
    """Someone signed up with an address that already has an account. Only the inbox owner reads this, so it tells
    them without telling the person at the form (who sees the usual "check your email")."""
    base = get_settings().frontend_base_url.rstrip("/")
    return _email(
        to,
        "You already have an Abhijatri account",
        "You already have an account", "আপনার ইতিমধ্যে অ্যাকাউন্ট আছে",
        "Someone, probably you, tried to sign up with this email address, which already has an account. Sign in instead. "
        f"If you forgot your password, reset it here: {base}/forgot-password",
        "এই ইমেইলে ইতিমধ্যে একটি অ্যাকাউন্ট আছে, তাই নতুন করে খোলা যায়নি। সাইন ইন করুন; "
        f"পাসওয়ার্ড ভুলে গেলে এখানে রিসেট করুন: {base}/forgot-password",
        f"{base}/login",
        "If this was not you, you can ignore this email; nothing changed on your account.",
        "আপনি না করলে এই ইমেইলটি উপেক্ষা করুন; আপনার অ্যাকাউন্টে কিছু বদলায়নি।",
        f"existing-{hashlib.sha256(to.encode()).hexdigest()[:16]}-{datetime.now(UTC).date().isoformat()}",
    )


def deliver(email: Email) -> None:
    """Runs after the response (FastAPI background task). Failures are logged without the token or address."""
    provider = get_provider()
    if provider is None:
        logger.warning("account email not sent: EMAIL_PROVIDER is none")
        return
    try:
        provider.send(email)
    except SendAmbiguous:
        logger.warning("account email may not have been delivered (%s)", provider.name)
    except SendFailed as error:
        logger.warning("account email failed via %s: %s", provider.name, error)
