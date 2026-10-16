# Abhijatri Architecture

**Status:** Current as of 15 October 2026 (Gantt F02/F06). Behavioural rules live in `Features/Review.md`; security controls in `Docs/Security.md`; build-time choices in `Docs/Decisions.md`.

## 1. System flow

```text
React PWA (offline-ready, IndexedDB drafts)
    |  HTTPS, JSON, explicit CORS origin
    v
FastAPI backend (Render web service, Docker, non-root)
    |  SQLAlchemy 2 / Psycopg 3, TLS, session pooler
    v
Supabase-managed PostgreSQL (plain Postgres; source of truth)
```

- The PWA talks **only** to the FastAPI API. It holds no Supabase key and never calls Supabase directly (no Supabase Auth, Data API, or client SDK).
- All authorisation, moderation, receipt checks and rating arithmetic run on the server.
- Redis, CDN and the media pipeline are deferred (Decisions.md, Scope control).

## 2. Backend structure (modular monolith)

| Module | Responsibility |
|---|---|
| `app/main.py` | App factory: CORS allow-list, logging, docs toggle, router. |
| `app/api.py` | HTTP layer under `/api/v1`: validation, staff dependency, error mapping (404/403/409), transaction commit/rollback. |
| `app/services.py` | Domain rules: Guest submission, receipt hashing (HMAC-SHA-256 with pepper), moderation, withdrawal, locked rating transitions, cursor encoding. |
| `app/models.py` | SQLAlchemy models and DB constraints (enums, partial unique indexes, rating checks). |
| `app/schemas.py` | Pydantic request/response contracts. |
| `app/config.py` | Typed settings and production fail-closed guard. |
| `app/db.py` | Engine, pooled sessions, `get_session` dependency. |
| `migrations/` | Alembic; the only schema-change path. |

Dependency direction: `api -> services -> models -> db`. Endpoints never perform rating arithmetic.

## 3. Core flow: submit -> moderate -> publish -> aggregate

1. `POST /reviews/guest` stores a `PENDING` review and first revision, deduplicated by a permanent `client_draft_id` + hashed Guest scope; returns a one-time receipt token (only its HMAC is stored).
2. A moderator (`/staff/moderation/reviews/{id}/decisions`) sends `expected_version` and a decision. The service locks the review and its destination aggregate row, checks `version`, applies the `counted_rating` delta exactly once, writes an audit decision, and commits.
3. Public feed `GET /destinations/{id}/reviews` returns only `PUBLISHED` reviews ordered by `(published_at, id)` with an opaque cursor, plus the Guest Feedback aggregate.
4. Receipt holders can check status and withdraw (`/review-receipts/exchange`, `/reviews/{id}/withdraw`); withdrawal subtracts the counted rating in the same transaction.

## 4. API surface today

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /api/v1/health` | none | Liveness; used by Render. |
| `GET /api/v1/health/ready` | none | Runs `SELECT 1`; 503 if the database is unreachable. |
| `POST /api/v1/reviews/guest` | Guest scope secret | 201 + receipt. |
| `GET /api/v1/destinations/{id}/reviews` | none | Public, paginated. |
| `POST /api/v1/review-receipts/exchange` | receipt token | Status. |
| `POST /api/v1/reviews/{id}/withdraw` | receipt token | Version-checked. |
| `GET /api/v1/staff/moderation/reviews` | staff | 501 in production until R04. |
| `POST /api/v1/staff/moderation/reviews/{id}/decisions` | staff | Version-checked. |
| `PUT /api/v1/staff/moderation/reviews/{id}/conflict` | staff | Locked rating transition. |

Planned endpoints (member reviews, reports, appeals, verification, roles) are listed in `Features/Review.md` section 9.2.

## 5. Delivery and environments

```text
GitHub PR -> CI (lint, unit, PostgreSQL integration, migration check, audit, secret scan, image build)
          -> merge to main -> Render deploy (only after checks pass)
          -> container start: alembic upgrade head -> uvicorn -> Supabase (session pooler)
```

| Environment | Database | `APP_ENV` | Staff identity |
|---|---|---|---|
| Local | Docker Compose Postgres 17 | development | `X-Test-Staff-Id` header |
| CI | Postgres service container (`abhijatri_test`) | test | test header |
| Shared dev / demo | Supabase project (separate per environment) | production | disabled (501) until R04 |

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `APP_ENV` | yes | `development`, `test`, or `production`; production enables the fail-closed guard. |
| `DATABASE_URL` | yes | Runtime connection; `postgres://` is normalised to `postgresql+psycopg://`; needs `sslmode=require` for remote hosts. |
| `MIGRATION_DATABASE_URL` | no | Alembic override (future migrator role). |
| `TEST_DATABASE_URL` | tests | Must name a database ending `_test`. |
| `RECEIPT_PEPPER` | yes | At least 32 random characters; rotating it invalidates existing receipts. |
| `RECEIPT_SESSION_MINUTES` | no | Receipt session lifetime (default 15). |
| `CORS_ALLOWED_ORIGINS` | yes (prod) | Comma-separated explicit origins. |
| `LOG_LEVEL` | no | Default `INFO`; never logs secrets. |
| `DOCS_ENABLED` | no | Defaults on outside production. |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE` | no | Pool tuning for Supabase connection limits. |

### Deployed environments (fill in; never record secrets here)

| Environment | API URL | Database project | Updated |
|---|---|---|---|
| Shared dev / demo | `https://<service>.onrender.com` | Supabase `abhijatri-dev` (Singapore) | |

