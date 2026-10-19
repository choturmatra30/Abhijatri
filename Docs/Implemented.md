# Implemented status

Claims here are limited to what is in the repository and evidenced by a test, migration check, or CI run. Last updated 19 October 2026.

| Area | Status | Evidence |
|---|---|---|
| Review schema, constraints, enums | Implemented | `migrations/versions/0001_review_vertical_slice.py`; `alembic upgrade head`, `check`, `downgrade base` clean on PostgreSQL 17. |
| Guest submission, permanent draft dedup, receipts | Implemented | `tests/test_review_postgres.py::test_guest_vertical_slice_and_retry_deduplication`. |
| Moderation, publish/hide/restore/withdraw with locked rating deltas | Implemented | Concurrency and property tests in `tests/test_review_postgres.py`. |
| Conflict flag transitions | Implemented | `test_conflict_flag_uses_locked_rating_delta`. |
| Public feed with stable cursor | Implemented | Vertical-slice test; `tests/test_review_unit.py`. |
| Production config guard, CORS allow-list, docs toggle, readiness probe | Implemented | `tests/test_config.py`; `app/main.py`. |
| CI (lint, unit, integration, migrations, audit, secret scan, image build) | Defined | `.github/workflows/ci.yml`; first green run to be confirmed on the PR. |
| Render deployment blueprint | Defined, not yet applied | `render.yaml`; requires dashboard setup and the Supabase URL. |
| Pending-review edit endpoint (`PATCH /reviews/{id}/pending`) | Not implemented | Decided in Decisions.md; endpoint absent from `app/api.py`. |
| Member reviews, accounts, verification, reports, appeals | Not implemented | Gantt R04, R07, R11. |
| Production authentication, staff MFA, CSRF, rate limiting | Not implemented | Security.md deploy gates; staff API returns 501 in production. |
| ERD (`Docs/Schema.md`) and API contract (`Docs/api/API.md`, `Docs/api/openapi-v1.json`) | Implemented, review pending | Contract and schema drift tests; sign-off in `Docs/Reviews/F02-review.md`. |
| Row-level security on all public tables | Implemented | `migrations/versions/0002_enable_rls.py`; `tests/test_rls.py`. |
| Destination profile, bilingual guide items, dated advisories (Current/Stale/Expired), public contacts, provenance; `GET /destinations`, `GET /destinations/{destination_id}` with public cache and ETag (R02) | Implemented | `migrations/versions/0003_destination_content.py`; `tests/test_destination_unit.py`, `test_destination_http.py`, `test_destination_postgres.py`; 70 backend tests pass on PostgreSQL 17 on 19 Oct 2026. No destination content is seeded beyond the one smoke-test record (R01). |
| Public review feed cache header | Implemented | `tests/test_destination_postgres.py::test_review_feed_has_a_short_public_ttl`. |
| Standard error body, bilingual messages, field-error codes (WP2) | Implemented | `tests/test_errors.py`. |
| Client-generated receipts, versioned HMAC keyring with rotation, `POST /review-receipts/status`, idempotent withdraw (WP3) | Implemented | `tests/test_receipts.py`; migration `0004_receipt_keyring`. |
| Trusted client address, durable rate limits, progressive receipt block, pending ceilings, emergency switch, server-side Turnstile (WP5) | Implemented, **staging proof outstanding** | `tests/test_client_address.py`, `test_turnstile.py`, `test_abuse.py`; migration `0005_rate_limit_buckets`. The forged-header test against the real Render edge and a live Turnstile key have not been run. 181 backend tests pass on PostgreSQL 17 on 19 Oct 2026. |
| `Idempotency-Key` replay (WP4), edit-pending, appeals, reports (WP6, WP7), CSRF and credentialed CORS (WP9), authentication (WP10), pack manifest (WP11) | Not implemented | `Docs/api/API.md` section 4. |
| Redis, CDN, media pipeline, offline pack API | Deferred | Decisions.md scope control; Gantt R14. |

## R02: Destination, advisory and contact data services (19 October 2026)

Full account: [`Docs/Backend-Implemented.md`](Backend-Implemented.md), section 1. This entry is a summary; the evidence below comes from a local run on PostgreSQL 17 on 19 October 2026 (181 backend tests passed, `ruff` and strict `mypy` clean, migrations applied and reversed cleanly). A first CI run on the pull request is still to be confirmed.

| Item | Status | Evidence |
|---|---|---|
| `GET /api/v1/destinations`: paged list of published destinations with both-language names, region, summary, coordinates, rating summaries, active-advisory count | Implemented | `tests/test_destination_postgres.py`; contract `Docs/api/API.md` 5.12 |
| `GET /api/v1/destinations/{destination_id}`: bilingual profile with seasonality, restrictions, guide items, advisories, contacts and per-record provenance | Implemented | `tests/test_destination_postgres.py`; contract 5.13 |
| Advisory states `CURRENT`, `STALE`, `EXPIRED`, `NOT_YET_EFFECTIVE`, evaluated on the Asia/Dhaka date; expired items hidden unless `include_expired=true` | Implemented | `tests/test_destination_unit.py` (boundaries, Dhaka versus UTC date), `test_destination_postgres.py` |
| Schema: profile columns on `destinations`; tables `destination_guide_items`, `destination_advisories`, `destination_contacts`; provenance columns, check constraints, indexes; row-level security on the new tables | Implemented | Migration `0003_destination_content`; `tests/test_rls.py`; `tests/test_docs_schema.py`; database rejection of bad coordinates, phone numbers and advisory windows is tested |
| Public caching: `Cache-Control: public, max-age=60` and weak ETag with `304` on the two routes; the review feed also has the short public TTL; all other routes stay `no-store` | Implemented | `tests/test_destination_postgres.py` |
| Privacy: no personal data; researcher and reviewer names not returned; non-published records return the same `404` as missing ones | Implemented | `tests/test_destination_postgres.py`, `tests/test_destination_http.py` |
| Settings `ADVISORY_STALE_AFTER_DAYS` (30) and `PUBLIC_CACHE_MAX_AGE_SECONDS` (60) | Implemented | `backend/.env.example`; `Docs/Architecture.md` |
| Real destination content for five destinations with sources and licences | Not implemented | R01. Only the Cox's Bazar smoke-test record exists. |
| Frontend using the endpoints | Not implemented | R03. The Destinations pages still use hardcoded data. |
| Staff create, edit and publish of destination content | Not implemented | R10 and R11, after real staff authentication. |
| Advisory staleness threshold of 30 days | Open | Working default; the team must confirm the value. |

Shared backend work built with R02 (error contract, client-generated receipts with a versioned keyring, durable rate limits, Turnstile validation) is described in `Docs/Backend-Implemented.md`, section 2.
