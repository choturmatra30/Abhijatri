# Backend handoff: open issues and work the frontend needs

**From:** Abdullah (frontend). **Date:** 6 November 2026.
**For:** Muhtasim (backend, R14, R16), Shahriar (Railway, Vercel, merges).
**Status:** each item says what is wrong, why it matters, what to do, and how to check it is done. Evidence and history: `Frontend-Implemented.md` section 6 (same IDs).

| ID | What | Owner | Blocks | Priority |
|---|---|---|---|---|
| [B5](#b5-live-api-sends-no-store-on-public-destination-routes) | Live API sends `Cache-Control: no-store` on public destination routes | Railway owner | R12 acceptance, R13 | **High** |
| [B6](#b6-shared-database-runs-out-of-connections) | Shared database runs out of connections (`EMAXCONNSESSION`) | Muhtasim, Supabase owner | Local development, possibly live | **High** |
| [DEP1](#dep1-the-live-site-does-not-have-the-abd-work) | Live site has none of the `abd` work | Abdullah (PR), Shahriar (merge) | R12 acceptance | **High** |
| [R14](#r14-pack-manifest-endpoint) | Pack manifest endpoint | Muhtasim | R13 offline packs | Due 27 Oct (late) |
| [R16](#r16-idempotency-key-replay-on-review-submission) | `Idempotency-Key` replay on review submission | Muhtasim | R15 offline drafts | Due 28 Oct (late) |

---

## B5: Live API sends `no-store` on public destination routes

**What is wrong.** On the live API, these three routes answer `Cache-Control: no-store`:

- `GET /api/v1/destinations`
- `GET /api/v1/destinations/{id}`
- `GET /api/v1/destinations/{id}/reviews`

The code on `main` sends `public, max-age=60` for exactly these routes (`app/destination_api.py` `public_cache_headers`, used in `app/api.py`). `app/main.py` adds `no-store` with `setdefault`, so it never overrides a route's own header. Locally (FastAPI `TestClient`) all three return `public, max-age=60` with no `Set-Cookie`. So Railway runs older code, or something in front of it rewrites the header.

**Why it matters.** The offline service worker (R12) must honour `no-store` (Security.md 7.4), so on the live site no destination is ever saved for offline. Offline mode works locally and will not work live until this is fixed.

**What to do.**
1. Redeploy Railway from current `main`.
2. In Railway's variables, check `PUBLIC_CACHE_MAX_AGE_SECONDS` is unset or a positive number (`0` gives `max-age=0`, which also defeats offline).
3. Do **not** ask the frontend to ignore `no-store`; the security rules forbid it.

**Done when:**

```
curl -sI https://abhijatri-backend.up.railway.app/api/v1/destinations | grep -i cache-control
```

prints `Cache-Control: public, max-age=60` (and the same for a destination id and its `/reviews`).

---

## B6: Shared database runs out of connections

**What is wrong.** The backend fails with:

```
FATAL: (EMAXCONNSESSION) max clients reached in session mode - max clients are limited to pool_size: 15
```

and then answers `503 SERVICE_UNAVAILABLE` to every route.

`DATABASE_URL` uses the Supabase **session-mode** pooler (`aws-0-ap-southeast-1.pooler.supabase.com:5432`), which allows **15 clients in total** for everyone. Each backend process may hold `DB_POOL_SIZE` 5 + `DB_MAX_OVERFLOW` 2 = **7** (`app/config.py`). Railway plus one or two local backends (and seed or test scripts) exceed 15.

**What to do (pick one or combine).**
1. **Quick, for local development:** in each local `backend/.env`, set `DB_POOL_SIZE=2` and `DB_MAX_OVERFLOW=0`.
2. **Proper:** switch to the **transaction-mode** pooler (port `6543`). psycopg's prepared statements must be turned off for it (`connect_args={"prepare_threshold": None}` in `app/db.py`'s `create_engine`), then run the test suite.
3. **Separate local work from the shared database:** develop against the local database (`127.0.0.1:54322`, already used for tests) instead of Supabase.

**Done when** Railway and two local backends run at the same time for 10 minutes without the error.

---

## DEP1: The live site does not have the `abd` work

**What is wrong.** Vercel builds `main`, last changed 1 November 2026 (PR #34). None of the frontend work since then is live: offline mode and installability (R12), shadcn/ui and the new theme, the review split, the destination selector, the Chrome audit fixes. On `https://abhijatri.vercel.app`, `/sw.js` and `/manifest.webmanifest` return the web page instead of the files.

**What to do.** Abdullah opens a pull request from `abd` to `main`; Shahriar reviews and merges; Vercel redeploys. No Vercel settings need changing (`frontend/vercel.json` already serves `sw.js` and the manifest with `no-cache`).

**Done when:**

```
curl -sI https://abhijatri.vercel.app/sw.js | grep -i content-type
```

shows `javascript`, and `/manifest.webmanifest` shows `application/manifest+json`.

---

## R14: Pack manifest endpoint

**What the frontend needs (for R13, offline destination packs).** API.md section 4 lists `GET /destinations/{destination_id}/pack/manifest` as "Planned (R14)" with no body yet. Platform Foundation 18.4 says every offline pack includes the fields below. Proposed response:

```json
{
  "destination_id": "uuid",
  "pack_version": 1,
  "content_version": "weak ETag or hash of the destination payload",
  "generated_at": "2026-11-06T10:00:00Z",
  "advisories_verified_at": "2026-11-01T00:00:00Z",
  "expires_at": "2026-11-13T10:00:00Z",
  "languages": ["bn", "en"],
  "sha256": "hex SHA-256 of the pack body",
  "parts": [
    { "path": "/api/v1/destinations/{id}", "sha256": "..." },
    { "path": "/api/v1/destinations/{id}/reviews?limit=10", "sha256": "..." }
  ],
  "removed_review_ids": []
}
```

**Rules from the specs.**
- Public route, `Cache-Control: public, max-age=60` and an `ETag` like the other destination routes (Decisions 2026-10-19 "Public caching"); never `no-store`.
- `expires_at`: 7 days after `generated_at` until the Step 8 decision (PF 18.4 default).
- `removed_review_ids`: reviews hidden, withdrawn or deleted since the previous pack, so a device removes them before showing a refreshed pack (PF 18.4 "applies removals").
- Only published, public content (PF 18.1); no user data.

**Until R14 lands,** the frontend builds R13 from the existing public routes and uses the destination's `last_updated` as the version, then switches to this endpoint.

**Done when** the route exists with tests (`404` for an unknown or draft destination; the hash matches the parts) and is in `Docs/api/API.md` and `openapi-v1.json`.

---

## R16: `Idempotency-Key` replay on review submission

**What already works.** Duplicate-proof guest submission via `client_draft_id` is implemented (API.md 5.2, order of checks step 2): the same `(guest scope, client_draft_id)` returns the existing review with `duplicate_recovered: true`.

**What is missing.** Step 3, `Idempotency-Key` replay (WP4), is not built. API.md section 6 says the header is "allowed by CORS but ignored". Without it, a retry after a lost response is recovered by step 2 for guest reviews, but other retryable writes (withdraw, member review, edit) have no replay.

**What to do (API.md section 3).**
- Store `(key, route, actor, request-body hash) → response` with an expiry; document the expiry (Gantt R16 note).
- Same key and same body: return the stored response. Same key, different body: `409 IDEMPOTENCY_KEY_REUSED`.
- A unique constraint on the key (Gantt R16 acceptance: "unique constraint and retry tests pass").
- Also confirm `POST /reviews/member` has the same `client_draft_id` recovery as the guest route.

**Done when** retry tests pass (same key twice returns one review; different body returns `409`), and API.md section 6 no longer lists the header as ignored.

---

## Older items still listed as open

These are from 19 October in `Frontend-Implemented.md` section 6. Please confirm or close them:

- **B1:** `counted_rating` is returned for Guest reviews, while API.md 5.10 says it is `null` for them.
- **B2:** `tests/test_config.py::test_unset_environment_fails_closed` fails unless `DATABASE_URL` is set in the shell.
- **B3:** the local `backend/.env` lists the API's own address as an allowed CORS origin.
- **B4:** Railway running pre-merge code. **Likely fixed:** `/destinations` and the review routes answer correctly now. Only B5 remains.
