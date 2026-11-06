"""Builds Docs/Abhijatri-SRS-Completion.docx: the standalone Software Requirements Specification (IEEE 29148 structure).

Version 1.0 also held a coverage check of the proposal; that is now the internal document built by build_srs_coverage.py.
"""

import json
from collections import Counter
from pathlib import Path

from docx_helpers import Doc

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
OUT = DOCS / "Abhijatri-SRS-Completion.docx"

GREEN, AMBER, RED = "E3F3EA", "FFF4D6", "F9DFD8"


def api_groups() -> list[list[str]]:
    spec = json.loads((DOCS / "api" / "openapi-v1.json").read_text(encoding="utf-8"))
    counts = Counter()
    for path, methods in spec["paths"].items():
        route = path.replace("/api/v1", "")
        seg = route.strip("/").split("/")
        key = "/" + seg[0]
        if seg[0] == "admin":
            key = "/admin"
        counts[key] += sum(1 for m in methods if m in ("get", "post", "put", "patch", "delete"))
    meaning = {
        "/admin": "Staff API: task queue and leases, review decisions, appeals, reports, enforcement, verification cases, audit log, staff roles, notification administration, media decisions",
        "/auth": "Registration, email verification, sign-in and sign-out, password reset, TOTP enrolment, re-authentication, session and CSRF token",
        "/reviews": "Guest and member review creation, edit while unpublished, withdraw, owner view, member history, media upload, reports",
        "/review-receipts": "Receipt status and guest appeals (the receipt travels in the request body)",
        "/destinations": "Published destination list, profile, and the public review feed",
        "/notifications": "Member inbox, unread count, mark read, live stream",
        "/notification-preferences": "Email and notification preferences",
        "/appeals": "Member appeals against rejection or hiding",
        "/verifications": "Verified Member requests and evidence",
        "/ops": "Operator panels (token protected)",
        "/health": "Liveness and readiness",
        "/staff": "Legacy: the first moderation endpoints from the vertical slice; superseded by /admin and kept only for old tests",
        "/guest-visits": "First-visit signal counted in Redis",
        "/review-parameters": "Limits and labels the review form needs",
        "/webhooks": "Email provider callbacks",
    }
    rows = [[k, str(v), meaning.get(k, "")] for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
    rows.append(["Total", str(sum(counts.values())), "operations in Docs/api/openapi-v1.json"])
    return rows


def main() -> None:
    doc = Doc(
        "Software Requirements Specification",
        "Requirements of the Abhijatri platform, with the status of each as built on 31 October 2026",
        [
            ("Project", "Abhijatri: a Bangla-first, offline-ready community travel platform for Bangladesh (Team ChoturMatra, CSE 3102)"),
            ("Document", "Software Requirements Specification (SRS)"),
            ("Version", "1.1, 31 October 2026 (replaces the SRS completion notes, version 1.0 of 30 October 2026)"),
            ("Based on", "Docs/Abhijatri_Project_Proposal.tex (12 October 2026) and the repository on 31 October 2026"),
            ("Structure", "IEEE 29148-2018: 1 Introduction, 2 Overall description, 3 Specific requirements, 4 Verification, 5 As built "
                          "versus proposed, appendices"),
            ("Companion documents", "Abhijatri-DFD.docx (data flow diagrams) and Abhijatri-Venn-Diagram.docx"),
        ],
        "Abhijatri: Software Requirements Specification",
    )
    doc.contents()

    # ---- 4.1
    doc.h1("1. Introduction")
    doc.h2("1.1 Purpose")
    doc.p("This Software Requirements Specification describes Abhijatri, a Bangla-first, offline-ready community travel platform for Bangladesh. It states what the system must do and the qualities it must have, "
          "so that the team, the instructor and the evaluators can judge the finished product against the same list. It is written for the four team members (frontend, backend, quality assurance and project leader), the course instructor and external evaluators.")
    doc.h2("1.2 Scope")
    doc.p("Abhijatri lets travellers explore destinations in Bangla or English, read dated advisories, write and read moderated reviews, and (in the semester plan) estimate trip cost and use destination packs without a connection. "
          "Staff moderate content, decide appeals, verify members and monitor the system.")
    doc.table(
        ["In scope (semester MVP)", "Out of scope (future or excluded)"],
        [
            ["Five seeded destination profiles with sourced, dated guidance, contacts and advisories", "Real payment, SMS gateways, NID verification, live inventory"],
            ["Bangla and English interface", "Native mobile applications"],
            ["Guest and member reviews, structured ratings, moderation, appeals, reports, notifications", "Live chat, arbitrary private groups, vendor responses, booking"],
            ["Accounts, email verification, TOTP for staff, roles, audit log", "Automated sentiment analysis and machine-learning moderation"],
            ["Operations dashboard and retention jobs", "Editing a published review (withdraw and resubmit instead)"],
            ["Prototype screens for cost planning, offline packs and saved trips (not yet functional)", "Agency and guide onboarding, commissions"],
        ],
        [8.2, 8.3], caption="Scope boundary",
    )
    doc.h2("1.3 Definitions, acronyms and abbreviations")
    gl = [
        ["API", "Application programming interface. Here, the FastAPI service under /api/v1."],
        ["Appeal", "A request to reconsider a rejection or hiding decision, allowed until the end of the 30th day (Asia/Dhaka)."],
        ["AAL2", "Authenticator assurance level 2: a session that passed a second factor (TOTP). Staff routes require it."],
        ["Audit event", "An append-only record of a privileged action: who, what, when, and why."],
        ["BDT", "Bangladeshi taka."],
        ["CSRF", "Cross-site request forgery; prevented with a token that must accompany every signed-in write."],
        ["Draft id", "A random UUID created on the device for one review; the server keeps only one review per draft id, so retries are safe."],
        ["Guest", "A visitor without an account. Guest reviews never change the Community Rating."],
        ["Guest Feedback", "The average of published Guest ratings, shown separately from the Community Rating."],
        ["Guest tag", "A short random badge (for example 1C669-J0TDY) derived on the device from the scope secret; it names a Guest "
                      "without an account and reveals no traffic volume."],
        ["Idempotency-Key", "A request header on staff moderation decisions; replaying the same key returns the stored result instead "
                            "of deciding twice."],
        ["Community Rating", "A Bayesian score built only from eligible Verified Member reviews: (sum + 5 x 3.5) / (count + 5). "
                             "It is shown only once a destination has at least five eligible reviews (the Bayesian threshold)."],
        ["Consent version", "The version of the moderation and retention notice the author accepted; every submission records it."],
        ["Dead letter", "An outbox event that failed six relay attempts; it stops retrying and is shown to the Superadmin and the ops panels."],
        ["IndexedDB", "The browser database planned for drafts and offline packs (not built yet)."],
        ["Lease", "A time-limited claim (300 seconds) a moderator holds on a task so two people do not decide the same item."],
        ["Member / Verified Member", "A signed-in user / a member whose identity evidence staff approved."],
        ["MFA / TOTP", "Multi-factor authentication / time-based one-time password from an authenticator app."],
        ["Moderator / Superadmin", "Staff roles. Both need TOTP; only a superadmin can grant roles."],
        ["MVP", "Minimum viable product: the semester deliverable."],
        ["Ops operator", "A person holding the ops token who reads the separate monitoring site; not a staff role."],
        ["Outbox", "A database table of events written in the same transaction as the change they describe, processed later by a worker."],
        ["PWA", "Progressive web application: a website that can be installed and work offline."],
        ["RLS", "PostgreSQL row-level security, enabled on every public table."],
        ["Receipt", "A secret the Guest's browser generates (abr1_ plus 43 characters). The server stores only a keyed digest and never reissues it."],
        ["Rating eligibility", "Whether a published review counts: ELIGIBLE (Verified Member), INELIGIBLE_GUEST (counts in Guest "
                               "Feedback only), INELIGIBLE_UNVERIFIED, or INELIGIBLE_CONFLICT (author declared a conflict of interest)."],
        ["Revision", "One saved version of a review's content; revisions are append-only."],
        ["Scope secret", "A 48-byte random secret kept in the Guest's browser; the server stores only a keyed digest. It links one "
                         "browser's reviews and gives the guest tag."],
        ["Supabase", "Hosted PostgreSQL, identity and storage provider used by the project."],
        ["Turnstile", "Cloudflare's bot-check widget used on guest submissions."],
        ["Verified Visit", "A future, separate claim that a visit happened; not the same as Verified Member."],
        ["WP / R-number", "Work package and Gantt task identifiers (for example R07 = structured review CRUD)."],
    ]
    doc.table(["Term", "Meaning in this project"], gl, [3.4, 13.1], caption="Glossary", size=8.6, bold_first_col=True)
    doc.h2("1.4 References")
    doc.bullets([
        "Abhijatri Project Proposal, 12 October 2026 (`Docs/Abhijatri_Project_Proposal.pdf`).",
        "`Docs/Architecture.md`, `Docs/Schema.md`, `Docs/Security.md`, `Docs/Implemented.md`.",
        "`Docs/Decisions.md`, in particular 27 October 2026: Supabase Auth (a recorded deviation from Platform Foundation 8.1), "
        "account email sent by the API, and media for every signed-in member.",
        "`Docs/Backend-Implemented.md` and `Docs/Frontend-Implemented.md` (what is built and the evidence).",
        "`Docs/api/API.md` and `Docs/api/openapi-v1.json` (the API contract).",
        "`Features/Review.md`, `Features/Platform-Foundation.md`, `Features/Execution.md` (feature specifications).",
        "`Docs/Moderation-Dashboard-Specification.md`, `Docs/Notification-Documentation.md`, `Docs/System-Monitoring-Dashboard.md`.",
        "IEEE Std 29148-2018, Systems and software engineering: Life cycle processes: Requirements engineering (structure of this SRS).",
        "Abhijatri-DFD.docx (data flow diagrams, version 1.1) and Abhijatri-Venn-Diagram.docx (companion documents).",
    ])
    doc.h2("1.5 Overview of the rest of this document")
    doc.p("Section 2 describes the product in context, its users, constraints, dependencies and costs. Section 3 gives the specific "
          "requirements: interfaces (3.1), features and their status (3.2), data (3.3), use cases (3.4), behaviour models (3.5) and "
          "non-functional requirements (3.6). Section 4 traces requirements to code and tests. Section 5 compares the proposal with what "
          "was built. Appendix A summarises the data flow model and Appendix B records revisions and approval.")

    # ---- 4.2
    doc.h1("2. Overall description")
    doc.h2("2.1 Product perspective")
    doc.p("Abhijatri is a new, self-contained system with four deployable parts and a small number of external services. "
          "The public web app (React, TypeScript) talks only to the API; it holds no database key. The FastAPI service enforces all authorisation, moderation, receipt checks and rating arithmetic. "
          "PostgreSQL (hosted by Supabase) is the source of truth. A separate staff web app and a private operations app use the same API.")
    doc.p("Figure 1 on the next page shows the system and the ten external entities around it (the context data flow diagram).")
    doc.landscape()
    doc.figure(HERE / "dfd-context.png", "System context (the context data flow diagram from Abhijatri-DFD.docx)", 24.5, 15.6)
    doc.portrait()
    doc.h2("2.2 Product functions")
    doc.table(
        ["Function group", "What the system does", "DFD process"],
        [
            ["Destination guidance", "Shows bilingual destination profiles, advisories with a current, stale or expired state, contacts and rating summaries", "1.0"],
            ["Trip planning (prototype)", "Estimate cost, save trip briefs, download packs", "2.0"],
            ["Accounts", "Register, verify email, sign in, reset password, TOTP for staff, roles", "3.0"],
            ["Reviews", "Create, edit while unpublished, withdraw, view status and history, attach media, appeal, report", "4.0"],
            ["Notifications", "In-app inbox and email with preferences, retries and digests", "5.0"],
            ["Moderation", "Task queue, decisions, ratings, appeals, reports, enforcement, verification", "6.0"],
            ["Operations", "Ops panels, daily visit rollup, audit log view, retention", "7.0"],
        ],
        [3.6, 10.5, 2.4], caption="Product functions and the data flow processes that realise them",
    )
    doc.h2("2.3 User classes")
    doc.table(
        ["User class", "Description", "Technical skill", "Can do"],
        [
            ["Guest", "Traveller without an account; may use Bangla only and a low-end Android phone", "Low", "Browse, read reviews, submit reviews (each with its own receipt, within rate limits), check status, edit or withdraw them, appeal a rejection"],
            ["Member", "Signed-in user with a verified email", "Low to medium", "Everything a Guest can; also own review history, media upload, appeals, reports, notifications, verification request"],
            ["Verified Member", "Member whose evidence staff approved", "Low to medium", "Their reviews can count toward the Community Rating"],
            ["Moderator", "Staff with TOTP", "Medium", "Claim tasks, decide reviews, appeals and reports, review verification"],
            ["Superadmin", "Staff with TOTP and a recent password check for sensitive actions", "High", "Everything a moderator can; grant roles, take enforcement action, administer notifications, read the audit log, see dead letters and delivery records"],
            ["Ops operator", "Holds the ops token", "High", "Read monitoring panels only"],
        ],
        [2.6, 5.4, 2.3, 6.2], caption="User classes",
    )
    doc.p("These six names are used in every Abhijatri document. The data flow diagrams draw Member and Verified Member as one "
          "entity, because they exchange the same kinds of data; the use case diagram shows Verified Member separately.")
    doc.h2("2.4 Operating environment")
    doc.bullets([
        "Client: current Chromium-based Android browsers and modern desktop browsers; Safari limitations are documented where a device is available.",
        "Server: Python 3.12 container running FastAPI behind HTTPS; PostgreSQL 17 (Supabase); Redis over TLS for counters only.",
        "Build: Node 22 for the three front-end apps; CI on every pull request (lint, type check, tests, migration check, dependency audit, secret scan, image build).",
        "Time zone: the server stores UTC; dates shown to users and appeal deadlines use Asia/Dhaka.",
    ])
    doc.h2("2.5 Design and implementation constraints")
    doc.table(
        ["ID", "Constraint", "Source"],
        [
            ["C1", "Bangla is the default language; Bangla text must render correctly including conjuncts, and names are limited by code point count, not bytes.", "Proposal; Review.md 3.4"],
            ["C2", "The browser never holds a database or service key; all authority is on the server.", "Architecture.md section 1"],
            ["C3", "No real payment, SMS gateway, NID or live inventory in the semester.", "Proposal MVP exclusions"],
            ["C4", "Total direct cost must stay within the planning ceiling of BDT 6,000.", "Proposal feasibility"],
            ["C5", "Final completion on 17 or 18 January 2027; formal testing 4 to 11 January 2027.", "Proposal timeline"],
            ["C6", "A published review is never edited; the author withdraws and writes a new one.", "Review.md 5.2"],
            ["C7", "A Guest review never changes the Community Rating; receipts are never reissued.", "Review.md 3.2, 4.2"],
            ["C8", "Personal data is minimised: no NID, no payment data; optional contacts stay on the device.", "Proposal privacy; Security.md"],
            ["C9", "Hosted free or low-cost tiers limit storage, email volume and request rates.", "Decisions.md"],
            ["C10", "Every schema change is a reversible migration; the API contract in openapi-v1.json is checked in CI.", "backend/migrations, tests/test_openapi_contract.py"],
            ["C11", "Identity uses Supabase Auth through the API; the browser never calls Supabase. This deviates from Platform Foundation 8.1 "
                    "(\"Supabase Auth shall not be used\"); the owner's decision is recorded and the Platform Foundation amendment is pending.",
             "Decisions.md, 27 Oct 2026; Platform-Foundation.md 8.1"],
        ],
        [1.0, 11.2, 4.3], caption="Constraints", size=8.8,
    )
    doc.h2("2.6 Assumptions and dependencies")
    doc.table(
        ["ID", "Assumption or dependency", "If it fails"],
        [
            ["A1", "Supabase Auth, PostgreSQL and Storage are available (Supabase Auth: see C11).", "Sign-in, reviews or media are unavailable; the API answers SERVICE_UNAVAILABLE and readiness reports 503."],
            ["A2", "Cloudflare Turnstile is reachable for guest submissions.", "New guest reviews cannot be submitted; reading and receipt operations continue."],
            ["A3", "An email provider is configured and delivers verification, password reset and notification email (AUTH_EMAIL_DELIVERY=app).",
             "New members cannot verify their email and reset links do not arrive. Notification email is retried (1 min, 5 min, 30 min, 2 h) "
             "and then marked failed; the in-app notification still exists."],
            ["A4", "Users have a Chromium-based or modern browser.", "Some features degrade; documented limits apply."],
            ["A5", "At least two trained moderators are available (a decision on appeal needs a second person).", "Appeals wait in the queue."],
            ["A6", "Destination data is researched, sourced and dated by the team.", "Advisories become stale or expired and are labelled so."],
            ["A7", "Redis is available for counters.", "Visit and event counters lose data; reviews are not affected."],
            ["A8", "Users consent to the moderation and retention notice shown with a submission.", "No submission is accepted without a consent version."],
        ],
        [1.0, 7.5, 8.0], caption="Assumptions and dependencies", size=8.8,
    )

    doc.h2("2.7 Hosting, costs and third-party risk")
    doc.table(
        ["Service", "Used for", "Plan on 31 October 2026", "Monthly cost"],
        [
            ["Railway", "API container (interim deployment, not in the approved plan)", "Account plan not recorded in the repository", "To confirm"],
            ["Render (render.yaml)", "Prepared blueprint for the API in Singapore", "plan: free", "BDT 0"],
            ["Vercel", "Public PWA (interim) and the private ops site", "Shared team account", "To confirm"],
            ["Supabase", "PostgreSQL, Auth and Storage", "Projects abhijatri-staging and abhijatri-prod", "To confirm"],
            ["Upstash Redis", "Visit and event counters", "Not recorded", "To confirm"],
            ["Brevo or Gmail API", "Account and notification email", "Brevo free tier (300 emails a day); Gmail API about 500 a day", "BDT 0"],
            ["Cloudflare Turnstile", "Bot check for guest submissions", "Free", "BDT 0"],
        ],
        [3.2, 5.2, 5.0, 3.1], caption="Hosting and services (sources: render.yaml, Docs/Architecture.md, Docs/Decisions.md)", size=8.4,
    )
    doc.p("The proposal's planning ceiling is BDT 6,000 for the semester (constraint C4). The repository does not record the paid "
          "plans, if any; the team should fill in the \"To confirm\" cells from the account bills before submission.")
    doc.table(
        ["Risk", "Likelihood", "Impact", "Mitigation"],
        [
            ["A free tier ends, is paused for inactivity, or hits its limit (Supabase, Upstash, Vercel, Railway, email)", "Medium", "High",
             "Keep the database portable (plain PostgreSQL migrations); readiness check reports 503; email has two providers; "
             "document a paid fallback within the BDT 6,000 ceiling."],
            ["Supabase Auth outage or policy change", "Low", "High", "Sessions continue until expiry; the API proxies Auth, so a swap "
             "touches only the auth module."],
            ["Email provider blocks or delays mail", "Medium", "Medium", "Switch EMAIL_PROVIDER (Brevo, Gmail API, SMTP, Resend); "
             "retries; in-app notifications do not depend on email."],
            ["Cloudflare Turnstile unavailable", "Low", "Medium", "Guest submissions pause; members and reading are unaffected; "
             "GUEST_WRITES_PAUSED switch."],
        ],
        [5.0, 1.8, 1.6, 8.1], caption="Third-party dependency risk", size=8.4,
    )

    # ---- 4.3
    doc.h1("3. Specific requirements")
    doc.h2("3.1 External interface requirements")
    doc.h3("3.1.1 User interfaces")
    doc.table(
        ["Application", "Main screens", "Notes"],
        [
            ["Public PWA (frontend/)", "Landing, guest entry, register, verify email, sign in, forgot and reset password, overview, destinations and detail, reviews (form, receipt status, withdraw), account verification, appeals, notifications; prototype: planner, offline packs, saved trips", "Bangla first; English selectable; keyboard and screen-reader support are required; prototype screens must be labelled"],
            ["Staff app (staff/)", "Sign-in with TOTP, task queue with lease, decision form, media, appeals, reports, enforcement, verification cases, staff, audit, inbox, notifications", "Never part of the public build; staff routes answer 404 to non-staff"],
            ["Ops app (ops/)", "Health, content, traffic, members, notifications, queue and reviews panels", "Read-only; token in a header; separate deployment"],
        ],
        [3.2, 8.5, 4.8], caption="User interfaces", size=8.6,
    )
    doc.h3("3.1.2 Software interface: the API")
    doc.p("The contract is `Docs/api/openapi-v1.json` (checked against the code by a test) and `Docs/api/API.md`. All errors use one body, `{ error: { code, message, request_id, field_errors } }`, with Bangla and English messages. "
          "Signed-in writes need a CSRF token; guest operations send the receipt in the JSON body only; lists use opaque cursors. "
          "The /staff group is legacy and is not part of the requirements.")
    doc.table(["Group", "Operations", "Purpose"], api_groups(), [3.2, 2.3, 11.0], caption="API operations by group (from openapi-v1.json)", size=8.6)
    doc.h3("3.1.3 Third-party services")
    doc.table(
        ["Service", "Purpose", "Data exchanged", "When unavailable"],
        [
            ["Supabase Auth", "Identity, passwords, TOTP (constraint C11)", "Credentials, tokens, one-time tokens, user id", "Sign-in and registration fail with a clear error; existing sessions continue until expiry"],
            ["Supabase PostgreSQL", "System of record", "All application tables", "Readiness 503; the API does not accept writes"],
            ["Supabase Storage", "Private media and evidence", "Signed links, processed files", "Upload answers SERVICE_UNAVAILABLE with a Retry-After header"],
            ["Cloudflare Turnstile", "Bot check on guest submission", "One-time token", "Guest submissions refused; other features unaffected"],
            ["Email provider (SMTP, Gmail, Brevo, Resend)", "Verification, password reset and notification email", "Email address, message, delivery status webhooks",
             "Registration and password reset cannot complete; notification email is retried, then marked failed; alert raised after a threshold"],
            ["Upstash Redis", "Visit and event counters", "Counter increments and totals", "Counters lost; core flows unaffected"],
        ],
        [3.4, 3.4, 4.0, 5.7], caption="Third-party services", size=8.6,
    )
    doc.h3("3.1.4 Hardware and communications interfaces")
    doc.bullets([
        "No special hardware. Target device: a low-end Android phone on a slow mobile network; the proposal's measure is usable core text within 5 seconds on a throttled Fast 3G profile.",
        "All traffic uses HTTPS; cookies are HttpOnly and Secure in production; CORS allows only the configured origins.",
    ])

    # ---- 4.4
    doc.h2("3.2 System features: use case model and requirement status")
    doc.p("The use case diagram shows the system as built, with the six user classes of section 2.3. Each use case is marked built, "
          "prototype or planned. It replaces the proposal's diagram, which used different actor names and showed unbuilt administration "
          "features without a marker.")
    doc.figure(HERE / "usecase-asbuilt.png", "Use case diagram of Abhijatri as built (31 October 2026)", 16.0, 21.0)
    doc.p("Status of each functional requirement as of 31 October 2026, from the repository (Docs/Implemented.md, Docs/Backend-Implemented.md, Docs/Frontend-Implemented.md and the tests):")
    status = [
        ["FR01", "Destination catalogue", "Implemented", "Five destinations with sourced, dated content; R01 content review pending"],
        ["FR02", "Language selection", "Implemented", "Bangla default, English selectable; no test of the language switch was found"],
        ["FR03", "Account lifecycle", "Partly", "Register, verify, sign in, reset, sign out built; account deletion request not found in the API"],
        ["FR04", "Structured review", "Implemented", "Guest and member; seven category ratings; the local offline draft is not built (see FR12)"],
        ["FR05", "Review moderation", "Implemented", "Publish, reject, hide, restore, request changes; audit and actor recorded; DELETED state defined but not used"],
        ["FR06", "Review reporting", "Implemented (member)", "Member reports with duplicate control; anonymous public reports planned"],
        ["FR07", "Destination rating", "Implemented", "Guest Feedback average; Bayesian Community Rating from eligible Verified Member reviews, hidden below the threshold"],
        ["FR08", "Cost planner", "Prototype", "Screen only; no estimator logic or API"],
        ["FR09", "Pricing units", "Not implemented", "Depends on the planner and a price catalogue"],
        ["FR10", "Offline pack", "Prototype", "No service worker, manifest or IndexedDB yet"],
        ["FR11", "Saved trip brief", "Prototype", "Screen only"],
        ["FR12", "Offline review draft", "Not implemented", "Draft store (IndexedDB) planned for R15"],
        ["FR13", "Retry-safe submission", "Partly", "Permanent draft id uniqueness and receipt recovery built and tested; Idempotency-Key replay is built for staff decisions, planned for other writes"],
        ["FR14", "Pack update", "Not implemented", "Depends on FR10"],
        ["FR15", "Advisory freshness", "Implemented", "Current, stale, expired and not-yet-effective, on the Dhaka date"],
        ["FR16", "Administration", "Partly", "Staff roles, audit log, notification administration, media decisions built; staff editing of destination content not built"],
        ["FR17", "Storage control", "Not implemented", "Depends on FR10"],
    ]
    fills = {}
    for i, r in enumerate(status):
        fills[(i, 2)] = GREEN if r[2].startswith("Implemented") else (AMBER if r[2] in ("Partly", "Prototype") else RED)
    doc.table(["ID", "Requirement", "Status", "Evidence or note"], status, [1.2, 3.6, 2.8, 8.9], caption="Functional requirement status", size=8.6, fills=fills)
    done = sum(1 for r in status if r[2].startswith("Implemented"))
    doc.p(f"Summary: {done} implemented, {sum(1 for r in status if r[2] == 'Partly')} partly implemented, {sum(1 for r in status if r[2] == 'Prototype')} prototypes and {sum(1 for r in status if r[2] == 'Not implemented')} not implemented, of {len(status)}. "
          "The offline group (FR10, FR11, FR12, FR14, FR17) and the estimator (FR08, FR09) are the main remaining work.")

    # ---- 4.5
    doc.h2("3.3 Data requirements")
    doc.p("The database has more than 35 tables; the diagram shows the ones needed to understand reviews, moderation and notifications. "
          "Line ends use crow's-foot notation (a bar is one, a circle is optional, a fork is many). Every public table has row-level "
          "security enabled, and the application connects as the owner role.")
    doc.figure(HERE / "erd.png", "Entity-relationship diagram of the main tables", 16.6, 22.0)
    doc.table(
        ["Data", "Where kept", "Retention or protection"],
        [
            ["Review text and ratings", "reviews, review_revisions, review_category_ratings", "Kept while published; revisions append-only. Tombstoning rejected content after 30 days (Review.md) is not built yet"],
            ["Guest receipt and scope secret", "Browser only; server holds keyed digests (review_receipts, reviews.guest_scope_hash)", "Raw values never stored or logged; receipts never reissued"],
            ["Account identity", "users, user_roles; passwords and TOTP in Supabase Auth", "Passwords never in the application database"],
            ["Verification evidence", "Private storage; verification_cases, verification_evidence", "Files erased 24 hours after approval; files and the case row erased 30 days after rejection or withdrawal; nothing erased while an appeal is open"],
            ["Photos and videos", "review_media; private bucket", "Uploads not completed within 24 hours are purged; re-encoded images have EXIF and GPS removed"],
            ["Notifications", "notifications and delivery tables", "Standard items 90 days; critical items 24 months; open appeals preserved"],
            ["Outbox events", "outbox_events", "Processed rows removed after 30 days"],
            ["Rate-limit counters", "rate_limit_buckets", "Old windows purged automatically"],
            ["Audit events", "audit_events", "Append-only; the application role cannot update or delete"],
        ],
        [3.6, 6.5, 6.4], caption="Data kept and how it is protected", size=8.6,
    )

    # ---- 4.6
    doc.h2("3.4 Use case specifications")
    doc.p("Six core use cases are specified in full. Each maps to a package in the use case model and to a flow in the data flow diagrams.")

    def uc(title, rows):
        doc.table(["Field", "Specification"], rows, [3.2, 13.3], caption=title, size=8.4, bold_first_col=True)

    uc("UC-01 Submit a review", [
        ["Actors", "Guest or Member (primary); Cloudflare Turnstile (secondary)"],
        ["Trigger", "The user finishes the structured review form and presses Submit."],
        ["Preconditions", "A published destination exists. A Guest has a generated receipt, scope secret and draft id. A Member is signed in with a CSRF token."],
        ["Main flow", "1. The client sends the review (title, note, overall rating, optional category ratings, language, traveller type, comfort tier, visit month, consent version).\n2. The server checks the schema and receipt format.\n3. If the draft id already exists with the same receipt, it returns the existing review (not counted against rate limits).\n4. For a Guest it verifies the Turnstile token and durable rate limits and pending ceilings.\n5. It creates the review (PENDING), first revision, category ratings, receipt digest, moderation task and outbox event in one transaction.\n6. It answers 201 with review id and status."],
        ["Alternative flows", "A member who already has an active review for the same destination and month gets MEMBER_REVIEW_EXISTS. A different receipt on an existing draft gets DRAFT_ALREADY_SUBMITTED."],
        ["Exceptions", "Turnstile failure (CHALLENGE_FAILED), rate limit (RATE_LIMITED with Retry-After), guest writes paused (GUEST_WRITES_PAUSED), validation errors with field codes."],
        ["Postconditions", "One PENDING review is queued for moderation; nothing is counted or public."],
        ["Requirements", "FR04, FR13, FR05"],
        ["API and tests", "POST /reviews/guest, POST /reviews/member; tests/test_review_postgres.py, test_receipts.py, test_abuse.py, test_category_ratings.py"],
    ])
    uc("UC-02 Edit an unpublished review", [
        ["Actors", "Guest (with receipt) or Member (owner)"],
        ["Trigger", "The author changes a pending review or answers a moderator's request for changes."],
        ["Preconditions", "The review is PENDING or CHANGES_REQUESTED and the author knows its current version."],
        ["Main flow", "1. The client sends PATCH /reviews/{id}/pending with expected_version and only the changed fields (a Guest adds the receipt; a Member uses the session and CSRF token).\n2. The server proves ownership (receipt digest or author id).\n3. It checks the state and the version.\n4. It validates and merges the changes with the current revision.\n5. It writes a new revision, marks the old one SUPERSEDED, sets the review to PENDING and re-queues the moderation task.\n6. It answers 200 with the new version and revision number."],
        ["Alternative flows", "Moving a member review onto a month already reviewed gives MEMBER_REVIEW_EXISTS."],
        ["Exceptions", "Wrong receipt (RECEIPT_NOT_FOUND, counted toward a progressive block); another person's review (404); any other state (INVALID_TRANSITION); stale version (REVIEW_VERSION_CONFLICT)."],
        ["Postconditions", "A new revision exists; the review is hidden and uncounted until a moderator publishes it."],
        ["Requirements", "FR04, FR05; Review.md 5.2"],
        ["API and tests", "PATCH /reviews/{id}/pending; tests/test_review_crud.py (member and guest edit, refused states, month collision, request-changes round trip)"],
    ])
    uc("UC-03 Moderate a review", [
        ["Actors", "Moderator or Superadmin"],
        ["Trigger", "A moderator opens the queue and takes a pending review."],
        ["Preconditions", "Staff signed in with TOTP; a moderation task exists; the moderator is not the author."],
        ["Main flow", "1. Claim the task and receive a lease token (300 seconds; heartbeat extends it).\n2. Read the content and any media.\n3. Send the decision (PUBLISH, REJECT, REQUEST_CHANGES, HIDE, RESTORE) with the task id, lease token, the review's version and a reason code.\n4. In one transaction the server changes the status, updates rating totals exactly once, decides media, writes the moderation action, an audit event and an outbox event, and completes the task.\n5. The worker later notifies a member author in the inbox and by email; a Guest author has no account and sees the decision through the receipt status."],
        ["Alternative flows", "A decision can be replayed with the same Idempotency-Key and returns the stored result."],
        ["Exceptions", "Stale version (REVIEW_VERSION_CONFLICT); lost lease (LEASE_LOST); impossible move (TRANSITION_NOT_ALLOWED); own review (SELF_MODERATION_FORBIDDEN)."],
        ["Postconditions", "Status and aggregates are consistent; the decision is auditable; a member author is notified; a Guest sees the outcome in the receipt status."],
        ["Requirements", "FR05, FR07, FR16"],
        ["API and tests", "POST /admin/tasks/{id}/claim, POST /admin/submissions/{id}/moderation-actions; tests/test_admin.py, test_review_postgres.py, test_review_crud.py"],
    ])
    uc("UC-04 Appeal a rejection", [
        ["Actors", "Member (session) or Guest (receipt); a second moderator"],
        ["Trigger", "The author sees a rejection with its reason and appeal deadline."],
        ["Preconditions", "The review is REJECTED (or HIDDEN for a member) and the 30-day window (end of day 30, Asia/Dhaka) has not closed."],
        ["Main flow", "1. The author files the appeal (member: POST /appeals; guest: POST /review-receipts/appeals with the receipt and a 20 to 2000 character statement).\n2. The server records one appeal per decision and queues an appeal task.\n3. A moderator other than the original decider claims it and decides upheld or overturned.\n4. If overturned, a rejected review returns to PENDING for a fresh review; a hidden review is restored.\n5. The author is notified (a Guest sees the outcome in the receipt status)."],
        ["Exceptions", "Window closed (APPEAL_WINDOW_CLOSED); second appeal (DUPLICATE_APPEAL); the original decider tries to decide (APPEAL_REVIEWER_NOT_INDEPENDENT)."],
        ["Postconditions", "The appeal has a final state and an audit record."],
        ["Requirements", "FR05; Review.md 4.2, 5.4"],
        ["API and tests", "POST /appeals, POST /review-receipts/appeals, POST /admin/appeals/{id}/decision; tests/test_cases.py, test_review_crud.py"],
    ])
    uc("UC-05 Estimate trip cost (prototype)", [
        ["Actors", "Guest or Member"],
        ["Trigger", "The traveller enters party size, dates, comfort tier and choices."],
        ["Intended flow", "The estimator applies source-dated prices by pricing unit (person, room, vehicle, group, day, night, meal, entry) and returns an itemised BDT range with per-person cost and a confidence label."],
        ["Status", "Prototype screen only. There is no estimator logic, price catalogue or API in the repository yet (FR08, FR09)."],
        ["Requirements", "FR08, FR09; proposal section 4 (cost planner rules and worked example)"],
        ["Verification plan", "Ten held-out trips evaluated after the price catalogue is frozen (objective O6)."],
    ])
    uc("UC-06 Download an offline pack (prototype)", [
        ["Actors", "Guest or Member"],
        ["Trigger", "The traveller chooses a destination pack to keep for airplane mode."],
        ["Intended flow", "The app downloads a versioned pack (guidance, contacts, coordinates, advisories, costs) into IndexedDB, asks for persistent storage, and later replaces it atomically after validating a newer manifest."],
        ["Status", "Prototype screen only. No service worker, manifest, IndexedDB or pack API exists yet (FR10, FR14, FR17)."],
        ["Requirements", "FR10, FR14, FR17"],
        ["Verification plan", "10 of 10 packs open in airplane mode on real devices (objective O4)."],
    ])

    # ---- 4.7
    doc.landscape()
    doc.h2("3.5 Behaviour models")
    doc.h3("3.5.1 Review lifecycle (state diagram)")
    doc.figure(HERE / "review-state.png", "Review states and the transitions the code allows", 24.5, 15.2)
    doc.portrait()
    doc.table(
        ["Event", "From", "To", "Who", "Side effects"],
        [
            ["Submit", "(new)", "PENDING", "Guest or Member", "Revision 1, receipt digest, task, outbox event"],
            ["PUBLISH", "PENDING", "PUBLISHED", "Moderator", "Rating counted once (Guest Feedback or Community Rating); category totals move; author notified"],
            ["REJECT", "PENDING", "REJECTED", "Moderator", "Public-safe reason; 30-day appeal window starts"],
            ["REQUEST_CHANGES", "PENDING", "CHANGES_REQUESTED", "Moderator", "Author notified with the reason; no rating change"],
            ["Edit", "PENDING or CHANGES_REQUESTED", "PENDING", "Author", "New revision; old one SUPERSEDED; task re-queued"],
            ["HIDE", "PUBLISHED", "HIDDEN", "Moderator", "Rating removed in the same transaction"],
            ["Enforcement takedown", "PUBLISHED", "HIDDEN", "Moderator or Superadmin (after a report)", "Rating removed; enforcement case and sanction recorded"],
            ["RESTORE", "HIDDEN", "PUBLISHED", "Moderator", "Rating added back"],
            ["Appeal overturned or enforcement lifted", "HIDDEN", "PUBLISHED", "A second moderator, or Superadmin", "Rating added back"],
            ["Withdraw", "PENDING, CHANGES_REQUESTED, PUBLISHED, REJECTED or HIDDEN", "WITHDRAWN", "Author",
             "A counted rating is removed; open tasks cancelled; repeating it on a WITHDRAWN review is a no-op"],
            ["Appeal overturned", "REJECTED", "PENDING", "A second moderator", "Back to the queue for a fresh review"],
        ],
        [2.6, 3.6, 2.9, 2.6, 4.8], caption="Transitions", size=8.4,
    )
    doc.p("The states UNDER_REVIEW and DELETED exist in the data model and are accepted by some checks, but no current code path sets them; a moderator's claim is held on the task, not on the review.")
    doc.note("**Open product decision.** The code allows an author to withdraw a review while an appeal on it is still open "
             "(services.withdraw_review checks only for WITHDRAWN and DELETED). Review.md 4.2 suggests an open appeal should block "
             "withdrawal. The product owner should decide which rule applies; this SRS records the code as it is.")

    # ---- 4.8
    doc.landscape()
    doc.h3("3.5.2 Sequence diagrams")
    doc.figure(HERE / "seq-submit-moderate.png", "A Guest submits, a moderator publishes, the Guest checks the receipt status", 24.0, 14.6)
    doc.figure(HERE / "seq-guest-edit.png", "Request changes, edit with the receipt, return to the queue", 24.0, 14.6)
    doc.portrait()
    doc.h2("3.6 Non-functional requirements")
    doc.p("Targets come from the proposal's non-functional requirements table. The one target marked \"(v1.1)\" is new in this SRS "
          "because the proposal gave no availability figure; the team should confirm it. Evidence is what the repository shows on 31 October 2026.")
    nf = [
        ["Performance", "Usable core text within 5 s on a throttled Fast 3G profile on the target Android device; a downloaded pack opens "
                        "within 2 s; catalogue, review and estimator APIs under 2 s at the 95th percentile in a 50-user load test", "Not measured. Lists are paginated (default 20, maximum 50) and public responses are cached "
                        "for 60 seconds; no timing or load test is in the repository.", "Gap"],
        ["Security and access control", "Server-side authority, CSRF, TOTP (AAL2) for staff, role checks, audit, rate limits, Turnstile, RLS",
         "Built and tested: tests/test_auth.py, test_admin.py, test_rls.py, test_abuse.py; dependency audit clean; committed-secret check in CI", "Met"],
        ["Reliability and availability", "No duplicate on an identical retry; an interrupted pack update keeps the last pack; one backup and one restore test for the "
                                         "pilot; 99 % monthly availability of the API during the pilot (v1.1)",
         "Retry safety built and tested; outbox is at-least-once and idempotent; pack update not applicable yet; no restore test or uptime measurement recorded", "Partly"],
        ["Scalability", "Stateless API, indexes, pagination, bounded queries; semester load target of 50 concurrent virtual users", "Built; no load test", "Partly"],
        ["Usability and accessibility", "Applicable WCAG 2.2 AA criteria evaluated with at least eight users; Bangla default; labelled forms; keyboard "
                                        "access; Bengali conjuncts render correctly",
         "Bilingual UI built; a real-Chrome end-to-end run passed 59 of 59 checks (30 Oct 2026, Docs/diagrams/e2e); QA notes list remaining "
         "accessibility items; no screen-reader or WCAG audit record", "Partly"],
        ["Maintainability", "Modular code, migrations, API docs, tests, code review",
         "502 backend tests; 95 public-app, 28 staff-app and 19 ops-app unit tests (Frontend-Implemented.md, 30 Oct 2026); lint and strict "
         "typing in CI; 18 migrations; contract tests", "Met"],
        ["Portability", "Chromium on Android, modern desktop browsers", "All three apps build; the end-to-end run used desktop Chrome; no "
                        "recorded run on a real Android device", "Partly"],
        ["Privacy", "Minimal data, consent, retention, deletion support", "Retention jobs and consent version built; account deletion request not found", "Partly"],
    ]
    fills = {(i, 3): {"Met": GREEN, "Partly": AMBER, "Gap": RED}[r[3]] for i, r in enumerate(nf)}
    doc.table(["Category", "Requirement and target", "Evidence in the repository", "Status"], nf, [3.0, 5.4, 6.6, 1.5],
              caption="Non-functional requirements: targets and evidence", size=8.2, fills=fills)

    # ---- 4.9
    doc.h1("4. Verification: requirements traceability")
    doc.table(
        ["FR", "Use case (as-built diagram)", "API operations", "Automated tests", "Status"],
        [
            ["FR01", "Browse destinations and advisories", "GET /destinations, /destinations/{id}", "test_destination_unit, test_destination_http, test_destination_postgres, test_seed_content", "Implemented"],
            ["FR02", "All use cases (language switch)", "Accept-Language on all routes", "No test of the language switch found", "Implemented"],
            ["FR03", "Register, sign in, reset password", "POST /auth/register, verify-email, login, logout, password-reset/*; GET /auth/session", "test_auth", "Partly"],
            ["FR04", "Submit a review", "POST /reviews/guest, /reviews/member; GET /review-parameters", "test_review_postgres, test_review_unit, test_category_ratings, test_receipts, test_review_crud", "Implemented"],
            ["FR05", "Moderate the review queue", "GET /admin/queue; POST /admin/tasks/{id}/claim, /admin/submissions/{id}/moderation-actions", "test_admin, test_review_postgres, test_review_crud", "Implemented"],
            ["FR06", "Report a review; Decide appeals and reports", "POST /reviews/{id}/reports; POST /admin/reports/{id}/transition", "test_admin (report flow and rules)", "Implemented (member)"],
            ["FR07", "Read published reviews and ratings; Count toward the Community Rating", "GET /destinations/{id}/reviews; rating logic in services.py", "test_review_postgres, test_destination_postgres", "Implemented"],
            ["FR08, FR09", "Estimate trip cost (prototype)", "None yet", "None yet", "Prototype / not implemented"],
            ["FR10, FR14, FR17", "Download offline pack, save trip (prototype)", "None yet", "None yet", "Prototype / not implemented"],
            ["FR11", "Download offline pack, save trip (prototype)", "None (local)", "None yet", "Prototype"],
            ["FR12", "Submit a review (offline draft not built)", "None (local)", "None yet", "Not implemented"],
            ["FR13", "Submit a review", "POST /reviews/guest (draft id), POST /reviews/member; Idempotency-Key on staff decisions", "test_review_postgres (retry deduplication), test_receipts, test_admin (idempotent decision)", "Partly"],
            ["FR15", "Browse destinations and advisories", "GET /destinations/{id} (advisory state)", "test_destination_unit (boundaries, Dhaka date)", "Implemented"],
            ["FR16", "Manage staff roles; Administer notifications; Read the audit log; Edit destination content (planned)", "GET /admin/staff, POST /admin/staff/{id}/role, GET /admin/audit-events, notification admin routes", "test_admin, test_notifications", "Partly"],
            ["R07 (review CRUD)", "Check, edit or withdraw a review; Appeal a decision", "PATCH /reviews/{id}/pending, GET /reviews/{id}, GET /reviews/mine, POST /reviews/{id}/withdraw, POST /review-receipts/appeals", "test_review_crud (16 tests)", "Implemented"],
            ["Notifications", "Read notifications, set preferences", "GET /notifications, PATCH /notifications/{id}, /notification-preferences", "test_notifications", "Implemented"],
        ],
        [1.6, 3.6, 4.7, 4.0, 2.6], caption="Traceability: requirement to use case to API to test", size=7.8,
    )
    doc.note("The as-built use case diagram includes notifications, appeals, verification, media and monitoring, which the proposal's diagram did not.")

    # ---- 4.10
    doc.h1("5. As built versus proposed")
    doc.table(
        ["Topic", "Proposal (12 October 2026)", "As built (31 October 2026)", "Action"],
        [
            ["Authentication", "Argon2id hashing and opaque server-side sessions", "Supabase Auth holds passwords and TOTP; the API verifies signed tokens and sets HttpOnly session cookies with a CSRF token", "Recorded as a deviation from Platform Foundation 8.1 (Decisions.md, 27 Oct 2026); PF 8.1 amendment pending; update the proposal's security row"],
            ["Staff security", "Role-based access", "Staff need TOTP (AAL2); superadmin needs a recent password check for role changes; every action is audited", "Add to NFR text"],
            ["Guest identity", "Guest reviews with a draft id", "Client-generated receipt, keyed digests, durable rate limits, Turnstile, public pseudonymous guest tag", "Describe in the review section"],
            ["Review lifecycle", "Published, hidden, rejected or deleted", "Adds PENDING, CHANGES_REQUESTED, WITHDRAWN, SUPERSEDED revisions, appeals and edit-while-pending", "Update FR05 and the state model"],
            ["Photos and video", "Image attachment for Verified Members", "Any signed-in member may attach up to 5 photos and 1 video; no transcoding", "Recorded in Decisions.md (27 Oct 2026); Review.md 8 and 12.3 amendment pending"],
            ["Notifications", "Not in scope", "Full outbox, inbox, email, digests and webhooks", "Add as a feature"],
            ["Observability", "Not specified", "Ops dashboard, audit log, alerts", "Add to NFR"],
            ["Hosting", "Optional short-term hosting, BDT 2,500", "API on Railway (interim; a Render free-plan blueprint is in render.yaml), PWA and ops site on Vercel, Supabase, Upstash", "Costs in section 2.7; fill in the unconfirmed plans"],
            ["Offline and PWA", "Core of the MVP", "Prototype screens only; no service worker or IndexedDB", "State the status; plan the remaining work"],
            ["Cost estimator", "Rule-based itemised estimate", "Prototype screen only", "State the status"],
            ["Booking and payment", "Demonstration only", "Not built", "Keep as demonstration or remove from the diagram"],
        ],
        [2.6, 4.3, 5.6, 4.0], caption="Proposal and implementation compared", size=8.2,
    )

    # ---- 4.11
    doc.h1("Appendix A. Data flow model")
    doc.p("The complete data flow model is in Abhijatri-DFD.docx (version 1.1): a context diagram, a level 0 diagram with seven processes "
          "on six sheets, level 1 diagrams for processes 3.0 to 7.0 and level 2 diagrams for 4.3 (edit) and 6.2 (decide). A script checks "
          "the rules, the balancing between levels by flow name, and that every data store is written and read.")
    doc.table(
        ["Process", "Name", "Realises (section 2.2)"],
        [["1.0", "Browse destinations and advice", "Destination guidance"], ["2.0", "Plan trips offline (prototype)", "Trip planning"],
         ["3.0", "Authenticate and manage accounts", "Accounts"], ["4.0", "Submit and manage reviews", "Reviews"],
         ["5.0", "Notify members and staff", "Notifications"], ["6.0", "Moderate, verify and rate", "Moderation"],
         ["7.0", "Monitor, audit and retain data", "Operations"]],
        [2.0, 7.5, 7.0], caption="Level 0 processes",
    )
    doc.h1("Appendix B. Revision history and approval")
    doc.table(
        ["Version", "Date", "Author", "Change"],
        [
            ["0.1", "12 October 2026", "Team ChoturMatra", "Project proposal"],
            ["1.0", "30 October 2026", "Team ChoturMatra", "SRS completion sections, coverage check, traceability"],
            ["1.1", "31 October 2026", "Team ChoturMatra", "Standalone SRS in IEEE 29148 order; as-built use case diagram; corrected state, "
                                                          "sequence and ER diagrams; NFR targets; costs and third-party risk; Supabase Auth deviation cited"],
        ],
        [2.0, 3.4, 4.5, 6.6], caption="Revision history",
    )
    doc.table(
        ["Role", "Name", "Signature", "Date"],
        [
            ["Project leader", "Shahriar Islam", "", ""],
            ["Frontend and offline", "Abdullah Bin Sorwar Choudhury", "", ""],
            ["Backend and data", "Syed Muhtasim Alam", "", ""],
            ["Quality assurance", "Md. Irfan Iqbal", "", ""],
            ["Course instructor", "(to be completed at signing)", "", ""],
        ],
        [4.0, 6.0, 3.8, 2.7], caption="Approval",
    )
    doc.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    main()
