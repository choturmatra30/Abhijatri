# Backend code map: which file does what

The backend is a FastAPI application (Python 3.12, PostgreSQL through SQLAlchemy and Alembic, Supabase Auth for sign-in, Redis for counters). Everything lives under `backend/`. This page says what each file is for, so you know where to look.

## How a request travels

```
browser / app
   |  HTTPS
   v
app/main.py            builds the app, adds security headers, CORS, request id, event counting
   |
   +- app/auth/*       who are you? (cookies, CSRF, Supabase Auth)
   +- app/abuse.py, limits.py, turnstile.py     are you a bot, or going too fast?
   v
route file             app/api.py, member_routes.py, destination_api.py, admin/routes.py, tours/routes.py ...
   |  validates input with app/schemas.py
   v
service file           app/services.py, destination_services.py, admin/actions.py, tours/service.py ...
   |  uses the tables in app/models.py, the session from app/db.py
   v
PostgreSQL             tables created by migrations/versions/*
```

Errors always come back in one shape (`app/errors.py`). Settings come from environment variables (`app/config.py`; copy `.env.example` to `.env`).

## Top level of `backend/`

| File or folder | Purpose |
|---|---|
| `app/` | All application code (below). |
| `migrations/` | Alembic database migrations: `env.py` wires Alembic to the app; `versions/0001` to `0024` build and change the tables in order. |
| `tests/` | Automated tests (pytest). File names say the area, for example `test_auth.py`, `test_tours.py`, `test_notifications.py`; `conftest.py` sets up the test database. |
| `scripts/` | One-off helpers: seed destinations, export the OpenAPI file, end-to-end smoke tests. |
| `Dockerfile` | Builds the production image: installs dependencies with `uv`, runs `alembic upgrade head`, then starts `uvicorn`. |
| `pyproject.toml`, `uv.lock` | Dependencies and tool settings (ruff, mypy, pytest). |
| `alembic.ini` | Alembic settings. |
| `.env.example` | Every environment variable with a comment. Never put real secrets in it. |
| `README.md` | Setup, checks and deploy steps. |

## `app/` core files

| File | What it does |
|---|---|
| `main.py` | Creates the FastAPI app: a logging filter that hides receipts and guest tags, security headers on every response, request id, CORS, event counters, all routers, the background scheduler and notification worker, and the staff dashboard at `/staff`. |
| `config.py` | All settings (`Settings`) read from environment variables, with checks that refuse unsafe production values. |
| `db.py` | Database engine, connection pool, per-connection timeouts, and `get_session` (one transaction per request). |
| `models.py` | The SQLAlchemy tables: destinations, users, roles, reviews, ratings, reports, moderation tasks, audit events, verification cases, sanctions and more. Tours have their own `tours/models.py`. |
| `schemas.py` | Request and response shapes (Pydantic): what the API accepts and returns. Unknown fields are rejected. |
| `errors.py` | The single error contract: error codes with their Bangla and English messages, status codes, and the handlers. |
| `api.py` | The core public routes: health checks, guest review submission, review parameters, guest visits, receipts, the public review feed, and the original staff moderation routes. |
| `services.py` | Review business logic: guest submission, receipts, duplicates, withdrawal, edits, moderation transitions, appeal deadlines. |
| `destination_api.py`, `destination_services.py` | Public destination list and full bilingual profile (guides, advisories, contacts), and the queries behind them. |
| `member_routes.py` | Signed-in member routes: reviews with photos and videos, verification, appeals, notifications. |
| `public_reports.py` | Reports and removal requests from people who are not signed in. |
| `media.py` | Photo and video handling on reviews: type checks, size limits, re-encoding, EXIF removal, quarantine and approval. |
| `storage.py` | Private Supabase Storage: evidence and media upload and signed links. |
| `eligibility.py`, `rating_integrity.py` | Which reviews count toward a destination rating, and keeping the stored totals correct. |
| `review_parameters.py`, `review_lists.py`, `reasons.py`, `report_reasons.py` | The review form rules the API publishes, lists of rejected or hidden reviews, and the allowed reason codes for decisions and reports. |
| `guest_tag.py`, `visits.py`, `redis_client.py` | The random public guest label, visit counting, and the one Redis connection. |
| `abuse.py`, `limits.py`, `turnstile.py`, `client_address.py` | Durable abuse limits and progressive blocks, rate limits per route, the Cloudflare Turnstile check, and the single place the client address is worked out. |
| `crypto.py`, `fieldcrypt.py` | Keyed digests for receipts and addresses, and encryption of sensitive fields. |
| `idempotency.py` | Replays the stored answer when a client retries a write with the same `Idempotency-Key`. |
| `audit_actions.py` | The list of every action name written to the audit log. |
| `scheduler.py` | One loop each minute for time-based work (expiries, tour transitions). |
| `sms.py` | SMS one-time codes behind a swappable gateway (the development one shows the code in Mailpit). |
| `staff_site.py` | Serves the built staff dashboard at `/staff` with its own strict headers. |

## `app/auth/`: accounts and sessions

