# Backend Implementation Record

**Status:** Current as of 19 October 2026.
**Scope of this file:** what the backend actually does today, how it was built, and the evidence for each claim. The headline section is **R02**, the destination, advisory and contact data services. The sections after it record the shared backend work that was built alongside R02 because the approved API contract (`Docs/api/API.md`) required it.
**Rule:** this file claims only what the repository contains and a test or migration check demonstrates. Anything not yet built is listed under "Not implemented" and in `Docs/Implemented.md`.
**Related documents:** `Docs/api/API.md` (contract), `Docs/Schema.md` (tables), `Docs/Architecture.md` (environment variables), `Docs/Decisions.md` (decisions and reasons), `Docs/Implemented.md` (project-wide status).

---

## 1. R02: Destination, advisory and contact data services

### 1.1 Task and requirements

| Item | Value |
|---|---|
| Gantt task | R02, "Build destination, advisory and contact data services" |
| Owner | Muhtasim; 5 points; 15 to 21 October 2026 |
| Depends on | F02 (architecture, schema, API contract) and R01 (seeded destination content) |
| Unblocks | R03 (bilingual destination list and detail screens) and R14 (offline destination pack) |

Requirements the implementation answers:

| Source | Requirement | How it is met |
|---|---|---|
| Proposal FR01, O2 | A bilingual destination profile with attractions, accommodation, food, transport, local practices, contacts, coordinates, seasonality and restrictions. | `destinations` profile columns plus `destination_guide_items` and `destination_contacts`; one payload carries Bangla and English for every text field. |
| Proposal, "Advisory freshness" | Every advisory stores source, verification date, effective date and validity date. Current, stale and expired states are shown distinctly. Expired information is never presented as current. | `destination_advisories` columns; `state` computed on read; expired items hidden unless requested. |
| Platform Foundation 17 | Provenance on every maintained record: source type, reference, publisher, effective date, verification date, next review date, language, licence, researcher, reviewer. | A shared provenance mixin on all three content tables. |
| Platform Foundation 11.2 | Advisory validity and seasonal rules use the `Asia/Dhaka` calendar. | `today_in_display_tz()` evaluates every date rule on the Dhaka date. |
| Security 7.1 | Public destination pages are cacheable with a short explicit TTL; everything else is `no-store`. | `Cache-Control: public, max-age=60` plus a weak ETag on the public routes only. |
| Execution.md, row 2 | Provenance, administrative maintenance, bilingual content. | Provenance and bilingual content done; administrative maintenance is deliberately deferred (section 1.10). |

### 1.2 What was delivered

| Deliverable | Location |
|---|---|
| Models, enums, provenance mixin | `backend/app/models.py` |
| Migration | `backend/migrations/versions/0003_destination_content.py` |
| Read services | `backend/app/destination_services.py` |
| HTTP routes | `backend/app/destination_api.py` (included from `backend/app/main.py`) |
| Response schemas | `backend/app/schemas.py` |
| Settings | `backend/app/config.py`, `backend/.env.example` |
| Contract text | `Docs/api/API.md` sections 4.3, 5.12, 5.13 and 8 |
| Schema text | `Docs/Schema.md` |
| OpenAPI snapshot | `Docs/api/openapi-v1.json` |
| Tests | `backend/tests/test_destination_unit.py`, `test_destination_http.py`, `test_destination_postgres.py` |

### 1.3 Endpoints

The contract lists exactly two R02 routes, so exactly two exist. Advisories and contacts are part of the profile payload and have no routes of their own. A request for `/destinations/{id}/advisories` or `/contacts` returns `404`, and a test asserts that.

| Method and path | Purpose | Credential | Cache |
|---|---|---|---|
| `GET /api/v1/destinations` | Paged list of published destinations | none | `public, max-age=60`, weak ETag |
| `GET /api/v1/destinations/{destination_id}` | Full bilingual profile with guide items, advisories, contacts and provenance | none | `public, max-age=60`, weak ETag |

**`GET /destinations`**

