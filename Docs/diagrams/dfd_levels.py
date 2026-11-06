"""Level 1 and level 2 data flow diagrams of Abhijatri (children of the level 0 diagram in dfd_data.py).

Balancing is checked by content: every flow that crosses a child's boundary names, with `of=`, the parent flow it
realises, on the same outside node and in the same direction; every parent flow must be realised at least once.
A store used by only one process may first appear on that process's level 1 diagram ("local" store, D11).
Large diagrams are drawn on several sheets; each process appears on one sheet with all of its flows.
"""

from dfd_data import CONTEXT, L0_SHEETS
from diagram_lib import DFD, Flow, Node, lanes

N, F = Node, Flow
SIZE = (14.4, 9.4)
LEG = None

# ------------------------------------------------------------------ parent flow names (level 0, process 4.0)
R_GIN = "guest review, receipt operations, appeal"
R_GOUT = "review status"
R_MIN = "review, media, edit, withdraw, appeal, report"
R_MOUT = "review status and history"
R_D1 = "destination status"
R_D9 = "submission and receipt limits"
R_D3 = "reviews, revisions, receipts, media"
R_D4 = "rating totals (withdrawal)"
R_D5 = "tasks, appeals, reports, verified status"
R_D6 = "review, appeal and report events"
R_TS_OUT, R_TS_IN = "challenge token", "pass or fail"
R_ST_OUT, R_ST_IN = "signed link requests, processed files", "uploaded files"



def P(pid, label):
    return N(pid, "process", label, 0, 0)


def E(nid, label, **kw):
    return (nid, "entity", label, kw)


def S(nid, label, **kw):
    return (nid, "store", label, kw)


GUEST, MEMBER = E("Guest", "Guest"), E("Member", "Member / Verified Member")
MOD, ADMIN, OPS = E("Moderator", "Moderator"), E("Admin", "Superadmin"), E("Ops", "Ops operator")
AUTH, EMAIL, REDIS = E("Auth", "Supabase Auth"), E("Email", "Email provider"), E("Redis", "Upstash Redis")
TURNSTILE, STORAGE = E("Turnstile", "Cloudflare Turnstile"), E("Storage", "Supabase Storage")
D1, D2, D3, D4 = S("D1", "Destinations and advisories", w=26), S("D2", "Users and roles"), S("D3", "Reviews"), S("D4", "Rating statistics")
D5, D6, D7, D8 = S("D5", "Moderation records"), S("D6", "Outbox events"), S("D7", "Notifications"), S("D8", "Audit log")
D9, D11, D12 = S("D9", "Abuse limits"), S("D11", "Idempotency keys"), S("D12", "Visit statistics")


def sheet(key, group, title, parent_process, n, total, name, lane_specs, flows, note):
    """A level 1 sheet laid out in lanes; it takes every flow that touches one of its processes."""
    pids = {spec[0].id for spec in lane_specs}
    mine = [f for f in flows if f.src in pids or f.dst in pids]
    return lanes(key, title, lanes=lane_specs, flows=mine, size=SIZE, level="1", parent="dfd-level0", parent_process=parent_process,
                 group=group, sheet=f"sheet {n} of {total}: {name}", note=note, legend=LEG)