## 6. Trust boundaries

Public internet -> Render edge (TLS) -> API container -> Supabase over TLS. Secrets are injected through Render's dashboard, never committed. CI has no production credentials. Supabase's Data API and anon key are not part of the architecture.

## 7. Authentication boundary

| Actor | Credential | Transport | Reaches | Status |
|---|---|---|---|---|
| Guest | Guest scope secret (submission) and receipt token (status, withdraw); only HMAC digests stored | Request body, never cookie or URL | `/reviews/guest`, `/review-receipts/exchange`, `/reviews/{id}/withdraw` | Implemented |
| Member | Server-side session, `__Host-` HttpOnly Secure SameSite cookie, CSRF token | Cookie | Member review and account routes | Planned (R04) |
| Staff | Separate cookie name and scope, MFA, short lifetime, `can(actor, action, resource)` per request | Cookie | `/staff/*` | Test header in dev/test only; 501 in production |

Rules: Guest and Member credentials are different cookie names and scopes; a Verified Member badge never grants staff authority; staff routes are authorised server-side even if the URL is known; private responses carry `Cache-Control: no-store`.

## 8. Offline boundary

| Data | Offline treatment |
|---|---|
| Public destination pages, advisories, contacts, pack manifest | Cacheable by the service worker and stored in IndexedDB with version and generated date. |
| Published review snapshot | Stored with its age; refreshed on reconnect; an over-age snapshot is not presented as current (maximum age is an open decision, Decisions.md Step 8). |
| Review text drafts | IndexedDB only; user can delete per draft or clear all; no receipt secret, verification evidence or contacts. |
| Receipts, account, staff and moderation responses | Never cached or stored by the PWA. |
| Reconnect submission | Re-sent with the same `client_draft_id`; the server returns the existing review instead of a duplicate. |
| Published-review edits | Online only (MVP uses withdraw and resubmit). |

## 9. Open boundary questions (to settle with Abdullah before R04 and R13)

1. Cookie domain layout: same-site API origin versus cross-site API with `SameSite=None`. Same-site is preferred to keep CSRF simple.
2. Maximum age of an offline review snapshot and the refresh trigger.
3. Where the frontend stores the receipt secret (user-held code versus browser storage), given the "no receipt secret in IndexedDB" rule.
4. Structured error codes (`{code, message, details}`) needed by the UI before H04.

## 10. Frontend Architecture (React PWA)

```text
Browser (Vite + React 18 + TypeScript)
  ├── Context Layer: LanguageContext (Bangla default / English), ThemeContext (Sage / Neon)
  ├── Route Layer: React Router v6 (/overview, /destinations, /destinations/:id, /planner, /offline-packs, /trips, /reviews, /health)
  ├── Styling: Tailwind CSS + global.css (Design tokens: Hind Siliguri, Noto Serif Bengali, Inter -0.06em)
  ├── Cache Layer: IndexedDB (Dexie.js) for downloaded travel packs and offline drafts
  └── API Client: /api/v1 proxying to FastAPI backend with real-time health diagnostic
```

### 10.1 Page URL & Component Topology

| Route | Component | Role | Traces to Requirement |
|---|---|---|---|
| `/` or `/overview` | `OverviewPage` | Dashboard, spotlight destination, live sync metrics | Proposal Section 1 |
| `/destinations` | `DestinationsPage` | 5 seeded destination profiles with category filters | O2, FR01 |
| `/destinations/:id` | `DestinationDetailPage` | Destination guide, seasonality, advisories, pack download | FR01, FR10, FR15 |
| `/planner` | `PlannerPage` | Deterministic cost estimator with shared/individual split | O3, FR08, FR09 |
| `/offline-packs` | `OfflinePacksPage` | Offline travel packs manager with IndexedDB cache | O4, FR10, FR17 |
| `/trips` | `SavedTripsPage` | Local UUID-based trip briefs and saved estimates | FR11 |
| `/reviews` | `ReviewsPage` | Guest review submission with receipt token & draft deduplication | O5, FR04, FR12, FR13 |
| `/health` | `HealthCheckPage` | Real-time diagnostic console testing `GET /api/v1/health` & readiness | Acceptance testing |

