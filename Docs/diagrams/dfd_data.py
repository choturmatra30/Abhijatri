"""Abhijatri data flow diagrams as data: the context diagram and the level 0 diagram (three sheets).

Names follow the code: stores map to real tables (see STORE_TABLES), processes to real modules and routes.
Prototype parts (planner, offline packs, saved trips) are marked proto=True and drawn dashed.
Each flow on a lower level names the parent flow it realises (`of=`), so balancing is checked by content, not
only by direction (make_diagrams.py).
"""

from diagram_lib import DFD, Flow, Node

N, F = Node, Flow

# store id -> tables it stands for (used in the Word data dictionary and checked against models.py)
STORE_TABLES = {
    "D1": ("Destinations and advisories", ["destinations", "destination_guide_items", "destination_advisories", "destination_contacts"]),
    "D2": ("Users and roles", ["users", "user_roles", "auth_session_activity", "role_admin_guard"]),
    "D3": ("Reviews", ["reviews", "review_revisions", "review_category_ratings", "review_receipts", "review_media"]),
    "D4": ("Rating statistics", ["destination_rating_stats", "destination_category_stats"]),
    "D5": ("Moderation records", ["moderation_tasks", "moderation_actions", "reports", "appeals", "enforcement_cases", "sanctions",
                                  "verification_cases", "verification_evidence", "verifications"]),
    "D6": ("Outbox events", ["outbox_events"]),
    "D7": ("Notifications", ["notifications", "notification_deliveries", "notification_delivery_attempts", "notification_digests",
                             "notification_preferences", "notification_suppressions", "notification_templates", "notification_rules",
                             "notification_provider_events"]),
    "D8": ("Audit log", ["audit_events"]),
    "D9": ("Abuse limits", ["rate_limit_buckets"]),
    "D10": ("Device storage (IndexedDB)", []),  # lives in the browser, not the database; prototype for packs
    "D11": ("Idempotency keys", ["idempotency_keys"]),  # local to 6.0
    "D12": ("Visit statistics", ["visit_daily_stats"]),
}
# where each store first appears
STORE_FIRST = {"D11": "Local to 6.0 (level 1, 6.0 sheet 1)"}

# ----------------------------------------------------------------------------------------------- context flows
C1 = "destination and trip requests, guest reviews, receipt operations, visit signal"
C2 = "destination guidance, published reviews, estimates (prototype), review status"
C3 = "sign-up, sign-in, destination and trip requests, reviews, media, appeals, reports, verification evidence, inbox requests, preferences"
C4 = "session, account messages, destination guidance, review history, verification status, notifications"
C5 = "sign-in, TOTP codes, claims, decisions, outcomes, inbox requests"
C6 = "session, review queue, case files, evidence links, staff notices"
C7 = "sign-in, TOTP codes, role grants, enforcement, notification rules and templates, audit queries"
C8 = "session, staff list, case reports, audit log, delivery records, staff notices"
C9 = "panel requests (ops token)"
C10 = "health, content, traffic and queue panels"
C11 = "credentials, MFA codes, token requests"
C12 = "signed tokens, one-time tokens, user identity"
C13 = "challenge token"
C14 = "pass or fail"
C15 = "verification, reset and notification emails"
C16 = "bounce and complaint webhooks"
C17 = "signed link requests, processed files, deletions"
C18 = "uploaded files, evidence files"
C19 = "visit and event counters"
C20 = "counter totals"