# ------------------------------------------------------------------ level 1: 4.0 reviews
REVIEW_FLOWS = [
        F("Guest", "4.1", "guest review, receipt, Turnstile token", of=R_GIN, wrap=40),
        F("Member", "4.1", "member review", of=R_MIN),
        F("4.1", "Turnstile", "challenge token", of=R_TS_OUT),
        F("Turnstile", "4.1", "pass or fail", of=R_TS_IN),
        F("D1", "4.1", "destination status", of=R_D1),
        F("4.1", "D9", "submission limits", both=True, of=R_D9),
        F("4.1", "Guest", "refusal", of=R_GOUT),
        F("4.1", "Member", "refusal", of=R_MOUT),
        F("4.1", "4.2", "valid submission"),
        F("D5", "4.2", "verified status", of=R_D5),
        F("4.2", "D5", "moderation task", of=R_D5),
        F("4.2", "D3", "review, first revision, receipt digest", of=R_D3, wrap=18),
        F("4.2", "D6", "review.submitted", of=R_D6),
        F("4.2", "Guest", "review id, receipt", of=R_GOUT),
        F("4.2", "Member", "review id, status", of=R_MOUT),
        F("Guest", "4.3", "edit + receipt", of=R_GIN),
        F("Member", "4.3", "edit request", of=R_MIN),
        F("D3", "4.3", "current revision", of=R_D3),
        F("4.3", "D3", "new revision", of=R_D3),
        F("4.3", "D5", "re-queued task", of=R_D5),
        F("4.3", "D6", "review.edited", of=R_D6),
        F("4.3", "D9", "failed-receipt counter", both=True, of=R_D9),
        F("4.3", "Guest", "new version or refusal", of=R_GOUT),
        F("4.3", "Member", "new version or refusal", of=R_MOUT),
        F("Guest", "4.4", "withdraw + receipt", of=R_GIN),
        F("Member", "4.4", "withdraw request", of=R_MIN),
        F("4.4", "D9", "failed-receipt counter", both=True, of=R_D9),
        F("4.4", "D3", "withdrawn status", both=True, of=R_D3),
        F("4.4", "D4", "rating removed", both=True, of=R_D4),
        F("4.4", "D5", "cancelled tasks", of=R_D5),
        F("4.4", "D6", "review.withdrawn", of=R_D6),
        F("4.4", "Guest", "withdrawal status", of=R_GOUT),
        F("4.4", "Member", "withdrawal status", of=R_MOUT),
        F("Guest", "4.5", "status request + receipt", of=R_GIN),
        F("Member", "4.5", "history request", of=R_MIN),
        F("D3", "4.5", "review data", of=R_D3),
        F("D5", "4.5", "appeal state", of=R_D5),
        F("4.5", "Guest", "status, reason, appeal deadline", of=R_GOUT, wrap=14),
        F("4.5", "Member", "review, history", of=R_MOUT),
        F("Member", "4.6", "media request", of=R_MIN),
        F("4.6", "Storage", "signed link request, processed file", of=R_ST_OUT, wrap=18),
        F("Storage", "4.6", "quarantined upload", of=R_ST_IN),
        F("4.6", "D3", "media records", both=True, of=R_D3),
        F("4.6", "Member", "upload link, media status", of=R_MOUT),
        F("Guest", "4.7", "guest appeal + receipt", of=R_GIN),
        F("Member", "4.7", "appeal, report", of=R_MIN),
        F("D3", "4.7", "review state", of=R_D3),
        F("4.7", "D5", "appeal or report case", both=True, of=R_D5),
        F("4.7", "D6", "appeal.received, report events", of=R_D6, wrap=18),
        F("4.7", "Guest", "appeal accepted or refused", of=R_GOUT),
        F("4.7", "Member", "appeal or report accepted", of=R_MOUT),
]
T4 = "Level 1 diagram: 4.0 Submit and manage reviews"
L1_REVIEWS_A = sheet("dfd-level1-reviews-a", "dfd-level1-reviews", T4, "4.0", 1, 3, "screen and create", [
    (P("4.1", "Screen submission"), [GUEST, MEMBER], [TURNSTILE, D1, D9]),
    (P("4.2", "Create review"), [GUEST, MEMBER], [D5, D3, D6]),
], REVIEW_FLOWS, "Turnstile checks guest submissions only; member submissions rely on the session and CSRF token. A Guest proves ownership "
                 "with the receipt. Refusals "
                 "(limit reached, challenge failed, destination closed) return to the sender. A stroke in a corner marks a copy of a "
                 "box already drawn on the sheet.")
