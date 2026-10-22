"""Members panel: account counts only (Dashboard doc 4). Shows "member sign-in not built" until R04."""

from sqlalchemy import func, or_, select

from app.models import PlatformRole, User, UserPlatformRole, Verification
from app.ops.registry import Panel, PanelContext, PanelResult, register, stat, status, table


@register
class MembersPanel(Panel):
    id = "members"
    title = {"bn": "সদস্য", "en": "Members"}
    refresh_seconds = 300
    sources = ("postgres",)

    def collect(self, ctx: PanelContext) -> PanelResult:
        with ctx.sessions() as session:
            members = int(session.scalar(select(func.count()).select_from(User)) or 0)
            verified_email = int(
                session.scalar(select(func.count()).where(User.email_verified_at.is_not(None))) or 0
            )
            badges = int(
                session.scalar(
                    select(func.count(func.distinct(Verification.user_id))).where(
                        Verification.status == "APPROVED",
                        Verification.revoked_at.is_(None),
                        or_(Verification.expires_at.is_(None), Verification.expires_at > ctx.now),
                    )
                )
                or 0
            )
            staff = session.execute(
                select(PlatformRole.code, func.count(func.distinct(UserPlatformRole.user_id)))
                .join(UserPlatformRole, UserPlatformRole.role_id == PlatformRole.id)
                .where(or_(UserPlatformRole.expires_at.is_(None), UserPlatformRole.expires_at > ctx.now))
                .group_by(PlatformRole.code)
                .order_by(PlatformRole.code)
            ).all()
        return PanelResult(
            fresh={"postgres": ctx.now},
            blocks=[
                status(
                    "member_sign_in",
                    {"bn": "সদস্য সাইন-ইন", "en": "Member sign-in"},
                    "not built",
                    level="warn",
                ),
                stat("members", {"bn": "সদস্য", "en": "Members"}, members),
                stat("email_verified", {"bn": "ইমেইল যাচাইকৃত", "en": "Email verified"}, verified_email),
                stat("verified_member_badges", {"bn": "ভেরিফায়েড মেম্বার ব্যাজ", "en": "Verified Member badges"}, badges),
                table(
                    "staff_by_role",
                    {"bn": "ভূমিকা অনুযায়ী স্টাফ", "en": "Staff by role"},
                    ["role", "accounts"],
                    [[code, int(count)] for code, count in staff],
                ),
            ],
        )