CONTEXT = DFD(
    key="dfd-context",
    title="Context Diagram (Level C): The Abhijatri Platform and Everything Outside It",
    level="context",
    size=(14.4, 9.4),
    note="One process, ten external entities, no data stores. Member includes the Verified Member badge holder. Staff (Moderator, Superadmin) "
         "use the staff app; the Ops operator uses the ops app with a token.",
    nodes=[
        N("0", "process", "Abhijatri platform (PWA, API, staff and ops apps)", 72, 47, 26, 72),
        N("Guest", "entity", "Guest (traveller without an account)", 14, 79, 20, 9),
        N("Member", "entity", "Member / Verified Member", 14, 57, 20, 8),
        N("Moderator", "entity", "Moderator", 14, 35, 20, 7),
        N("Admin", "entity", "Superadmin", 14, 15, 20, 7),
        N("Ops", "entity", "Ops operator", 130, 79, 20, 7),
        N("Auth", "entity", "Supabase Auth", 130, 66, 20, 7),
        N("Turnstile", "entity", "Cloudflare Turnstile", 130, 53, 20, 8),
        N("Email", "entity", "Email provider (Brevo, Resend, SMTP or Gmail)", 130, 40, 20, 10),
        N("Storage", "entity", "Supabase Storage", 130, 27, 20, 7),
        N("Redis", "entity", "Upstash Redis", 130, 15, 20, 7),
    ],
    flows=[
        F("Guest", "0", C1, wrap=30, off=2.0), F("0", "Guest", C2, wrap=30, off=2.0),
        F("Member", "0", C3, wrap=34, off=2.0), F("0", "Member", C4, wrap=34, off=2.0),
        F("Moderator", "0", C5, wrap=30, off=2.0), F("0", "Moderator", C6, wrap=30, off=2.0),
        F("Admin", "0", C7, wrap=34, off=2.0), F("0", "Admin", C8, wrap=34, off=2.0),
        F("Ops", "0", C9, wrap=24, off=2.0), F("0", "Ops", C10, wrap=24, off=2.0),
        F("0", "Auth", C11, wrap=24, off=2.0), F("Auth", "0", C12, wrap=24, off=2.0),
        F("0", "Turnstile", C13, off=2.0), F("Turnstile", "0", C14, off=2.0),
        F("0", "Email", C15, wrap=24, off=2.0), F("Email", "0", C16, wrap=20, off=2.0),
        F("0", "Storage", C17, wrap=22, off=2.0), F("Storage", "0", C18, wrap=16, off=2.0),
        F("0", "Redis", C19, wrap=14, off=2.0), F("Redis", "0", C20, wrap=14, off=2.0),
    ],
)

# ----------------------------------------------------------------------------------------------- level 0
# Process numbering (used by every level-1 and level-2 diagram and by the Word documents):
# 1.0 Browse, 2.0 Plan offline (prototype), 3.0 Accounts, 4.0 Reviews, 5.0 Notify, 6.0 Moderate and verify, 7.0 Monitor.
# Level 0 is drawn on six sheets so that every label stays readable when printed; each process appears on exactly one
# sheet with all of its flows. People are on the left, data stores on the right, outside services above or below.
L0_NOTE = "Each process appears on one sheet with all of its flows; a store or entity may appear on several sheets. "
L0_TITLE = "Level 0 diagram"
L0_SHEET_NAMES = ["1.0 and 2.0: browsing and trip planning", "3.0: accounts", "4.0: reviews", "5.0: notifications",
                  "6.0: moderation and verification", "7.0: monitoring and retention"]


def star(key, n, pid, plabel, left, right, top=(), bottom=(), flows=(), note="", proto=False):
    """One tall process in the middle: people and outside services on the left, stores on the right. Every flow is a
    straight horizontal line, so no line crosses another and every label sits on its own arrow."""
    nodes = [N(pid, "process", plabel, 72, 48, 26, 72, proto=proto)]

    def spread(items, hi, lo):
        if len(items) == 1:
            return [(lo + hi) / 2]
        step = (hi - lo) / (len(items) - 1)
        return [hi - i * step for i in range(len(items))]

    people = list(top) + list(left) + list(bottom)
    for (nid, lab), y in zip(people, spread(people, 79, 17)):
        nodes.append(N(nid, "entity", lab, 14, y))
    for item, y in zip(right, spread(right, 80, 16)):
        nid, lab = item[0], item[1]
        nodes.append(N(nid, "store", lab, 128, y, **(item[2] if len(item) > 2 else {})))
    return DFD(key=key, group="dfd-level0", sheet=f"sheet {n} of 6: {L0_SHEET_NAMES[n - 1]}", title=L0_TITLE, level="0",
               parent="dfd-context", size=(14.4, 9.4), note=L0_NOTE + note, nodes=nodes, flows=list(flows))