L1_REVIEWS_B = sheet("dfd-level1-reviews-b", "dfd-level1-reviews", T4, "4.0", 2, 3, "edit and withdraw", [
    (P("4.3", "Edit unpublished review"), [GUEST, MEMBER], [D9, D3, D5, D6]),
    (P("4.4", "Withdraw review"), [GUEST, MEMBER], [D9, D3, D4, D5, D6]),
], REVIEW_FLOWS, "Withdrawal is refused only for a review already WITHDRAWN or DELETED. It removes a published rating from D4 and "
                 "cancels open moderation tasks in the same transaction. Wrong receipts are counted in D9.")
L1_REVIEWS_C = sheet("dfd-level1-reviews-c", "dfd-level1-reviews", T4, "4.0", 3, 3, "status, media and appeals", [
    (P("4.5", "Show status and history"), [GUEST, MEMBER], [D3, D5]),
    (P("4.6", "Attach photos and video"), [MEMBER], [STORAGE, D3]),
    (P("4.7", "File appeal or report"), [GUEST, MEMBER], [D3, D5, D6]),
], REVIEW_FLOWS, "Uploads land in a quarantine folder and are copied to processed/ after checks. Members attach media; guest reviews "
                 "are text only.")

# ------------------------------------------------------------------ level 1: 6.0 moderation (level 0 flow names)
M_MIN, M_MOUT = "claims, decisions, outcomes", "queue, case files, evidence links"
M_UIN, M_UOUT = "verification request, evidence", "verification status"
M_AIN, M_AOUT = "enforcement actions", "case reports"
M_D3, M_D4, M_D5, M_D6, M_D8 = "review data", "rating totals", "tasks, decisions, cases", "decision events", "audit records"
M_ST_OUT, M_ST_IN = "signed link requests", "evidence files"

MOD_FLOWS = [
        F("Moderator", "6.1", "claim, heartbeat, release", of=M_MIN, wrap=16),
        F("6.1", "Moderator", "queue, lease token", of=M_MOUT),
        F("6.1", "D5", "task state, lease", both=True, of=M_D5),
        F("D3", "6.1", "review preview", of=M_D3),
        F("6.1", "D8", "task audit", of=M_D8),
        F("Moderator", "6.2", "decision + lease + version", of=M_MIN, wrap=16),
        F("6.2", "Moderator", "decision result or refusal", of=M_MOUT, wrap=16),
        F("6.2", "D11", "idempotency key, stored result", both=True, wrap=18),
        F("6.2", "D5", "action, task done", both=True, of=M_D5),
        F("6.2", "D3", "review state, media", both=True, of=M_D3),
        F("6.2", "D4", "rating totals", both=True, of=M_D4),
        F("6.2", "D6", "state_changed event", of=M_D6),
        F("6.2", "D8", "decision audit", of=M_D8),
        F("Moderator", "6.3", "appeal outcome", of=M_MIN),
        F("6.3", "Moderator", "appeal case file", of=M_MOUT),
        F("6.3", "D5", "appeal state", both=True, of=M_D5),
        F("6.3", "D3", "restored or kept review", both=True, of=M_D3, wrap=16),
        F("6.3", "D4", "restored rating", both=True, of=M_D4),
        F("6.3", "D6", "appeal.decided", of=M_D6),
        F("6.3", "D8", "appeal audit", of=M_D8),
        F("Admin", "6.4", "enforcement actions", of=M_AIN),
        F("6.4", "Admin", "case reports", of=M_AOUT),
        F("Moderator", "6.4", "report decision", of=M_MIN),
        F("6.4", "Moderator", "report case file", of=M_MOUT),
        F("6.4", "D5", "reports, cases, sanctions", both=True, of=M_D5, wrap=16),
        F("6.4", "D3", "hide or restore", both=True, of=M_D3),
        F("6.4", "D4", "rating totals", both=True, of=M_D4),
        F("6.4", "D6", "enforcement and sanction events", of=M_D6, wrap=18),
        F("6.4", "D8", "enforcement audit", of=M_D8),
        F("Member", "6.5", "verification request, evidence", of=M_UIN, wrap=16),
        F("6.5", "Member", "verification status", of=M_UOUT),
        F("Moderator", "6.5", "verification decision", of=M_MIN),
        F("6.5", "Moderator", "case, evidence links", of=M_MOUT),
        F("6.5", "Storage", "signed link requests", of=M_ST_OUT),
        F("Storage", "6.5", "evidence files", of=M_ST_IN),
        F("6.5", "D5", "verification case", both=True, of=M_D5),
        F("6.5", "D6", "verification events", of=M_D6),
        F("6.5", "D8", "verification audit", of=M_D8),
]
T6 = "Level 1 diagram: 6.0 Moderate, verify and rate"
L1_MOD_A = sheet("dfd-level1-moderation-a", "dfd-level1-moderation", T6, "6.0", 1, 3, "queue and review decisions", [
    (P("6.1", "Manage task queue"), [MOD], [D5, D3, D8]),
    (P("6.2", "Decide review"), [MOD, D11], [D5, D3, D4, D6, D8]),
], MOD_FLOWS, "Every decision needs a task lease and the review's version. D11 is local to this process (first shown here). "
              "Ratings change in the same transaction as the status change.")