| Parameter | Rule |
|---|---|
| `limit` | 1 to 50, default 20 |
| `after` | Opaque cursor, at most 300 characters |

- Only `PUBLISHED` destinations appear. Drafts and archived records are invisible.
- Order is `name_en`, then `id`. The cursor encodes the last `(name_en, id)` pair, so the next page is a tuple comparison in PostgreSQL and is stable when records are added.
- Each item carries: both names, region, summary, coordinates, `community_rating` and `guest_feedback` summaries, `active_advisory_count` and `last_updated`.
- `community_rating.average` is `null` until Verified Member ratings exist; Guest Feedback is a separate object and is never merged into it.
- `active_advisory_count` counts published advisories that are in effect and not expired on the Dhaka date.
- An undecodable cursor returns `422 {"error": {"code": "INVALID_CURSOR", ...}}`.

**`GET /destinations/{destination_id}`**

| Parameter | Rule |
|---|---|
| `include_expired` | Boolean, default `false`. Adds expired advisories, each marked `EXPIRED`. |

The response contains: identity and both-language names; region, summary, seasonality and restrictions in both languages; coordinates; rating summaries; `guide_items`; `advisories`; `contacts`; `content_licence`; `content_verified_on`; `as_of` (the Dhaka date used for all state decisions); `stale_after_days`; and `last_updated`.

- A draft, archived or unknown destination returns the same `404 NOT_FOUND`, so existence is not leaked.
- A malformed identifier returns `422 VALIDATION_FAILED` with a field error.
- `guide_items` are ordered by category, then `sort_order`, then title. `advisories` are ordered most severe first, then by `valid_until`. `contacts` are ordered by kind, then name.
- Only items with `is_published = true` are ever returned.

**Caching behaviour.** A weak ETag is the SHA-256 of the serialised response body. A request with a matching `If-None-Match` receives `304` with no body and the same `Cache-Control` and `ETag`. The ETag changes whenever any returned field changes, including `as_of`, so an advisory that becomes stale or expires at midnight in Dhaka is never served from a cache as still current. Error responses stay `no-store`.

The public review feed `GET /destinations/{destination_id}/reviews` now sends the same short public `Cache-Control` (contract section 6, item B8). Every other route keeps `Cache-Control: no-store`.

### 1.4 Data model (migration `0003_destination_content`)

**Changes to `destinations`.** All new columns are nullable, so the existing seed record, the review slice and the review tests keep working before R01 content exists.

| Column | Type | Notes |
|---|---|---|
| `region_bn`, `region_en` | `varchar(160)` | |
| `summary_bn`, `summary_en` | `text` | |
| `seasonality_bn`, `seasonality_en` | `text` | |
| `restrictions_bn`, `restrictions_en` | `text` | |
| `latitude`, `longitude` | `numeric(9,6)` | Range checks `ck_destination_latitude_range` (-90 to 90) and `ck_destination_longitude_range` (-180 to 180); `ck_destination_coordinates_pair` requires both or neither. |
| `content_licence` | `varchar(160)` | |
| `content_verified_on` | `date` | |

A partial index `ix_destinations_published_name (name_en, id) WHERE status = 'PUBLISHED'` serves the list query.

**New tables.** Each table has a UUID primary key, a foreign key to `destinations` with `ON DELETE CASCADE` (these rows are owned children), an `is_published` flag that defaults to `false`, and an `updated_at` timestamp.

