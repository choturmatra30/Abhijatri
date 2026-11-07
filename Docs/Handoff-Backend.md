# Backend handoff: open issues and work the frontend needs

**From:** Abdullah (frontend). **Date:** 6 November 2026.
**For:** Muhtasim (backend, R14, R16), Shahriar (Railway, Vercel, merges).
**Updated 7 November 2026 (afternoon):** B5 withdrawn (a measurement error), DEP1 closed, R16 merged and live. **New: DEP2 (R13 not deployed), TS1 (Turnstile site key missing on Vercel), DOC1 (guideline status table out of date).** Q1 has a likely answer in Decisions.md (see Q1). Still open: B6.
**Status:** each item says what is wrong, why it matters, what to do, and how to check it is done. Evidence and history: `Frontend-Implemented.md` section 6 (same IDs).

**Update, 6 November 2026 (backend):** B5 and DEP1 are fixed and verified on the live system. R14 is merged and live (PR #37). R16 is built, tested and in PR #39, not yet merged (`Backend-Implemented.md` 5.23 to 5.25). B6 has its code change; the Railway variable change is still a deploy-owner step. B1, B2 and B3 are closed. Migration `0022` is applied to the shared database. The tables below keep the original text; the **Status** column is the current state.

| ID | What | Owner | Blocks | Priority | Status (6 Nov 2026) |
|---|---|---|---|---|---|
| [B5](#b5-withdrawn-cache-headers-are-correct) | ~~Live API sends `no-store`~~ **Withdrawn: headers are correct** | none | nothing | Closed |
| [B6](#b6-shared-database-runs-out-of-connections) | Shared database runs out of connections (`EMAXCONNSESSION`) | Muhtasim, Supabase owner | Local development, possibly live | **High** | **Code done** (`DB_PREPARED_STATEMENTS`, auto-off on port 6543). Pending: set Railway `DATABASE_URL` to port 6543 and run the 10-minute check |
| [DEP1](#dep1-closed-the-abd-work-is-live) | ~~Live site has none of the `abd` work~~ **Closed: deployed** | Abdullah, Shahriar | nothing | Closed |
| [R14](#r14-pack-manifest-endpoint) | Pack manifest endpoint | Muhtasim | R13 offline packs | Due 27 Oct (late) | **Merged and live (PR #37).** The route set differs from the proposal below: `manifest`, `pack?version=` and `packs/freshness` (API.md 5.23) |
| [R16](#r16-idempotency-key-replay-on-review-submission) | `Idempotency-Key` replay on review submission | Muhtasim | R15 offline drafts | Due 28 Oct (late) | **Merged and live (PR #39, 7 Nov 2026).** Live check passed: the API exposes `Idempotent-Replayed, Retry-After` (Offline-Frontend-Guideline 7). Remaining: test group R (guideline 9.6) |
| [Q1](#q1-where-does-the-guest-scope-secret-live) | **Question:** where the guest scope secret is stored (two specs disagree) | Muhtasim (spec owner) | R15 offline drafts | Answer before R15 | **Open; likely answered by Decisions 2026-10-19** (see Q1) |
| [DEP2](#dep2-r13-offline-packs-are-not-on-the-live-site) | R13 offline packs (and R15 part 1 once committed) are not on the live site | Abdullah (PR), Shahriar (merge) | R13 phone tests (guideline group P) | **High** | **Open (7 Nov 2026)** |
| [TS1](#ts1-turnstile-site-key-missing-on-vercel) | `VITE_TURNSTILE_SITE_KEY` is not set on Vercel: the review form shows no security check | Shahriar (Vercel), whoever holds the Cloudflare widget | Guest review submission on the live site (likely) | **High** | **Open (7 Nov 2026), not yet confirmed by a submission** |
| [DOC1](#doc1-offline-frontend-guideline-section-1-is-out-of-date) | `Offline-Frontend-Guideline.md` section 1 status table is out of date | Muhtasim (document owner) | Nothing; misleads readers | Low | **Open (7 Nov 2026)** |

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

**Update, 7 November 2026: a recorded decision already covers most of this.** `Decisions.md`, 2026-10-19 (Frontend integration), row "Guest scope secret storage": *kept in `localStorage` until the IndexedDB draft store (R15) exists, then moved there.* The draft store now exists (R15 part 1, `frontend/src/offline/draftStore.ts`). Unless someone objects, the frontend will:
1. follow that decision with the guideline 4.3 approach: copy the secret into IndexedDB `meta` with the **same value**, keeping `localStorage` as the reader for now (so the guest tag cannot change);
2. give each draft its own copy of the secret when it is created (guideline 6.2, test D10);
3. update `Guest-Identity-and-Visits.md` to say so.

Please confirm or object. The same decision row also says *"the receipt is never stored"*. That is stricter than PF 13.5, PF 18.1 and guideline 6.5, which allow the receipt of an **unsent** draft to be stored with it until the server acknowledges the review. R15 part 1 does store it, and deletes it after a successful send. The frontend proposes amending the row to: "the receipt of an unsent draft is stored with that draft until the review is acknowledged; receipts of submitted reviews are never stored (PF 13.5)."

---

## DEP2: R13 offline packs are not on the live site

**Found 7 November 2026, in Chrome on the live site.** `abd` is 5 commits ahead of `main` (R13 steps A, B, C and their docs), and Vercel deploys `main`. On `https://abhijatri.vercel.app` the sidebar still says "Offline packs **Soon**", `/offline-packs` shows the old "Not available yet" page, and destination pages have no "Save for offline use" button. R12 itself is live and works.

**What to do.** Abdullah opens a pull request from `abd` to `main` (after committing R15 part 1, so it goes in the same deploy); Shahriar reviews and merges.

**Done when** the live sidebar shows "Offline packs" without "Soon" and a destination page shows "Save for offline use (… KB)". Then the testers can run guideline group P (and D1 to D4, D2, D16 for R15 part 1) on phones.

---

## TS1: Turnstile site key missing on Vercel

**Found 7 November 2026.** None of the 33 JavaScript files of the live site contains a Turnstile site key, and the live review form renders no security check. The widget appears only when `VITE_TURNSTILE_SITE_KEY` is set at build time (`frontend/src/components/reviews/TurnstileWidget.tsx`; `.env.example` says it is "required wherever the API runs with TURNSTILE_ENABLED=true (every production deploy)"). The production backend requires Turnstile (`app/config.py` refuses to start in production without `TURNSTILE_ENABLED`, `TURNSTILE_SECRET` and `TURNSTILE_HOSTNAME`).

**Likely effect.** Guest review submission on the live site fails with `403 CHALLENGE_FAILED` (no token is sent). **Not yet confirmed:** the frontend did not submit a real review to find out.

**How to confirm safely.** On the live site, open DevTools → Network, submit a short test review, and look at the `POST /api/v1/reviews/guest` answer. If it was accepted after all, withdraw it at once with its receipt on the Check with receipt page.

**What to do.** In Vercel → Project → Settings → Environment Variables, set `VITE_TURNSTILE_SITE_KEY` to the **site key** of the same Cloudflare Turnstile widget whose **secret** Railway uses (`TURNSTILE_SECRET`), with the widget's hostname matching `TURNSTILE_HOSTNAME` (`abhijatri.vercel.app`). Redeploy (the key is read at build time).

**Done when** the live review form shows the Cloudflare check, and a test review submits (then withdraw it).

---

## DOC1: Offline-Frontend-Guideline section 1 is out of date

`Docs/Offline-Frontend-Guideline.md` section 1 ("Where things stand") still says: IndexedDB "Not started", Offline packs page "Placeholder", offline drafts "Not started", R16 "In PR #39". Now: IndexedDB, packs and the Offline packs page are built (R13, `Frontend-Implemented.md` 5k, not yet deployed: DEP2); draft saving and the offline form are built (R15 part 1, 5l, uncommitted); R16 is live. Section 7 was already corrected on 7 November (GET instead of `curl -I`).

**What to do.** Muhtasim updates the table, or tells Abdullah to do it.

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