L1_MOD_B = sheet("dfd-level1-moderation-b", "dfd-level1-moderation", T6, "6.0", 2, 3, "appeals, reports and enforcement", [
    (P("6.3", "Decide appeals"), [MOD], [D5, D3, D4, D6, D8]),
    (P("6.4", "Handle reports and enforcement"), [ADMIN, MOD], [D5, D3, D4, D6, D8]),
], MOD_FLOWS, "An overturned appeal or a lifted enforcement restores a hidden review and its rating; enforcement can hide a published "
              "review and remove its rating.")
L1_MOD_C = sheet("dfd-level1-moderation-c", "dfd-level1-moderation", T6, "6.0", 3, 3, "member verification", [
    (P("6.5", "Verify members"), [MEMBER, MOD], [STORAGE, D5, D6, D8]),
], MOD_FLOWS, "Verification evidence is read through short-lived signed links; the files stay in Supabase Storage and are deleted "
              "24 hours after approval or 30 days after rejection or withdrawal (7.4).")

# ------------------------------------------------------------------ level 1: 5.0 notifications
NOTIFY_FLOWS = [
        F("D6", "5.1", "due events, dead letters", both=True, of="events, dead letters", wrap=14),
        F("5.1", "5.2", "event"),
        F("D2", "5.2", "recipients, roles, language", of="recipients, roles, language", wrap=16),
        F("D7", "5.2", "rules, preferences", of="notifications, deliveries, rules"),
        F("5.2", "D7", "notifications, delivery rows", of="notifications, deliveries, rules", wrap=16),
        F("Member", "5.3", "inbox requests, preferences", of="inbox requests, preferences", wrap=16),
        F("5.3", "Member", "notifications, unread count", of="notifications", wrap=13),
        F("Moderator", "5.3", "inbox requests", of="inbox requests"),
        F("5.3", "Moderator", "staff notices", of="staff notices"),
        F("5.3", "Admin", "staff notices", of="staff notices, delivery records"),
        F("5.3", "D7", "read marks, preferences", both=True, of="notifications, deliveries, rules", wrap=16),
        F("D2", "5.4", "email address, language", of="recipients, roles, language", wrap=16),
        F("D7", "5.4", "due deliveries", of="notifications, deliveries, rules"),
        F("5.4", "D7", "attempt outcome", of="notifications, deliveries, rules"),
        F("5.4", "Email", "notification emails", of="notification emails"),
        F("Email", "5.5", "bounce and complaint webhooks", of="bounce and complaint webhooks", wrap=16),
        F("5.5", "D7", "suppressions, provider events", of="notifications, deliveries, rules", wrap=16),
        F("Admin", "5.6", "rules, templates, retries", of="notification rules, templates, retries", wrap=16),
        F("5.6", "Admin", "delivery records", of="staff notices, delivery records"),
        F("5.6", "D7", "rules, templates, deliveries", both=True, of="notifications, deliveries, rules", wrap=16),
        F("5.6", "D6", "dead letters to retry", both=True, of="events, dead letters", wrap=14),
        F("5.6", "D8", "admin audit", of="admin audit"),
]
T5 = "Level 1 diagram: 5.0 Notify members and staff"
L1_NOTIFY_A = sheet("dfd-level1-notifications-a", "dfd-level1-notifications", T5, "5.0", 1, 2, "events to inboxes", [
    (P("5.1", "Relay outbox events"), [], [D6], 0.7),
    (P("5.2", "Create notifications"), [], [D2, D7], 0.9),
    (P("5.3", "Serve inbox and preferences"), [MEMBER, MOD, ADMIN], [D7], 1.4),
], NOTIFY_FLOWS, "Processing is at-least-once and idempotent: the unique key (event, recipient, kind) stops duplicates. Guests have "
                 "no inbox and get no notifications.")