| Table | Content columns | Constraints and indexes |
|---|---|---|
| `destination_guide_items` | `category` (`ATTRACTION`, `ACCOMMODATION`, `FOOD`, `TRANSPORT`, `LOCAL_PRACTICE`), `title_bn/en`, `body_bn/en`, `sort_order` | Index `ix_guide_items_destination_category (destination_id, category, sort_order)` |
| `destination_advisories` | `severity` (`INFO`, `CAUTION`, `WARNING`, `CRITICAL`), `title_bn/en`, `text_bn/en`, `valid_until`, plus `effective_on` from the provenance set | `ck_advisory_validity_window` (`valid_until >= effective_on`); index `ix_advisories_destination_valid_until (destination_id, valid_until)` |
| `destination_contacts` | `kind` (`POLICE`, `TOURIST_POLICE`, `AMBULANCE`, `FIRE`, `HOSPITAL`, `COAST_GUARD`, `FOREST_OFFICE`, `LOCAL_GUIDE`, `OTHER`), `name_bn/en`, `phone`, `address_bn/en`, `latitude`, `longitude` | `ck_contact_phone_format` (`^\+?[0-9][0-9 -]{2,30}$`, so `999` and `+880 341-62000` pass and free text fails); the same coordinate checks as `destinations`; index `ix_contacts_destination_kind` |

**Provenance columns** (the same nine on each content table, from `ProvenanceMixin` in `models.py`):

| Column | Meaning |
|---|---|
| `source_type` | Enum `OFFICIAL`, `TEAM_RESEARCH`, `OPEN_LICENCE`, `VENDOR_LICENSED`, `OTHER` |
| `source_ref` | URL or reference to the source |
| `publisher` | Who published the source |
| `effective_on` | Date the information takes effect |
| `verified_on` | Date a team member last checked it |
| `next_review_on` | Optional date the record must be re-checked |
| `licence` | Licence or permission under which it is republished |
| `researcher`, `reviewer` | Internal names; **never returned by the public API** |

**Row-level security.** Migration `0002` enabled RLS only on the tables that existed when it ran. `0003` therefore enables RLS on its three new tables itself and revokes the Supabase `anon` and `authenticated` grants, using the same pattern. `tests/test_rls.py` fails if any public table lacks RLS.

**Reversibility.** `downgrade()` drops the indexes, tables, check constraints, columns and enum types. The sequence upgrade, `alembic check`, downgrade and upgrade was run clean on PostgreSQL 17.

### 1.5 Advisory freshness logic

`advisory_state()` in `destination_services.py` is a pure function of five dates. `today` is the Dhaka date; it is injectable so every boundary is testable.

| State | Rule | Returned by the profile |
|---|---|---|
| `NOT_YET_EFFECTIVE` | `today < effective_on` | Never |
| `EXPIRED` | `today > valid_until` | Only with `include_expired=true` |
| `STALE` | in effect, but `today - verified_on > ADVISORY_STALE_AFTER_DAYS` | Yes, flagged |
| `CURRENT` | in effect and verified within the threshold | Yes |

Design points:

- **Expired wins over stale.** An old, expired advisory is `EXPIRED`, never `STALE`, so it cannot be mistaken for something merely out of date.
- **The last day is inclusive.** An advisory valid until today is still `CURRENT` today.
- **A future verification date does not make an advisory stale.**
- **The date is the Dhaka date.** At 20:30 UTC on 19 October it is already 20 October in Dhaka, and a test proves the service uses 20 October. Using the UTC date would show an expired advisory as current for six hours each day.
- **State is never stored.** It is derived on every read, so no job has to run for an advisory to expire.
- `as_of` and `stale_after_days` are returned so the client can label advisories and the offline pack can record the evaluation date.

### 1.6 Service layer

`backend/app/destination_services.py` keeps the review code in `services.py` untouched.

| Function | Responsibility |
|---|---|
| `today_in_display_tz(now=None)` | Current date in `DEFAULT_DISPLAY_TIMEZONE` (default `Asia/Dhaka`) |
| `advisory_state(...)` | The classification in section 1.5 |
| `list_published_destinations(session, limit, after, today)` | Page of destinations with ratings and active-advisory counts. Ratings are fetched in one query and advisory counts in one grouped query per page, so there is no per-row query. |
| `get_destination_profile(session, id, include_expired, today)` | Loads the destination, published guide items, advisories (filtered in SQL by `effective_on <= today` and, unless requested, `valid_until >= today`) and contacts; raises `DestinationNotFound` for anything not `PUBLISHED`. |
| `encode_destination_cursor` / `decode_destination_cursor` | Opaque, URL-safe cursor. The last separator splits the value, so a name containing `|` round-trips. Malformed values raise `InvalidCursor`. |

