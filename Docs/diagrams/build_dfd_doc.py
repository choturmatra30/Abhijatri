"""Builds Docs/Abhijatri-DFD.docx from the diagram data, so the tables and the pictures cannot disagree.

The how-to material (symbols in depth, procedure, tools) is in build_dfd_guide.py, an internal guide.
"""

from pathlib import Path

import dfd_data
import dfd_levels
from diagram_lib import canon, check_balance, check_dfd, check_stores, merge_sheets
from dfd_data import STORE_TABLES
from docx_helpers import GOOD_FILL, Doc
from make_diagrams import run_checks

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "Abhijatri-DFD.docx"
SHEETS = dfd_levels.ALL
LOGICAL = {d.key: d for d in merge_sheets(SHEETS)}

# flow-id prefix per logical diagram (review issue D24: ids are unique across the document)
PREFIX = {
    "dfd-context": "C", "dfd-level0": "0", "dfd-level1-accounts": "3", "dfd-level1-reviews": "4",
    "dfd-level1-notifications": "5", "dfd-level1-moderation": "6", "dfd-level1-monitoring": "7",
    "dfd-level2-edit-review": "4.3", "dfd-level2-decide-review": "6.2",
}
SECTION = [  # (logical key, heading, what the diagram explains)
    ("dfd-context", "Context diagram",
     "The platform is one process. Guests and Members use the public PWA; the Moderator and the Superadmin use the staff app; the Ops operator "
     "reads the monitoring site with an ops token. Supabase Auth keeps passwords and TOTP secrets and issues tokens; Cloudflare Turnstile checks "
     "guest submissions; the email provider carries verification, reset and notification email; Supabase Storage keeps media and evidence; "
     "Upstash Redis counts visits and events."),
    ("dfd-level0", "Level 0 diagram",
     "Seven processes. The diagram is drawn on six sheets so that every label is readable at A4: each process appears on exactly one sheet "
     "with all of its flows, and a store or entity may appear on several sheets. Taken together, the six sheets are one diagram, and all "
     "checks run on that whole."),
    ("dfd-level1-accounts", "Level 1: 3.0 Authenticate and manage accounts",
     "Supabase Auth only issues tokens (including the one-time verification and reset tokens); the API mails the links itself through the "
     "email provider. Staff sign in through 3.2 and must pass TOTP in 3.4 to get an AAL2 session. Role changes need a password re-check and "
     "are written to the audit log."),
    ("dfd-level1-reviews", "Level 1: 4.0 Submit and manage reviews",
     "4.1 screens every submission (Turnstile for guests only, rate limits, destination open). 4.2 creates the review, its first revision, the "
     "receipt digest, a moderation task and an outbox event in one transaction. 4.3 and 4.4 are edit and withdraw; withdrawal also removes a "
     "counted rating (D4) and cancels open tasks (D5). 4.5 shows status and history, 4.6 handles media, 4.7 files appeals and reports."),
    ("dfd-level1-notifications", "Level 1: 5.0 Notify members and staff",
     "Events are claimed from the outbox, turned into notifications with a unique key on (event, recipient, kind), and emailed with retries "
     "after 1 minute, 5 minutes, 30 minutes and 2 hours. After six failed relay attempts an event becomes a dead letter. The Superadmin manages "
     "rules, templates and retries in 5.6; those actions are audited."),
    ("dfd-level1-moderation", "Level 1: 6.0 Moderate, verify and rate",
     "Every decision needs the task's lease token and the review's expected version. Rating totals change in 6.2 (publish, hide), 6.3 (an overturned "
     "appeal restores a review) and 6.4 (enforcement hides or restores), always in the same transaction as the status change. D11 is local to 6.2."),
    ("dfd-level1-monitoring", "Level 1: 7.0 Monitor, audit and retain data",
     "7.1 serves the ops panels from counts in D2, D3, D5, D6, D7 and D12 and today's Redis counters. 7.2 copies the daily counters into D12. "
     "7.3 shows the audit log to the Superadmin. 7.4 deletes expired records and files on a schedule."),
    ("dfd-level2-edit-review", "Level 2: 4.3 Edit unpublished review",
     "An edit is allowed only while the review is PENDING or CHANGES_REQUESTED. A wrong receipt counts toward the progressive block in D9. "
     "The previous revision is marked SUPERSEDED, a new append-only revision is written, and a moderation task is queued again."),
    ("dfd-level2-decide-review", "Level 2: 6.2 Decide review",
     "A stale version gives REVIEW_VERSION_CONFLICT, a lost lease gives LEASE_LOST, and a moderator cannot decide their own review. "
     "Status, rating totals, media states, action row, audit event and outbox event commit together."),
]