L0_BROWSE = DFD(
    key="dfd-level0-a", group="dfd-level0", sheet=f"sheet 1 of 6: {L0_SHEET_NAMES[0]}",
    title=L0_TITLE, level="0", parent="dfd-context",
    size=(14.4, 9.4), xscale=144 / 126,
    note=L0_NOTE + "Dashed shapes (2.0 and D10) are prototypes. D1 is loaded by the seed migration (outside the system); staff editing of destinations is not built.",
    nodes=[
        N("Guest", "entity", "Guest", 13, 47),
        N("Member", "entity", "Member / Verified Member", 108, 47),
        N("1.0", "process", "Browse destinations and advice", 60, 68),
        N("2.0", "process", "Plan trips offline (prototype)", 60, 24, proto=True),
        N("D1", "store", "Destinations and advisories", 60, 46, w=26, loaded_by="seed migration"),
        N("D4", "store", "Rating statistics", 22, 82),
        N("D3", "store", "Reviews", 50, 86),
        N("D9", "store", "Abuse limits", 80, 86),
        N("Redis", "entity", "Upstash Redis", 108, 76),
        N("D10", "store", "Device storage (IndexedDB)", 26, 12, w=26, proto=True),
    ],
    flows=[
        F("Guest", "1.0", "destination request, visit signal", of=C1, wrap=18),
        F("1.0", "Guest", "guidance, advisories, published reviews", of=C2, wrap=18),
        F("Member", "1.0", "destination request", of=C3, wrap=18),
        F("1.0", "Member", "guidance, advisories, published reviews", of=C4, wrap=18),
        F("D1", "1.0", "destination data"),
        F("D4", "1.0", "rating summaries"),
        F("D3", "1.0", "published reviews"),
        F("1.0", "D9", "visit limits", both=True),
        F("1.0", "Redis", "guest visit counter", of=C19),
        F("Guest", "2.0", "trip inputs", of=C1),
        F("2.0", "Guest", "cost estimate, offline pack", of=C2, wrap=16),
        F("Member", "2.0", "trip inputs", of=C3),
        F("2.0", "Member", "cost estimate, offline pack", of=C4, wrap=16),
        F("D1", "2.0", "price and pack data (planned)"),
        F("2.0", "D10", "packs, trips, drafts", both=True),
    ],
)

L0_ACCOUNTS = star(
    "dfd-level0-b", 2, "3.0", "Authenticate and manage accounts",
    left=[("Member", "Member / Verified Member"), ("Moderator", "Moderator"), ("Admin", "Superadmin")],
    right=[("D9", "Abuse limits"), ("D2", "Users and roles"), ("D8", "Audit log")],
    top=[("Auth", "Supabase Auth"), ("Redis", "Upstash Redis")],
    bottom=[("Email", "Email provider")],
    note="Account emails are sent by the API through the email provider; Supabase Auth only issues the one-time tokens.",
    flows=[
        F("Member", "3.0", "sign-up, sign-in, reset request", of=C3, wrap=18),
        F("3.0", "Member", "session, account messages", of=C4, wrap=18),
        F("Moderator", "3.0", "sign-in, TOTP code", of=C5),
        F("3.0", "Moderator", "session", of=C6),
        F("Admin", "3.0", "sign-in, TOTP code, role grants", of=C7, wrap=18),
        F("3.0", "Admin", "session, staff list", of=C8),
        F("3.0", "Auth", "credentials, MFA codes, token requests", of=C11, wrap=18),
        F("Auth", "3.0", "signed tokens, one-time tokens, identity", of=C12, wrap=18),
        F("3.0", "Email", "verification and reset emails", of=C15, wrap=18),
        F("3.0", "Redis", "member visit counter", of=C19, wrap=14),
        F("3.0", "D2", "accounts, roles, visit dates", both=True, wrap=16),
        F("3.0", "D9", "sign-up and sign-in limits", both=True, wrap=16),
        F("3.0", "D8", "role-change audit"),
    ],
)

L0_REVIEWS = star(
    "dfd-level0-c", 3, "4.0", "Submit and manage reviews",
    left=[("Guest", "Guest"), ("Member", "Member / Verified Member")],
    right=[("D1", "Destinations and advisories", {"w": 26}), ("D9", "Abuse limits"), ("D3", "Reviews"), ("D4", "Rating statistics"),
           ("D5", "Moderation records"), ("D6", "Outbox events")],
    top=[("Turnstile", "Cloudflare Turnstile")],
    bottom=[("Storage", "Supabase Storage")],
    note="Turnstile checks guest submissions only. Guests prove ownership with a receipt; Members with their session. Withdrawal removes a published rating in the same transaction.",
    flows=[
        F("Guest", "4.0", "guest review, receipt operations, appeal", of=C1, wrap=18),
        F("4.0", "Guest", "review status", of=C2),
        F("Member", "4.0", "review, media, edit, withdraw, appeal, report", of=C3, wrap=18),
        F("4.0", "Member", "review status and history", of=C4, wrap=18),
        F("D1", "4.0", "destination status"),
        F("4.0", "D9", "submission and receipt limits", both=True, wrap=16),
        F("4.0", "D3", "reviews, revisions, receipts, media", both=True, wrap=18),
        F("4.0", "D4", "rating totals (withdrawal)", both=True, wrap=16),
        F("4.0", "D5", "tasks, appeals, reports, verified status", both=True, wrap=18),
        F("4.0", "D6", "review, appeal and report events", wrap=18),
        F("4.0", "Turnstile", "challenge token", of=C13),
        F("Turnstile", "4.0", "pass or fail", of=C14),
        F("4.0", "Storage", "signed link requests, processed files", of=C17, wrap=18),
        F("Storage", "4.0", "uploaded files", of=C18),
    ],
)