The rating summary reuses `destination_rating_stats`, the same aggregate the review feed uses, with the same average calculation. `last_updated` is the newest `updated_at` among the destination and the rows returned.

### 1.7 API layer

`backend/app/destination_api.py` holds only the two routes and the cache helpers.

- It raises the standard `ApiError` codes (`NOT_FOUND`, `INVALID_CURSOR`); the shared handlers turn them into the contract error body.
- `public_cache_headers()` is reused by the review feed so there is one definition of the public TTL.
- A `304` response carries the cache headers, as HTTP requires.
- Routes are `GET` only. `POST` and `DELETE` return `405 METHOD_NOT_ALLOWED`.

### 1.8 Configuration added

| Variable | Default | Effect |
|---|---|---|
| `ADVISORY_STALE_AFTER_DAYS` | `30` (1 to 365) | Verification age after which an in-effect advisory is `STALE` |
| `PUBLIC_CACHE_MAX_AGE_SECONDS` | `60` (0 to 3600) | `max-age` on the public destination routes and the review feed |

Both are documented in `backend/.env.example` and `Docs/Architecture.md`.

### 1.9 Privacy and safety properties

- No personal data is stored or returned. Contacts are public institutions and emergency numbers; private contacts stay on the device (proposal privacy rule).
- `researcher` and `reviewer` names are internal and not in any response schema.
- Non-published records return the same `404` as missing ones.
- The new tables are unreachable through the Supabase Data API (RLS enabled, no policies).
- Database check constraints reject impossible coordinates, free-text phone numbers and inverted advisory windows even if data is loaded outside the application.

### 1.10 Decisions taken for R02

Recorded in `Docs/Decisions.md` (entry of 19 October 2026).

| Decision | Reason |
|---|---|
| Exactly the two contract routes | The approved contract (section 4.3) lists two. Advisories and contacts travel inside the profile, giving the PWA and the offline pack one fetch. |
| Read-only scope; no staff write endpoints | Staff authentication is still the development header and returns `501` in production. Content is loaded by script or migration until R10 and R11. |
| Both languages in every payload | Offline packs need both, and the client chooses the language (FR02). Content therefore does not vary by `Accept-Language`. |
| Stale threshold of 30 days | A working default. **The team must confirm the value**; Platform Foundation 18.4 uses seven days as the default maximum age for safety-sensitive offline snapshots, which is a related but separate rule. |
| Public caching limited to three routes | Security 7.1 allows an exact route allowlist with a short TTL only. |

### 1.11 Tests and evidence

| File | Type | What it proves |
|---|---|---|
| `tests/test_destination_unit.py` | Unit, no database | State boundaries (last valid day, day after, not yet effective, stale threshold at 30 and 31 days, future verification, expired beats stale); Dhaka date versus UTC date; cursor round-trip and rejection of malformed cursors; ETag stability and sensitivity; `If-None-Match` parsing |
| `tests/test_destination_http.py` | HTTP, stubbed session | `404` and its body for unknown destinations, `no-store` on errors, `422` for bad identifiers and list parameters, no routes for advisories or contacts, read-only methods |
| `tests/test_destination_postgres.py` | Integration, PostgreSQL 17 | List filtering and stable two-page pagination; Bangla text and ratings in list items; advisory counts; draft and archived records return `404`; full profile content, ordering and provenance; researcher and reviewer absent; unpublished items hidden; expired, stale, future and unpublished advisories; severity ordering; destination-scoped contacts; cache headers, ETag and `304` on both routes; ETag changes with content; the review feed has the public TTL while health stays `no-store`; the database rejects bad coordinates, phone numbers and advisory windows |

Verification run on 19 October 2026 against PostgreSQL 17 in a throwaway container:

