# Abhijatri Implementation Decisions

This log records build-time decisions without reopening the frozen Review specification.

## 2026-10-14

| Decision | Rule | Reason |
|---|---|---|
| Published review editing | Deferred to v1.1. The MVP uses withdraw and resubmit. | Prevents rating and revision races in the first vertical slice. |
| Feed cursor | Order by `(published_at, id)` descending. | Stable pagination when moderation publishes older submissions later. |
| Rating transitions | Lock the review and destination aggregate rows, check `version`, and apply `counted_rating` deltas once. | Prevents double counting under retries and concurrent moderation. |
| Member rating eligibility | Only an active, non-revoked `VERIFIED_MEMBER` verification is eligible. Team and conflict-declared reviews are excluded. | Keeps the Community Rating claim truthful. |
| Visit month clock | Reject future months using `Asia/Dhaka`. | Makes the rule deterministic for a Bangladesh-first platform. |
| Moderator self-review | Denied in the service layer. | Prevents an obvious conflict of interest. |
| Infrastructure order | PostgreSQL correctness first. Redis, CDN, and media processing remain deferred. | Keeps the first release testable and within semester scope. |
| Pending-review revisions | A Guest receipt may edit only a `PENDING` or `CHANGES_REQUESTED` review through `PATCH /api/v1/reviews/{review_id}/pending`. | Published-review editing remains deferred to v1.1. |
| Conflict changes | Setting or clearing `conflict_declared` is a locked rating transition with an expected-version check and the same `counted_rating` delta mechanism used by publish, hide, and withdraw. | Prevents a moderator flag change from leaving Community Rating stale. |
| Rejected rating value | A rejected review has `counted_rating = NULL`. If it was never published, its aggregate delta is zero. | Makes rejection behavior explicit and testable. |
| Restore transition | Restore applies only to a `HIDDEN` review and returns it to `PUBLISHED` after recalculating its current eligibility through the locked delta path. | Gives the aggregate property test and moderation workflow a precise restore meaning. |
| Active duplicate states | For one Member review per destination and visit month, active means `PENDING`, `UNDER_REVIEW`, `CHANGES_REQUESTED`, `PUBLISHED`, or `HIDDEN`. `REJECTED`, `WITHDRAWN`, and `DELETED` do not block a replacement. A recorded moderator override permits a legitimate repeat visit. | Prevents duplicate active submissions without permanently blocking corrected or later submissions. |

## 2026-10-15 (F06: repositories, CI, shared environments)

| Decision | Rule | Reason |
|---|---|---|
| System flow | React PWA -> HTTPS -> FastAPI (Render, Docker) -> SQLAlchemy/Psycopg -> Supabase-managed PostgreSQL. The browser never holds a Supabase key or calls Supabase directly. | Keeps authorisation, moderation and rating integrity in one server-side boundary. |
| Supabase connection | Backend uses the Supavisor **session** pooler URI (port 5432, `sslmode=require`). Transaction mode (6543) is not used. | Render is IPv4 and the direct host is IPv6-only; row locks and `SELECT ... FOR UPDATE` need session-stable connections. |
| Schema changes | Alembic only. Migrations run at container start (`alembic upgrade head`). Optional `MIGRATION_DATABASE_URL` allows a separate migrator role later. | Render `preDeployCommand` is paid-only; the migrator role is a Security 4.4 deploy gate. |
| Production config guard | Startup fails closed on default or short pepper, wildcard CORS, or non-TLS remote database. | Prevents silent insecure deployment. |
| Environments | `abhijatri-dev` (shared team) and `abhijatri-prod` (demo) Supabase projects; CI uses a throw-away PostgreSQL service container and never touches Supabase. | Security 9.1 environment separation. |
| Staff API on Render | Moderation endpoints return 501 in production until the real authentication adapter (R04) replaces the test header. | Security 2.2; the header must never be accepted publicly. |
| Deploy trigger | Render auto-deploys only after CI checks pass on `main` (`autoDeployTrigger: checksPass`). | Broken builds cannot reach the demo environment. |
| Free-tier risk | Supabase free projects pause when idle; use a paid plan or keep-alive before test and demo windows. | Avoids a dead demo. |
| Test fix | `test_concurrent_publish_counts_once` rebuilt its engine from `str(url)`, which masks the password; it now uses `render_as_string(hide_password=False)`. | The concurrency gate could not run against a password-protected database. |