L1_NOTIFY_B = sheet("dfd-level1-notifications-b", "dfd-level1-notifications", T5, "5.0", 2, 2, "email and administration", [
    (P("5.4", "Send email"), [], [D2, D7, EMAIL]),
    (P("5.5", "Handle provider webhooks"), [], [EMAIL, D7]),
    (P("5.6", "Administer notifications"), [ADMIN], [D7, D6, D8]),
], NOTIFY_FLOWS, "After 6 failed tries an event becomes a dead letter, which a Superadmin can retry (5.6). Bounces and complaints "
                 "suppress further email to that address.")

# ------------------------------------------------------------------ level 1: 3.0 accounts
A_MIN, A_MOUT = "sign-up, sign-in, reset request", "session, account messages"
A_OIN, A_OOUT = "sign-in, TOTP code", "session"
A_SIN, A_SOUT = "sign-in, TOTP code, role grants", "session, staff list"
A_AUTH_OUT, A_AUTH_IN = "credentials, MFA codes, token requests", "signed tokens, one-time tokens, identity"
A_EMAIL, A_REDIS = "verification and reset emails", "member visit counter"
A_D2, A_D9, A_D8 = "accounts, roles, visit dates", "sign-up and sign-in limits", "role-change audit"

ACCOUNT_FLOWS = [
        F("Member", "3.1", "email, password, token", of=A_MIN),
        F("3.1", "Member", "check-your-email message", of=A_MOUT, wrap=16),
        F("3.1", "Auth", "sign-up, token request", of=A_AUTH_OUT),
        F("Auth", "3.1", "one-time token, user id", of=A_AUTH_IN, wrap=14),
        F("3.1", "Email", "verification email", of=A_EMAIL),
        F("3.1", "D9", "sign-up limits", both=True, of=A_D9),
        F("3.1", "D2", "new user record", of=A_D2),
        F("Member", "3.2", "sign-in, sign-out", of=A_MIN),
        F("3.2", "Member", "session, CSRF token", of=A_MOUT),
        F("Moderator", "3.2", "sign-in", of=A_OIN),
        F("3.2", "Moderator", "session", of=A_OOUT),
        F("Admin", "3.2", "sign-in", of=A_SIN),
        F("3.2", "Admin", "session", of=A_SOUT),
        F("3.2", "Auth", "credentials, refresh", of=A_AUTH_OUT),
        F("Auth", "3.2", "tokens, identity", of=A_AUTH_IN),
        F("3.2", "D9", "sign-in limits", both=True, of=A_D9),
        F("3.2", "D2", "user, role, visit date", both=True, of=A_D2),
        F("3.2", "Redis", "member visit counter", of=A_REDIS),
        F("Member", "3.3", "reset request, new password", of=A_MIN, wrap=16),
        F("3.3", "Member", "reset result", of=A_MOUT),
        F("3.3", "Auth", "reset token request", of=A_AUTH_OUT),
        F("Auth", "3.3", "one-time reset token", of=A_AUTH_IN),
        F("3.3", "Email", "reset email", of=A_EMAIL),
        F("3.3", "D9", "reset limits", both=True, of=A_D9),
        F("Moderator", "3.4", "TOTP code", of=A_OIN),
        F("3.4", "Moderator", "QR code, AAL2 session", of=A_OOUT),
        F("Admin", "3.4", "TOTP code", of=A_SIN),
        F("3.4", "Admin", "QR code, AAL2 session", of=A_SOUT),
        F("3.4", "Auth", "MFA enrol, verify", of=A_AUTH_OUT),
        F("Auth", "3.4", "AAL2 tokens", of=A_AUTH_IN),
        F("Admin", "3.5", "role grants, password re-check", of=A_SIN, wrap=16),
        F("3.5", "Admin", "staff list", of=A_SOUT),
        F("3.5", "Auth", "re-check request", of=A_AUTH_OUT),
        F("Auth", "3.5", "re-check result", of=A_AUTH_IN),
        F("3.5", "D2", "roles", both=True, of=A_D2),
        F("3.5", "D9", "re-check limits", both=True, of=A_D9),
        F("3.5", "D8", "role-change audit", of=A_D8),
]
T3 = "Level 1 diagram: 3.0 Authenticate and manage accounts"
L1_ACCOUNTS_A = sheet("dfd-level1-accounts-a", "dfd-level1-accounts", T3, "3.0", 1, 2, "register and sign in", [
    (P("3.1", "Register and verify email"), [MEMBER], [AUTH, EMAIL, D9, D2]),
    (P("3.2", "Sign in and keep session"), [MEMBER, MOD, ADMIN], [AUTH, D9, D2, REDIS]),
], ACCOUNT_FLOWS, "Passwords and TOTP secrets are held by Supabase Auth, never by the Abhijatri database. Supabase Auth issues the "
                  "one-time tokens; the API sends the emails through the configured email provider.")