| Check | Result |
|---|---|
| `ruff check .` | clean |
| `mypy` (strict) | clean |
| `alembic upgrade head`, `alembic check`, downgrade and upgrade again | clean; "No new upgrade operations detected" |
| Full backend suite | 181 passed (the whole backend, including the R02 tests above) |
| Live check with `uvicorn` and `curl` | list returned `200` with `Cache-Control` and `ETag`; matching `If-None-Match` returned `304`; unknown identifier returned `404` |

To reproduce: start PostgreSQL 17, create a database whose name ends in `_test`, set `TEST_DATABASE_URL`, then run `uv run pytest -q` from `backend/`.

### 1.12 Not implemented for R02

| Item | Status |
|---|---|
| Real destination content (five bilingual destinations with sources and licences) | Seeded by `scripts/seed_destinations.py` on 19 October 2026 (section 2.5); R01 content review pending. |
| Frontend use of the endpoints | Done on 19 October 2026 (R03); see `Docs/Frontend-Implemented.md`. |
| Staff create, edit, publish and delete of destination content, translations and advisories | R10 and R11, after real staff authentication. |
| Confirmed advisory staleness threshold | Open decision for the team (section 1.10). |
| `last_updated` using verification dates | It uses row `updated_at` values only. |
| Pack manifest `GET /destinations/{id}/pack/manifest` | R14. |

---

## 2. Shared backend work built alongside R02

These items are not part of the R02 task, but the approved contract required them and R02 routes depend on them. Each is recorded with its evidence.

### 2.1 Standard error contract (contract section 2)

`backend/app/errors.py` is the single source for error bodies: `{"error": {"code", "message", "request_id", "field_errors"}}`.

- One catalogue maps every contract code to its HTTP status, a Bangla message and an English message. Bangla is the default; `Accept-Language` selects English, with quality values honoured.
- Handlers cover domain errors, framework `404` and `405`, validation failures, rate limits (with `Retry-After`), database outages, pool exhaustion, timeouts, oversized bodies and unexpected failures.
- `field_errors` carry only the field path and a stable code (`REQUIRED`, `TOO_SHORT`, `TOO_LARGE`, `INVALID_UUID`, `UNKNOWN_FIELD`, `FUTURE_MONTH` and so on). Submitted values are never echoed, because a rejected request can contain a receipt or Guest secret.
- `X-Request-ID` is a UUID and equals `error.request_id`.
- Evidence: `tests/test_errors.py`.

### 2.2 Client-generated receipts and the keyring (contract sections 5.1 to 5.4)

Migration `0004_receipt_keyring`, `backend/app/crypto.py`, `backend/app/services.py`.

- The client generates the receipt (`abr1_` plus 43 base64url characters). The server checks the exact format, rejects non-canonical and low-entropy values, stores only a keyed digest, and never issues, returns or reissues a receipt.
- Receipt, Guest-scope and network digests are HMAC-SHA-256 under a versioned key ring (`RECEIPT_KEYS`, `RECEIPT_KEY_CURRENT`; the pepper is key `v1` when no ring is set), separated by context labels. Lookups try every retained key; a successful receipt use re-digests under the current key.
- A repeated draft with the same receipt returns `200` and `duplicate_recovered: true`; with a different receipt it returns `409 DRAFT_ALREADY_SUBMITTED` without the review identifier.
- `POST /review-receipts/status` replaces `/review-receipts/exchange` and reports `decision_reason` and `appeal_deadline` for rejected reviews. Withdrawal succeeds on retry even with a stale version.
- Receipts and Guest-scope digests created before the migration are marked `legacy` (receipts revoked); pre-release data only.
- Evidence: `tests/test_receipts.py`.

### 2.3 Abuse controls (contract section 7, Platform Foundation 14)

Migration `0005_rate_limit_buckets`; `app/client_address.py`, `app/abuse.py`, `app/turnstile.py`.