L0_PROCESSES = [
    ["1.0 Browse destinations and advice", "Serves published destination profiles, advisories with their freshness state, contacts, rating "
     "summaries and the public review feed; records the guest visit counter.", "destination_api.py, api.py (feed, /guest-visits), visits.py"],
    ["2.0 Plan trips offline (prototype)", "Cost estimate, offline pack and saved trip screens. Prototype only: no estimator API, service worker "
     "or IndexedDB exists yet.", "frontend PlannerPage, OfflinePacksPage, SavedTripsPage"],
    ["3.0 Authenticate and manage accounts", "Register, verify email, sign in and out, reset password, staff TOTP, sessions with CSRF, staff "
     "roles; records member visits.", "auth/routes.py, auth/sessions.py, auth/mail.py, admin/roles.py"],
    ["4.0 Submit and manage reviews", "Create (guest, member), edit while unpublished, withdraw, status and history, media, appeals and reports.",
     "services.py, api.py, member_routes.py, media.py"],
    ["5.0 Notify members and staff", "Turns outbox events into notifications and email; inbox, preferences, webhooks, digests; "
     "rules, templates and retries for the Superadmin.", "notify/worker.py, notify/messages.py, notify/delivery.py, notify/admin_routes.py"],
    ["6.0 Moderate, verify and rate", "Task queue with leases, review decisions with the rating change in the same transaction, appeals, "
     "reports, enforcement, verification cases.", "admin/routes.py, admin/actions.py, admin/cases.py, services.moderate_review"],
    ["7.0 Monitor, audit and retain data", "Ops panels, daily visit rollup, the Superadmin's audit log view, retention and sanction expiry.",
     "ops/providers/*, visits.py (rollup), admin/routes.py (audit), jobs/retention.py"],
]

ENTITIES = [
    ["Guest", "A traveller without an account", "Destination and trip requests, guest reviews with a receipt, receipt operations, appeals",
     "Guidance, published reviews, review status (no notifications: a Guest has no account)"],
    ["Member / Verified Member", "A signed-in user; Verified Member is a badge after staff approval",
     "Sign-up, sign-in, reviews, media, appeals, reports, verification evidence, inbox requests, preferences",
     "Session, account messages, review history, verification status, notifications"],
    ["Moderator", "Staff with the moderator role and TOTP", "Sign-in, TOTP codes, claims, decisions, outcomes, inbox requests",
     "Session, queue, case files, evidence links, staff notices"],
    ["Superadmin", "Staff with the superadmin role and TOTP", "Sign-in, TOTP codes, role grants, enforcement, notification rules and templates, audit queries",
     "Session, staff list, case reports, audit log, delivery records, staff notices"],
    ["Ops operator", "A person holding the ops token", "Panel requests", "Health, content, traffic and queue panels"],
    ["Supabase Auth", "Hosted identity service (see note on the Platform Foundation deviation)", "Signed tokens, one-time tokens, user identity",
     "Credentials, MFA codes, token requests"],
    ["Cloudflare Turnstile", "Bot check service, used for guest submissions", "Pass or fail", "Challenge token"],
    ["Email provider", "SMTP, Gmail, Brevo or Resend (EMAIL_PROVIDER)", "Bounce and complaint webhooks", "Verification, reset and notification emails"],
    ["Supabase Storage", "Private object storage", "Uploaded (quarantined) files, evidence files", "Signed link requests, processed files, deletions"],
    ["Upstash Redis", "Counter service", "Counter totals", "Visit and event counters, rollup lock"],
]


