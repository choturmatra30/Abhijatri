# Backend handoff: open issues and work the frontend needs

**From:** Abdullah (frontend). **Date:** 6 November 2026.
**For:** Muhtasim (backend, R14, R16), Shahriar (Railway, Vercel, merges).
**Updated 7 November 2026:** B5 withdrawn (it was a measurement error), DEP1 closed (deployed), R16 merged and live. Still open: B6 (Railway variable) and question Q1.
**Status:** each item says what is wrong, why it matters, what to do, and how to check it is done. Evidence and history: `Frontend-Implemented.md` section 6 (same IDs).

**Update, 6 November 2026 (backend):** B5 and DEP1 are fixed and verified on the live system. R14 is merged and live (PR #37). R16 is built, tested and in PR #39, not yet merged (`Backend-Implemented.md` 5.23 to 5.25). B6 has its code change; the Railway variable change is still a deploy-owner step. B1, B2 and B3 are closed. Migration `0022` is applied to the shared database. The tables below keep the original text; the **Status** column is the current state.

| ID | What | Owner | Blocks | Priority | Status (6 Nov 2026) |
|---|---|---|---|---|---|
| [B5](#b5-withdrawn-cache-headers-are-correct) | ~~Live API sends `no-store`~~ **Withdrawn: headers are correct** | none | nothing | Closed |
| [B6](#b6-shared-database-runs-out-of-connections) | Shared database runs out of connections (`EMAXCONNSESSION`) | Muhtasim, Supabase owner | Local development, possibly live | **High** | **Code done** (`DB_PREPARED_STATEMENTS`, auto-off on port 6543). Pending: set Railway `DATABASE_URL` to port 6543 and run the 10-minute check |
| [DEP1](#dep1-closed-the-abd-work-is-live) | ~~Live site has none of the `abd` work~~ **Closed: deployed** | Abdullah, Shahriar | nothing | Closed |
| [R14](#r14-pack-manifest-endpoint) | Pack manifest endpoint | Muhtasim | R13 offline packs | Due 27 Oct (late) | **Merged and live (PR #37).** The route set differs from the proposal below: `manifest`, `pack?version=` and `packs/freshness` (API.md 5.23) |
| [R16](#r16-idempotency-key-replay-on-review-submission) | `Idempotency-Key` replay on review submission | Muhtasim | R15 offline drafts | Due 28 Oct (late) | **Merged and live (PR #39, 7 Nov 2026).** Live check passed: the API exposes `Idempotent-Replayed, Retry-After` (Offline-Frontend-Guideline 7). Remaining: test group R (guideline 9.6) |
| [Q1](#q1-where-does-the-guest-scope-secret-live) | **Question:** where the guest scope secret is stored (two specs disagree) | Muhtasim (spec owner) | R15 offline drafts | Answer before R15 | **Open (7 Nov 2026)** |

---

## B5: Withdrawn, cache headers are correct

**7 November 2026.** This was a mistake in the frontend's check, not a backend defect. `curl -I` sends a HEAD request; the API answers HEAD with `405` and `Cache-Control: no-store`, and the status line was filtered out. With a normal GET, the live API (through Vercel and on Railway) sends `Cache-Control: public, max-age=60` on `/destinations`, `/destinations/{id}`, `/destinations/{id}/reviews` and `/destinations/{id}/pack/manifest`, exactly as designed. **No action needed.** Sorry for the noise.

To check headers in future, use GET:

```
curl -s -D - -o /dev/null https://abhijatri-backend.up.railway.app/api/v1/destinations | grep -i cache-control
```

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

## DEP1: Closed, the `abd` work is live

**7 November 2026.** PR #38 merged `abd` into `main` and Vercel deployed it. `https://abhijatri.vercel.app/sw.js` is served as `application/javascript` and `/manifest.webmanifest` as `application/manifest+json`. Offline mode works on the live site (emulated acceptance passed; the real-phone run is in `Handoff-Testing.md`).

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

## Q1: Where does the guest scope secret live?

**Asked by Abdullah, 7 November 2026. Please answer before R15 (offline drafts) starts.**

Two documents disagree:

| Source | Says |
|---|---|
| `Features/Platform-Foundation.md` 18.1 | IndexedDB may hold "the guest scope secret" (and lists what each store may hold) |
| `Docs/Guest-Identity-and-Visits.md` (the `localStorage` key table) | The secret is stored in `localStorage` |
| `Docs/Offline-Frontend-Guideline.md` 4.3 | Copy it into IndexedDB `meta`, keep `localStorage` as the reader for now |

**Today** it is only in `localStorage` (`getGuestScopeSecret()` in `frontend/src/api/reviews.ts`). R13 step A deliberately left it there.

**Hard rule either way:** the value must never change. A new secret gives the visitor a new guest tag and breaks recovery of their reviews.

**Questions:**
1. Which document is right? If IndexedDB, should `Guest-Identity-and-Visits.md` be updated to say so?
2. If IndexedDB: is "write-through, `localStorage` stays the reader" (guideline 4.3) acceptable as the final state for M1, or must the app read from IndexedDB too (an async change touching every caller)?
3. R15 stores an unsent guest draft with its scope (guideline 6.2). Should the draft keep its own copy of the secret, so it can be sent after "Start as a new guest", as test D10 expects?

**Done when** the answer is written here and the losing document is corrected.

---

## Older items still listed as open

These are from 19 October in `Frontend-Implemented.md` section 6. Please confirm or close them:

- **B1 (closed 6 Nov, contract corrected):** the code was right and API.md 5.10 was wrong. Security.md defines `counted_rating` as the contribution currently present in an aggregate, the rating code subtracts it later, and the staff Decided screen uses it to show that a hidden rating still counts. API.md 5.10 now says so, and `test_a_published_guest_review_reports_its_counted_rating` pins it.
- **B1, original text:** `counted_rating` is returned for Guest reviews, while API.md 5.10 says it is `null` for them.
- **B2 (closed 6 Nov):** the test passes with `DATABASE_URL` unset.
- ~~**B2:**~~ `tests/test_config.py::test_unset_environment_fails_closed` fails unless `DATABASE_URL` is set in the shell.
- **B3 (closed 6 Nov):** `.env` no longer lists the API's own address.
- ~~**B3:**~~ the local `backend/.env` lists the API's own address as an allowed CORS origin.
- **B4:** Railway running pre-merge code. **Likely fixed:** `/destinations` and the review routes answer correctly now. Only B5 remains.
