# Implemented status

Claims here are limited to what is in the repository and evidenced by a test, migration check, or CI run. Last updated 15 October 2026.

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
| ERD (`Docs/Schema.md`) and API contract (`Docs/API.md`, `Docs/api/openapi-v1.json`) | Implemented, review pending | Contract and schema drift tests; sign-off in `Docs/Reviews/F02-review.md`. |
| Row-level security on all public tables | Implemented | `migrations/versions/0002_enable_rls.py`; `tests/test_rls.py`. |
| Redis, CDN, media pipeline, offline pack API | Deferred | Decisions.md scope control; Gantt R14. |