L1_ACCOUNTS_B = sheet("dfd-level1-accounts-b", "dfd-level1-accounts", T3, "3.0", 2, 2, "reset and staff security", [
    (P("3.3", "Reset password"), [MEMBER], [AUTH, EMAIL, D9]),
    (P("3.4", "Enrol and verify TOTP"), [MOD, ADMIN], [AUTH]),
    (P("3.5", "Manage staff roles"), [ADMIN], [AUTH, D2, D9, D8], 1.2),
], ACCOUNT_FLOWS, "Staff (Moderator, Superadmin) need TOTP (AAL2). A role change also needs a recent password re-check and is "
                  "written to the audit log.")

# ------------------------------------------------------------------ level 1: 7.0 monitoring
MONITOR_FLOWS = [
        F("Ops", "7.1", "panel requests", of="panel requests"),
        F("7.1", "Ops", "panels", of="health, content, traffic and queue panels"),
        F("7.1", "D9", "ops sign-in failures", both=True, of="ops sign-in failures", wrap=14),
        F("D2", "7.1", "member counts", of="member counts"),
        F("D3", "7.1", "review counts", of="review counts, expired media"),
        F("D5", "7.1", "case counts", of="case counts, expired cases"),
        F("D6", "7.1", "queue state", of="queue state, old events"),
        F("D7", "7.1", "delivery stats", of="delivery stats, old notifications"),
        F("D12", "7.1", "daily visits", of="daily visit totals"),
        F("Redis", "7.1", "today's counters", of="counter totals"),
        F("7.2", "Redis", "rollup lock, event counters", of="event counters, rollup lock", wrap=16),
        F("Redis", "7.2", "counter totals", of="counter totals"),
        F("7.2", "D12", "daily visit totals", both=True, of="daily visit totals", wrap=14),
        F("Admin", "7.3", "audit queries", of="audit queries"),
        F("7.3", "Admin", "audit log", of="audit log"),
        F("D8", "7.3", "audit events", of="audit log, expiry events"),
        F("7.4", "D3", "expired media", both=True, of="review counts, expired media"),
        F("7.4", "D5", "expired cases", both=True, of="case counts, expired cases"),
        F("7.4", "D6", "old events", both=True, of="queue state, old events"),
        F("7.4", "D7", "old notifications", both=True, of="delivery stats, old notifications"),
        F("7.4", "Storage", "deletions", of="deletions"),
        F("7.4", "D8", "expiry events", of="audit log, expiry events"),
]
T7 = "Level 1 diagram: 7.0 Monitor, audit and retain data"
L1_MONITOR_A = sheet("dfd-level1-monitoring-a", "dfd-level1-monitoring", T7, "7.0", 1, 2, "ops panels and visit rollup", [
    (P("7.1", "Serve ops panels"), [OPS, D2, D9], [D3, D5, D6, D7, D12, REDIS]),
    (P("7.2", "Roll up visits"), [], [REDIS, D12]),
], MONITOR_FLOWS, "The ops app is a separate site protected by an ops token. Today's numbers come from Redis; earlier days from D12, "
                  "filled once a day by 7.2.")