- The client address is read from one configured provider header and position; no other forwarding header is read; IPv6 is reduced to /64; only a keyed digest is stored. Uvicorn runs with `--no-proxy-headers`.
- Durable fixed-window counters commit in their own transaction before the business operation: 3 new drafts per scope per day, 30 per network per hour and 100 per day, 20 receipt operations per receipt per hour and 100 per network per hour.
- Failed receipt lookups feed a two-tier progressive block (5 per 15 minutes, 20 per 24 hours) that answers `429` with `Retry-After` before any lookup.
- Pending ceilings of 50 per destination and 500 total return `503 GUEST_WRITES_PAUSED` for new Guest submissions; a warning is logged from 80 percent. `GUEST_WRITES_PAUSED=true` is the emergency switch; reads, receipt status and recovery of an existing draft continue.
- Turnstile is validated on the server (success, hostname, action, one retry with the same idempotency key; an unreachable Cloudflare returns `503`, never a pass).
- The submission order follows contract section 5.2 except step 3 (`Idempotency-Key` replay).
- Evidence: `tests/test_client_address.py`, `tests/test_turnstile.py`, `tests/test_abuse.py`.

### 2.4 Housekeeping

- The API contract moved to `Docs/api/API.md`. `tests/test_openapi_contract.py` reads it, and references in `Decisions.md`, `Implemented.md`, `Reviews/F02-review.md` and `README.md` were updated.
- `httpx` became a runtime dependency (Turnstile); `uv.lock` was refreshed.

### 2.5 Destination seed content and CORS origin fix (19 October 2026, frontend integration)

| Item | Detail | Evidence |
|---|---|---|
| `scripts/seed_destinations.py` | Loads the five semester destinations from `scripts/destination_seed_content.py`: profile fields, guide items, advisories and contacts with full provenance. Idempotent: a destination is matched by `name_en` (so the `seed_destination.py` smoke record keeps its id and reviews), children are replaced with stable UUIDv5 ids, the rating aggregate row is created if missing and never reset. Refuses production without `--force`. `reviewer` stays empty until the R01 content review. | Two runs on a fresh database reused every id |
| `tests/test_seed_content.py` | Checks the content against the database constraints (lengths, phone format, coordinate ranges, advisory window) and PF 17 provenance, with no database. | 52 passed |
| `Settings.cors_origins` | Strips trailing slashes. Browsers send `Origin` without a path, so `http://localhost:5173/` in `CORS_ALLOWED_ORIGINS` silently blocked every request from the local frontend. | `tests/test_config.py::test_cors_origins_ignore_trailing_slashes` |

Run after migrating: `uv run python scripts/seed_destinations.py`.

Findings for the backend owner, recorded in `Docs/Frontend-Implemented.md` section 6: Guest reviews return `counted_rating` as the rating although API.md 5.10 says `null` (aggregates are correct); `test_unset_environment_fails_closed` depends on `DATABASE_URL` being set in the shell.

---

## 3. Not implemented in the backend

| Area | Contract reference | Planned work |
|---|---|---|
| `Idempotency-Key` replay | section 3 | WP4 |
| Edit pending review, appeals | 4.2, 5.5, 5.6 | WP6 (R07) |
| Member reviews, `GET /reviews/{id}` | 4.5 | WP6 with authentication |
| Reports and removal requests | 4.4, 5.7 | WP7 (R11) |
| Paged staff moderation queue; `build` and `db_revision` in `/health/ready` | 5.9, 4.1 | WP8 |
| Credentialed CORS, CSRF token endpoint | 1.2, `GET /auth/csrf` | WP9 |
| Registration, sign-in, sessions, staff MFA, verifications, role grants | 4.5, 4.6 | WP10 (R04, R11); needs `Features/Identity-Access-Verification.md` |
| Destination pack manifest | 4.3 | WP11 (R14) |

## 4. Open items that need evidence outside this repository

| Item | Why it is open |
|---|---|
| Forged-header test on the real Render edge | The trusted-address header cannot be proven locally. Production refuses to start without `CLIENT_ADDRESS_HEADER`. Platform Foundation 14.2 requires the result to be recorded in `Architecture.md` (Gate A). |
| Live Turnstile key | Tests use a mocked Cloudflare endpoint. |
| First green CI run on the pull request | All results above are from a local run. |
| Docker image build of the changed `Dockerfile` | Not confirmed locally. |
