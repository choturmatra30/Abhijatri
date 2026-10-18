# Abhijatri Architecture

**Status:** Current implementation snapshot updated 16 October 2026. The target architecture and Gate A requirements are authoritative in `Docs/Platform-Foundation.md`; behavioural rules live in `Features/Review.md`, security controls in `Docs/Security.md`, and build-time choices in `Docs/Decisions.md`.

## 1. System flow

```text
Public PWA at app.<owned-domain> and staff UI at admin.<owned-domain>
    |  HTTPS, JSON, explicit CORS origin
    v
FastAPI API at api.<owned-domain> (Render web service, Docker, non-root)
    |  SQLAlchemy 2 / Psycopg 3, TLS, session pooler
    v
Supabase-managed PostgreSQL (schema app; source of truth)
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

1. The current `POST /reviews/guest` stores a `PENDING` review and first revision, deduplicated by permanent `client_draft_id` and hashed Guest scope. It currently returns a server-issued receipt. Platform Foundation 13 replaces this with a client-generated, never-reissued receipt and domain-separated keyed digest before frontend integration.
2. A moderator (`/staff/moderation/reviews/{id}/decisions`) sends `expected_version` and a decision. The service locks the review and its destination aggregate row, checks `version`, applies the `counted_rating` delta exactly once, writes an audit decision, and commits.
3. Public feed `GET /destinations/{id}/reviews` returns only `PUBLISHED` reviews ordered by `(published_at, id)` with an opaque cursor, plus the Guest Feedback aggregate.
4. The current exchange endpoint is deprecated. The target contract uses receipt-scoped POST bodies for status, withdrawal, appeal, and pending edits without creating a receipt session.

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
GitHub PR -> CI (lint, unit, PostgreSQL integration, migration, security, contract and build checks)
          -> protected environment approval
          -> migration job against the selected commit
          -> API deploy and readiness verification
          -> public static build and verification
          -> staff static build and verification
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
| `MIGRATION_DATABASE_URL` | migration workflow only | Never present in the Render runtime environment. |
| `TEST_DATABASE_URL` | tests | Must name a database ending `_test`. |
| Receipt and scope HMAC keyring | yes | Versioned keys with separate context labels; raw keys are never committed. |
| `CORS_ALLOWED_ORIGINS` | yes (prod) | Comma-separated explicit origins. |
| `LOG_LEVEL` | no | Default `INFO`; never logs secrets. |
| `DOCS_ENABLED` | no | Defaults on outside production. |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE` | no | Pool tuning for Supabase connection limits. |

### Deployed environments (fill in; never record secrets here)

| Environment | API URL | Database project | Updated |
|---|---|---|---|
| Staging | `https://api.<owned-domain>` | Supabase `abhijatri-staging` | |
| Production or pilot | `https://api.<owned-domain>` | Supabase `abhijatri-prod` | |

## 6. Trust boundaries

Public internet -> Render edge (TLS) -> API container -> Supabase over TLS. Secrets are injected through Render's dashboard, never committed. CI has no production credentials. Supabase's Data API and anon key are not part of the architecture.

## 7. Authentication boundary

| Actor | Credential | Transport | Reaches | Status |
|---|---|---|---|---|
| Guest | Guest scope secret and client-generated receipt; domain-separated keyed digests stored | Request body, never cookie or URL | Guest submission and receipt-scoped POST operations | Target; current server-issued exchange flow is scheduled for replacement |
| Member | Server-side session, `__Host-` HttpOnly Secure SameSite cookie, CSRF token | Cookie | Member review and account routes | Planned (R04) |
| Staff | Separate cookie name and scope, MFA, short lifetime, `can(actor, action, resource)` per request | Cookie | `/staff/*` | Test header in dev/test only; 501 in production |

Rules: Guest and Member credentials are different cookie names and scopes; a Verified Member badge never grants staff authority; staff routes are authorised server-side even if the URL is known; private responses carry `Cache-Control: no-store`.

## 8. Offline boundary

| Data | Offline treatment |
|---|---|
| Public destination pages, advisories, contacts, pack manifest | Cacheable by the service worker and stored in IndexedDB with version and generated date. |
| Published review snapshot | Stored with its age; refreshed on reconnect; an over-age snapshot is not presented as current (maximum age is an open decision, Decisions.md Step 8). |
| Review text drafts | IndexedDB only; user can delete per draft or clear all. An unsent Guest draft includes its receipt until acknowledgement. |
| Submitted-review receipts, account, staff and moderation responses | Never cached by the service worker; submitted-review receipts are removed from IndexedDB under Platform Foundation 13.5. |
| Reconnect submission | Re-sent with the same `client_draft_id`; the server returns the existing review instead of a duplicate. |
| Published-review edits | Online only (MVP uses withdraw and resubmit). |

## 9. Resolved boundary decisions

1. Cookie and domain topology is fixed by Platform Foundation 5.
2. Offline snapshot age defaults to seven days until the Step 8 measurement records a replacement.
3. Receipt custody is fixed by Platform Foundation 13.5.
4. The structured error contract is fixed by Platform Foundation 12.3.
5. Trusted client-address derivation remains a Gate A deployment test. Gate B is blocked if the provider chain cannot be verified.

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

### 10.2 Modular API Architecture (`src/api/`)

The frontend network and data layer is organized into isolated, domain-focused API modules under `src/api/`:

| Module File | Scope & Exported Members | Architectural Contract |
|---|---|---|
| `src/api/client.ts` | `API_BASE_URL`, `apiRequest<T>()`, `ApiError`, `ApiErrorResponse` | Base HTTP client managing base URL resolution (`VITE_API_BASE_URL`), JSON headers, query serialization, and structured error mapping (`{code, message, details}`) per Platform Foundation 12.3. |
| `src/api/health.ts` | `checkBackendHealth(customUrl?: string)` | Diagnostic health runner checking backend liveness (`GET /api/v1/health`) and database readiness probe (`GET /api/v1/health/ready` testing `SELECT 1`). |
| `src/api/destinations.ts` | `SEEDED_DESTINATIONS`, `getSeededDestinations()`, `getDestinationById(id)` | Seeded destination profiles (Cox's Bazar, Sajek, Sylhet, Sundarbans, Bandarban) satisfying Semester Scope O2 and Proposal Section 1. |
| `src/api/index.ts` | Barrel export (`* from './client'`, `'./health'`, `'./destinations'`) | Unified entrypoint for cleaner imports across UI pages and widgets (`import { ... } from '../api'`). |