L0_NOTIFY = star(
    "dfd-level0-d", 4, "5.0", "Notify members and staff",
    left=[("Member", "Member / Verified Member"), ("Moderator", "Moderator"), ("Admin", "Superadmin")],
    right=[("D2", "Users and roles"), ("D6", "Outbox events"), ("D7", "Notifications"), ("D8", "Audit log")],
    bottom=[("Email", "Email provider")],
    note="Guests have no account, so they get no notifications.",
    flows=[
        F("Member", "5.0", "inbox requests, preferences", of=C3, wrap=16),
        F("5.0", "Member", "notifications", of=C4),
        F("Moderator", "5.0", "inbox requests", of=C5),
        F("5.0", "Moderator", "staff notices", of=C6),
        F("Admin", "5.0", "notification rules, templates, retries", of=C7, wrap=18),
        F("5.0", "Admin", "staff notices, delivery records", of=C8, wrap=18),
        F("D2", "5.0", "recipients, roles, language", wrap=16),
        F("5.0", "D6", "events, dead letters", both=True),
        F("5.0", "D7", "notifications, deliveries, rules", both=True, wrap=18),
        F("5.0", "D8", "admin audit"),
        F("5.0", "Email", "notification emails", of=C15),
        F("Email", "5.0", "bounce and complaint webhooks", of=C16, wrap=16),
    ],
)

L0_MODERATE = star(
    "dfd-level0-e", 5, "6.0", "Moderate, verify and rate",
    left=[("Moderator", "Moderator"), ("Member", "Member / Verified Member"), ("Admin", "Superadmin")],
    right=[("D3", "Reviews"), ("D4", "Rating statistics"), ("D5", "Moderation records"), ("D6", "Outbox events"), ("D8", "Audit log")],
    top=[("Storage", "Supabase Storage")],
    note="Ratings change in 6.0 and in 4.0 (withdrawal), always in the same transaction as the status change.",
    flows=[
        F("Moderator", "6.0", "claims, decisions, outcomes", of=C5, wrap=16),
        F("6.0", "Moderator", "queue, case files, evidence links", of=C6, wrap=18),
        F("Member", "6.0", "verification request, evidence", of=C3, wrap=16),
        F("6.0", "Member", "verification status", of=C4),
        F("Admin", "6.0", "enforcement actions", of=C7),
        F("6.0", "Admin", "case reports", of=C8),
        F("6.0", "D3", "review data", both=True),
        F("6.0", "D4", "rating totals", both=True),
        F("6.0", "D5", "tasks, decisions, cases", both=True),
        F("6.0", "D6", "decision events"),
        F("6.0", "D8", "audit records"),
        F("6.0", "Storage", "signed link requests", of=C17, wrap=14),
        F("Storage", "6.0", "evidence files", of=C18, wrap=14),
    ],
)

L0_MONITOR = star(
    "dfd-level0-f", 6, "7.0", "Monitor, audit and retain data",
    left=[("Ops", "Ops operator"), ("Admin", "Superadmin")],
    right=[("D2", "Users and roles"), ("D3", "Reviews"), ("D5", "Moderation records"), ("D6", "Outbox events"), ("D7", "Notifications"),
           ("D8", "Audit log"), ("D9", "Abuse limits"), ("D12", "Visit statistics")],
    top=[("Redis", "Upstash Redis")],
    bottom=[("Storage", "Supabase Storage")],
    note="The ops app is a separate site protected by an ops token. Retention deletes expired files, events and notifications on a schedule.",
    flows=[
        F("Ops", "7.0", "panel requests", of=C9),
        F("7.0", "Ops", "health, content, traffic and queue panels", of=C10, wrap=18),
        F("Admin", "7.0", "audit queries", of=C7),
        F("7.0", "Admin", "audit log", of=C8),
        F("Redis", "7.0", "counter totals", of=C20, wrap=12),
        F("7.0", "Redis", "event counters, rollup lock", of=C19, wrap=12),
        F("7.0", "D12", "daily visit totals", both=True),
        F("7.0", "D8", "audit log, expiry events", both=True),
        F("7.0", "D3", "review counts, expired media", both=True, wrap=28),
        F("7.0", "D5", "case counts, expired cases", both=True, wrap=28),
        F("7.0", "D6", "queue state, old events", both=True),
        F("7.0", "D7", "delivery stats, old notifications", both=True, wrap=26),
        F("D2", "7.0", "member counts"),
        F("7.0", "D9", "ops sign-in failures", both=True),
        F("7.0", "Storage", "deletions", of=C17),
    ],
)

L0_SHEETS = [L0_BROWSE, L0_ACCOUNTS, L0_REVIEWS, L0_NOTIFY, L0_MODERATE, L0_MONITOR]