| File | What it does |
|---|---|
| `routes.py` | Register, verify email, resend, log in, log out, forgot and reset password, change password, session info, two-step code (TOTP) enrolment and checks. |
| `gotrue.py` | Small client for Supabase Auth (create user, issue links, sign in, sessions, factors). |
| `sessions.py` | The `__Host-` session cookies and the signed-in "principal" for each request. |
| `tokens.py` | Verifies Supabase access tokens (JWTs). |
| `csrf.py` | CSRF tokens and the Origin check (it allows the API's own host, which is how `/staff` signs in). |
| `mail.py` | Builds and sends the verification, reset and "you already have an account" emails. |
| `validation.py`, `breach.py` | Input rules for sign-up and passwords, and the leaked-password check. |

## `app/admin/`: the staff side (moderators and superadmins)

| File | What it does |
|---|---|
| `routes.py` | The whole staff API under `/api/v1/admin`: work queue, claim and release, decisions, reports, audit log, staff list and roles, media, monitoring. |
| `tasks.py` | The work queue and the time-limited claim ("lease") a moderator holds on an item. |
| `actions.py` | Decisions and report handling: publish, reject, hide, restore, with version checks. |
| `cases.py` | Verification cases, enforcement and sanctions, appeals, emergency follow-ups. |
| `roles.py` | Grants and revokes the moderator and superadmin roles; protects the last superadmin. |
| `audit.py`, `idempotency.py` | The append-only audit trail and retry-safe decisions. |

## `app/verification/`: the Verified Member application

| File | What it does |
|---|---|
| `routes.py`, `service.py` | The member application (details, phone code, evidence upload, selfie liveness, submission) and its rules. |
| `images.py` | Checks evidence images: real file type, editing metadata, duplicates. |
| `geo.py`, `jobs.py` | Bangladesh districts and divisions, and scheduled verification transitions. |

## `app/tours/`: Tours and TourMates (Verified Members only)

| File | What it does |
|---|---|
| `routes.py`, `service.py` | The tour API and logic: create, publish, join with a private code, approval, automatic confirmation, leave. |
| `search.py` | Travel preferences, compatibility score, Find Tours and Find People. |
| `chat.py`, `realtime.py` | Tour chat and the WebSocket gateway. |
| `workspace.py`, `safety.py` | Itinerary and budget; emergency contact, check-ins and SOS. |
| `invitations.py`, `reports.py`, `policy.py` | Invitations, reports and blocks, and who may see or do what. |
| `admin_routes.py`, `tour_ops.py` | Staff Tour Operations: suspend, restore, break-glass chat view. |
| `models.py`, `jobs.py` | Tour tables and scheduled tour transitions. |

## `app/notify/`: notifications and email

| File | What it does |
|---|---|
| `registry.py` | The catalogue of notification types. |
| `events.py`, `worker.py`, `messages.py` | Business events go to an outbox; the worker turns them into notifications. |
| `delivery.py`, `providers.py` | Email delivery with retries, and the providers (Gmail API, Brevo, Resend, SMTP, local Mailpit). |
| `webhooks.py`, `alerts.py`, `admin_routes.py` | Provider callbacks, operational alerts, and the superadmin monitoring screens. |

## `app/planner/`

| File | Purpose |
|---|---|
| `planner/rules.py` | Frozen constants of the cost planner (units, season factors, confidence weights, thresholds, rounding, limits, rules version). Constants only; the engine arrives with E07. Specified in `Features/Cost-Planner.md`. |

## `app/offline/` and `app/ops/`

| File | What it does |
|---|---|
| `offline/packs.py`, `offline/routes.py` | Builds, versions and serves the offline destination packs and their freshness check. |
| `ops/routes.py`, `ops/auth.py`, `ops/events.py`, `ops/registry.py` | The read-only System Monitoring API behind a bearer token. |
| `ops/providers/*.py` | One module per dashboard panel: content, health, members, notifications, reviews, traffic, visitors. |

## `app/jobs/`: commands you run from a terminal

Run with `python -m app.jobs.<name>`, or use the `make` shortcuts in the repo root.

| Command | Purpose |
|---|---|
| `bootstrap_admin` | Make the first superadmin (refuses if one exists). |
| `grant_role` | Grant or revoke the moderator or superadmin role (`make moderator`, `make superadmin`). |
| `list_staff` | List who holds a staff role (`make list-staff`). |
| `reset_mfa` | Clear a staff member's authenticator so they can enrol again. |
| `gmail_authorize` | One-time Google sign-in that prints the Gmail refresh token. |
| `send_test_email` | Send one test email through the configured provider. |
| `retention` | Delete expired data on schedule. |
| `reconcile_ratings` | Nightly check that the stored rating totals are right. |

## `scripts/`

| File | Purpose |
|---|---|
| `seed_destinations.py`, `seed_destination.py`, `destination_seed_content.py` | Load the sourced destinations, guides, advisories and contacts. |
| `export_openapi.py` | Writes `Docs/api/openapi-v1.json`. |
| `e2e_smoke.py`, `e2e_cases.py` | End-to-end checks against the local Supabase stack, including real TOTP. |

## Where to look when something breaks

| Problem | Look at |
|---|---|
| Sign-up or reset email not arriving | `auth/mail.py`, `notify/providers.py`, the Railway log (a dead Gmail token shows as `gmail token 400`) |
| Cannot sign in, or cookie trouble | `auth/routes.py`, `auth/sessions.py`, `auth/csrf.py` |
| A staff action is refused | `admin/routes.py`, `admin/roles.py`, `admin/tasks.py` (the claim lease) |
| Wrong rating on a destination | `eligibility.py`, `rating_integrity.py`, `jobs/reconcile_ratings.py` |
| Too many requests (429) | `abuse.py`, `limits.py` |
| Settings refused at start-up | `config.py`, `.env.example` |