def nm(d, node_id):
    n = d.node(node_id)
    return f"{n.tag or canon(n.id)} {n.label}" if n.kind != "entity" else n.label


def ids(key):
    """Flow ids for a logical diagram, numbered in sheet order: {id(flow): 'X-Fn'}."""
    return {id(f): f"{PREFIX[key]}-F{i}" for i, f in enumerate(LOGICAL[key].flows, 1)}


def sheet_of(flow):
    for s in SHEETS:
        if any(f is flow for f in s.flows):
            return s.sheet.split(":")[0].replace("sheet ", "") if s.sheet else "1 of 1"
    return ""


def check_tables() -> list[str]:
    """Every table named in a data store must exist in backend/app/models.py."""
    import re

    models = (HERE.parents[1] / "backend" / "app" / "models.py").read_text(encoding="utf-8")
    existing = set(re.findall(r'__tablename__ = "(\w+)"', models))
    return [f"{sid}: table {t} not in models.py" for sid, (_, tables) in STORE_TABLES.items() for t in tables if t not in existing]


def main() -> None:
    _, rule, layout = run_checks(SHEETS, draw=False)
    tables = check_tables()
    assert not (rule or tables), rule + tables

    nsheets = len(SHEETS)
    nflows = sum(len(d.flows) for d in LOGICAL.values())
    nproc = sum(1 for d in LOGICAL.values() for n in d.nodes if n.kind == "process")
    l0 = LOGICAL["dfd-level0"]
    l0_stores = sorted({canon(n.id) for n in l0.nodes if n.kind == "store"}, key=lambda s: int(s[1:]))

    doc = Doc(
        "Data Flow Diagrams",
        "The Abhijatri data flow model as built: context, level 0, level 1 and level 2",
        [
            ("Project", "Abhijatri: a Bangla-first, offline-ready community travel platform for Bangladesh (Team ChoturMatra, CSE 3102)"),
            ("Document", "Data flow diagrams (DFD) with data dictionary, balancing table and verification record"),
            ("Version", "1.1, 31 October 2026 (replaces 1.0 of 30 October 2026)"),
            ("Basis", "The implemented system: backend/app/models.py (tables), Docs/api/openapi-v1.json (88 paths, 92 operations), "
                      "Docs/Architecture.md, Docs/Backend-Implemented.md 5.13 to 5.19, Docs/Decisions.md"),
            ("Notation", "Gane-Sarson: rounded process boxes with a number, open-ended data stores with a D-number, external entities as "
                         "rectangles with a double border"),
            ("Regenerate", "python Docs/diagrams/make_diagrams.py, then python Docs/diagrams/build_dfd_doc.py"),
        ],
        "Abhijatri: Data Flow Diagrams",
    )
    doc.contents()

    # ------------------------------------------------------------------ 4 figures
    doc.landscape()
    doc.h1("1. The diagrams")
    first_page = True
    for key, heading, _ in SECTION:
        sheets = [s for s in SHEETS if s.group == key]
        for i, s in enumerate(sheets):
            doc.h2(heading) if i == 0 else doc.h3(f"{heading} (continued)")
            if not first_page:  # break before the heading, not after the caption (an empty paragraph could spill onto its own page)
                doc.d.paragraphs[-1].paragraph_format.page_break_before = True
            first_page = False
            cap = heading + (f", {s.sheet}" if s.sheet else "")
            doc.figure(HERE / f"{s.key}.png", cap, 24.5, 12.9 if key == "dfd-context" else 14.6)  # the first page also holds the h1

    # ------------------------------------------------------------------ 5 data dictionary
    doc.portrait()
    doc.h1("2. Data dictionary")
    doc.h2("2.1 External entities")
    doc.table(["Entity", "Who or what it is", "What it gives the system", "What it receives"], ENTITIES, [3.0, 4.0, 5.0, 4.5],
              caption="External entities", size=8.6)
    doc.h2("2.2 Data stores")
    rows = []
    for sid, (name, tables) in sorted(STORE_TABLES.items(), key=lambda kv: int(kv[0][1:])):
        first = dfd_data.STORE_FIRST.get(sid, "Level 0")
        extra = "; loaded by the seed migration" if sid == "D1" else ""
        rows.append([sid, name, (", ".join(tables) if tables else "Browser storage, not a database table (prototype)"), first + extra])
    doc.table(["Store", "Name", "Tables or place", "Where first shown"], rows, [1.3, 3.8, 7.9, 3.5], caption="Data stores and the tables behind them", size=8.4)
    doc.p("The table names come from backend/app/models.py; the build script confirms that each one exists there.")
    doc.h2("2.3 Data flows")
    doc.p("Flow ids carry their diagram's prefix (C for context, 0 for level 0, 4 for the level 1 diagram of 4.0, 4.3 for the level 2 diagram "
          "of 4.3), so every id is unique in this document. \"Realises\" names the parent diagram's flow that a flow is part of.")
    for key, heading, _ in SECTION:
        d = LOGICAL[key]
        fid = ids(key)
        multi = sum(1 for s in SHEETS if s.group == key) > 1

        def realises(f, d=d):
            if not d.parent:
                return ""
            if d.node(f.src).kind == "process" and d.node(f.dst).kind == "process":
                return "(internal)"
            return f.of or f.label

        rows = [[fid[id(f)], sheet_of(f) if multi else "", nm(d, f.src), nm(d, f.dst), f.label + (" (read and write)" if f.both else ""),
                 realises(f)]
                for f in d.flows]
        doc.h3(heading)
        head = ["ID", "Sheet", "From", "To", "Data flow", "Realises"]
        widths = [1.2, 1.2, 3.3, 3.3, 3.8, 3.7]
        keep = [i for i in range(6) if (i != 1 or multi) and (i != 5 or d.parent)]
        spare = (16.5 - sum(widths[i] for i in keep)) / 3  # give dropped columns' width to From, To and Data flow
        widths = [w + (spare if i in (2, 3, 4) else 0) for i, w in enumerate(widths)]
        doc.table([head[i] for i in keep], [[r[i] for i in keep] for r in rows], [widths[i] for i in keep], size=7.8)

    # ------------------------------------------------------------------ 6 balancing
    doc.h1("3. Balancing: the levels agree")
    doc.p("For every parent flow that crosses a decomposed process's boundary, the table lists the child flows that realise it. "
          "The script also confirms the reverse: no child flow crosses the boundary without realising a parent flow. "
          "Level 0 is balanced against the context diagram in the same way.")
    rows, fills = [], {}
    for child in LOGICAL.values():
        if not child.parent:
            continue
        parent = LOGICAL[child.parent]
        pids = {"0"} if parent.level == "context" else {child.parent_process}
        own = {n.id for n in child.nodes if n.kind == "process"}
        pf = [f for f in parent.flows if (f.src in pids) != (f.dst in pids)]
        cf = [f for f in child.flows if (f.src in own) != (f.dst in own)]
        cid, pidmap = ids(child.key), ids(parent.key)
        for f in pf:
            other = f.dst if f.src in pids else f.src
            direction = "to" if f.src in pids else "from"
            real = [g for g in cf if (g.of or g.label) == f.label and canon(g.dst if g.src in own else g.src) == canon(other)]
            rows.append([f"Level {child.level}" + (f" of {child.parent_process}" if child.parent_process else ""), pidmap[id(f)] + " " + direction + " " +
                         nm(parent, other).replace(" (traveller without an account)", ""), f.label,
                         "; ".join(f"{cid[id(g)]} {g.label}" for g in real) or "MISSING"])
            fills[(len(rows) - 1, 3)] = GOOD_FILL if real else "F9DFD8"
    nbal = len(rows)
    doc.table(["Child", "Parent flow", "Parent label", "Child flows that realise it"], rows, [2.4, 4.2, 4.4, 5.5],
              caption="Parent flows and the child flows that realise them", size=7.4, fills=fills)

    doc.save(OUT)
    print("saved", OUT, f"({nbal} balancing rows, {nflows} flows)")


if __name__ == "__main__":
    main()