**Evidence:** first real PostgreSQL execution on 15 October 2026 passed all 20 tests, including the aggregate property test, concurrent moderation test, and Guest vertical slice; `alembic upgrade head`, `alembic check`, and `alembic downgrade base` are clean. Gates 2-4 below are therefore met locally and are re-verified on every CI run.

## 2026-10-15 (F02: schema and API contract)

| Decision | Rule | Reason |
|---|---|---|
| ERD and contract location | `Docs/Schema.md` (Mermaid ERD, implemented vs planned) and `Docs/API.md` plus `Docs/api/openapi-v1.json`. | One reviewed source for Abdullah and Irfan. |
| Contract drift | `tests/test_openapi_contract.py` fails when `app.openapi()` differs from the committed snapshot or a route is missing from `Docs/API.md`; `tests/test_docs_schema.py` does the same for tables. | Keeps documents honest without manual review. |
| Pending-review edit | `PATCH /reviews/{id}/pending` stays **planned (R07)**; it is not implemented in this slice. | Avoids shipping unreviewed revision logic during a documentation task. |
| Versioning | Additive changes stay in `/api/v1`; breaking changes need `/api/v2`. | Frontend can rely on stability. |

## Decisions scheduled during implementation

These choices are intentionally made at the named implementation step and then recorded in this log. They are not permission to weaken the frozen security or correctness rules.

| When | Decision to record | Required guardrail | Status |
|---|---|---|---|
| Step 4 | Exact submission and receipt rate limits, the anti-abuse challenge, and the maximum number of pending reviews per Guest scope. | Limits must combine Guest scope, account where present, and cautiously weighted IP signals because mobile-carrier CGNAT makes IP-only blocking unsafe. | Open until Step 4 load and abuse tests. |
| Step 5 | Final duplicate-index implementation and rejection transition behavior. | Rejection leaves `counted_rating` null; active states are the states recorded above; all aggregate changes use row locks and version checks. | Rules fixed; implementation and PostgreSQL tests in progress. |
| Step 7 | Moderator self-review and visit-month timezone. | A moderator cannot moderate their own review; future visit months are evaluated in `Asia/Dhaka`. | Decided and implemented in the service and validation layers. |
| Step 8 | Maximum age and refresh behavior for offline review snapshots. | The UI must display snapshot age, attempt refresh on reconnection, and stop presenting an over-age snapshot as current because removed reviews can remain on a device. | Open until offline-pack testing. |
| Account deletion | Choose anonymisation or deletion for eligible review content. | Either choice must remove personal linkage as promised, subtract any `counted_rating` in the same locked transaction, emit an audit/outbox event, and preserve only the minimum lawful deletion ledger. | Open before account-deletion implementation. |

## First-week execution gates

Work may proceed beyond the first review slice only after these gates have evidence.

| Order | Gate | Required evidence | Current status |
|---:|---|---|---|
| 1 | Database invariants | PostgreSQL migrations contain permanent draft uniqueness, the active Member duplicate index, enum-backed state values, rating checks from 1 to 5, aggregate non-negative checks, and foreign keys. | Implemented; migration SQL generation passes. |
| 2 | Aggregate property test | Random sequences of publish, hide, withdraw, and restore produce the same sums and counts as a full recomputation on real PostgreSQL. | Passed on real PostgreSQL 17 (15 Oct 2026); re-run in CI. |
| 3 | Moderation concurrency test | Two moderators acting on the same review concurrently produce one successful transition, one version conflict, and exactly one aggregate delta. | Passed on real PostgreSQL 17 (15 Oct 2026); re-run in CI. |
| 4 | Guest vertical slice | One Guest review completes submit, moderation, publication, public retrieval, and Guest Feedback aggregate update end to end. | Passed on real PostgreSQL 17 (15 Oct 2026); re-run in CI. |

## Scope control

The Review specification is frozen after the schema amendments. Necessary implementation changes are added to this decisions log rather than rewriting the architecture. Redis, CDN integration, and the image pipeline remain out of scope until implementation steps 1 through 9 and their regression tests pass.