L1_MONITOR_B = sheet("dfd-level1-monitoring-b", "dfd-level1-monitoring", T7, "7.0", 2, 2, "audit log and retention", [
    (P("7.3", "Show audit log"), [ADMIN], [D8]),
    (P("7.4", "Apply retention"), [D8, STORAGE], [D3, D5, D6, D7]),
], MONITOR_FLOWS, "Retention: verification files 24 h after approval and 30 days after rejection or withdrawal; notifications 90 or "
                  "730 days; outbox events 30 days. Each run is audited.")

# ------------------------------------------------------------------ level 2: 4.3 edit (parent flows from L1_REVIEWS_A)
L2_EDIT = DFD(
    key="dfd-level2-edit-review",
    title="Level 2 diagram: 4.3 Edit unpublished review", level="2", parent="dfd-level1-reviews", parent_process="4.3",
    size=SIZE, legend=LEG, xscale=144 / 126,
    note="Allowed only while PENDING or CHANGES_REQUESTED. The edit is a new append-only revision; nothing is counted because the review "
         "is not published. Wrong receipts are counted in D9. A stroke in a corner marks a copy of a box already on the sheet.",
    nodes=[
        N("Guest", "entity", "Guest", 11, 80, dup=True),
        N("Member", "entity", "Member / Verified Member", 11, 67, dup=True),
        N("4.3.1", "process", "Authenticate owner", 46, 74),
        N("D9", "store", "Abuse limits", 86, 85),
        N("Guest~r", "entity", "Guest", 11, 53, dup=True),
        N("Member~r", "entity", "Member / Verified Member", 11, 41, dup=True),
        N("4.3.2", "process", "Check state and version", 46, 47),
        N("D3", "store", "Reviews", 82, 62),
        N("4.3.3", "process", "Validate and merge changes", 112, 47),
        N("4.3.4", "process", "Write new revision", 112, 26),
        N("4.3.5", "process", "Re-queue and emit event", 72, 24),
        N("Guest~n", "entity", "Guest", 11, 27, dup=True),
        N("Member~n", "entity", "Member / Verified Member", 11, 15, dup=True),
        N("D5", "store", "Moderation records", 108, 13),
        N("D6", "store", "Outbox events", 52, 11),
    ],
    flows=[
        F("Guest", "4.3.1", "edit + receipt", of="edit + receipt"),
        F("Member", "4.3.1", "edit + session", of="edit request"),
        F("4.3.1", "D9", "failed-receipt counter", both=True, of="failed-receipt counter", wrap=14),
        F("D3", "4.3.1", "receipt digest, author id", of="current revision", wrap=14),
        F("4.3.1", "Guest", "wrong receipt", of="new version or refusal"),
        F("4.3.1", "4.3.2", "owner confirmed"),
        F("D3", "4.3.2", "status, version", of="current revision"),
        F("4.3.2", "Guest~r", "not editable or stale", of="new version or refusal", wrap=14),
        F("4.3.2", "Member~r", "not editable or stale", of="new version or refusal", wrap=14),
        F("4.3.2", "4.3.3", "editable review"),
        F("D3", "4.3.3", "current revision, categories", of="current revision", wrap=16),
        F("4.3.3", "4.3.4", "validated values"),
        F("4.3.4", "D3", "new revision", of="new revision"),
        F("4.3.4", "4.3.5", "revision number"),
        F("4.3.5", "D5", "moderation task", of="re-queued task"),
        F("4.3.5", "D6", "review.edited", of="review.edited"),
        F("4.3.5", "Member~n", "new version", of="new version or refusal"),
        F("4.3.5", "Guest~n", "new version", of="new version or refusal"),
    ],
)

# ------------------------------------------------------------------ level 2: 6.2 decide review (parent flows from L1_MOD_A)
L2_DECIDE = DFD(
    key="dfd-level2-decide-review",
    title="Level 2 diagram: 6.2 Decide review", level="2", parent="dfd-level1-moderation", parent_process="6.2",
    size=SIZE, legend=LEG, xscale=144 / 126,
    note="All writes commit together. A stale version returns REVIEW_VERSION_CONFLICT; a lost lease returns LEASE_LOST; a moderator "
         "cannot decide their own review. A repeated request with the same idempotency key returns the stored result.",
    nodes=[
        N("D11", "store", "Idempotency keys", 16, 82),
        N("D5", "store", "Moderation records", 46, 84, dup=True),
        N("D3", "store", "Reviews", 80, 84),
        N("D4", "store", "Rating statistics", 110, 86),
        N("Moderator", "entity", "Moderator", 11, 58, dup=True),
        N("6.2.1", "process", "Verify lease and version", 44, 60),
        N("6.2.2", "process", "Apply state transition", 80, 60),
        N("6.2.3", "process", "Update rating totals", 112, 70),
        N("6.2.4", "process", "Decide media", 112, 46),
        N("6.2.5", "process", "Record audit and emit event", 72, 30),
        N("Moderator~r", "entity", "Moderator", 11, 30, dup=True),
        N("D5~w", "store", "Moderation records", 38, 14, dup=True),
        N("D8", "store", "Audit log", 108, 30),
        N("D6", "store", "Outbox events", 108, 18),
    ],
    flows=[
        F("Moderator", "6.2.1", "decision, task id, lease, version", of="decision + lease + version", wrap=14),
        F("6.2.1", "Moderator", "refusal (conflict, lease lost)", of="decision result or refusal", wrap=14),
        F("6.2.1", "D11", "key, stored result", both=True, of="idempotency key, stored result", wrap=14),
        F("D5", "6.2.1", "task and lease", of="action, task done"),
        F("D3", "6.2.1", "review version", of="review state, media"),
        F("6.2.1", "6.2.2", "checked decision", wrap=10),
        F("D3", "6.2.2", "review, revision", of="review state, media"),
        F("6.2.2", "D3", "new status, version", of="review state, media"),
        F("6.2.2", "6.2.3", "publish or hide transition", wrap=14),
        F("6.2.3", "D4", "totals", both=True, of="rating totals"),
        F("6.2.2", "6.2.4", "decision"),
        F("6.2.4", "D3", "media states", of="review state, media"),
        F("6.2.2", "6.2.5", "transition record"),
        F("6.2.5", "D5~w", "moderation action, task done", of="action, task done", wrap=14),
        F("6.2.5", "D8", "audit event", of="decision audit"),
        F("6.2.5", "D6", "state_changed event", of="state_changed event"),
        F("6.2.5", "Moderator~r", "decision result", of="decision result or refusal"),
    ],
)

# every sheet, in document order
ALL = [CONTEXT, *L0_SHEETS, L1_ACCOUNTS_A, L1_ACCOUNTS_B, L1_REVIEWS_A, L1_REVIEWS_B, L1_REVIEWS_C, L1_NOTIFY_A, L1_NOTIFY_B,
       L1_MOD_A, L1_MOD_B, L1_MOD_C, L1_MONITOR_A, L1_MONITOR_B, L2_EDIT, L2_DECIDE]
