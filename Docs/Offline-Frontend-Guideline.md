# Offline frontend guideline: finishing R13 and R15

**For:** Abdullah (frontend), with Muhtasim (API) and Irfan (R18 offline QA). **Date:** 6 November 2026.
**Goal:** finish the offline part of M1. R12 (installable app, opened pages stay readable) works. R13 (downloaded packs) and R15 (offline drafts) are not built. The backend they need, R14 and R16, is built.

**Sources:** Platform Foundation (PF) 13.5 and 18, Review.md (RV) 4, 5.1 and 7, Security.md 7.4, API.md 3, 5.2 and 5.23, Gantt R13 and R15. If this guide and a spec disagree, the spec wins; tell Muhtasim.

---

## 1. Where things stand

| Area | State | Where |
|---|---|---|
| App shell, precache (40 entries), update prompt | Done, live | `frontend/src/sw.ts`, `components/common/UpdatePrompt.tsx` |
| Opened destination pages and their reviews saved for 7 days | Done, live; checked in Chrome on 6 Nov | `sw.ts` `PUBLIC_API`, `offline/savedDestinations.ts` |
| Offline and server-down banners, not-saved states | Done, live | `components/common/StatusBanners.tsx`, `StatusViews.tsx` |
| Persistent storage request | Done, but the result is not shown to the user | `UpdatePrompt.tsx` |
| `Idempotency-Key` on review writes | Done; kept **in memory only** | `api/idempotency.ts`, `hooks/useIdempotencyKeys.ts` |
| Pack, manifest and freshness API (R14) | Built, CI green, in PR #37; **not merged, so 404 on the live API** | API.md 5.23 |
| Key replay API (R16) | Built and tested; migration `0022` is on the shared database; **code not deployed** | API.md 3 |
| IndexedDB | **Nothing yet**; no `indexedDB` use in `src/` | |
| Offline packs page | **Not built**; sidebar item `/offline-packs` is marked Soon | `components/layout/Sidebar.tsx` |
| Offline drafts | **Not built**; offline the reviews page says sending needs a connection | `pages/ReviewsPage.tsx` |

**Before you start:** Shahriar merges PR #37 and Railway redeploys. Until then, work locally against a backend running `backend-dev` (`npm run preview:offline`; `npm run dev` has no service worker).

---

## 2. Rules that must not be broken

1. IndexedDB holds only pack data, your own drafts (with the receipt of an unsent draft), the guest scope secret and the language preference (PF 18.1).
2. Never store sessions, auth responses, staff data, or anything marked `no-store`. Never cache `/api/v1/auth`, receipts, reports or notifications in the service worker.
3. Do not ignore `no-store` to make something work offline (Security 7.4).
4. An expired pack is never shown as current safety guidance. Label it (Security 7.4, PF 18.4).
5. Never pre-download map tiles (PF 18.3).
6. No background sync and no automatic submission. When the connection returns, show pending drafts and let the user submit (RV 7.3, API.md 5.2).
7. A draft stays on the device until the server acknowledges the review (RV 7.3).
8. Never tell the user storage is durable when `persist()` was refused (PF 18.2).
9. Everything visible works in Bangla and English, with Bangla digits in Bangla mode.

---

## 3. Shared foundation (do this first)

Add `src/offline/db.ts`, one small wrapper over IndexedDB. `idb` is a reasonable choice; it is not installed yet.

Database `abhijatri-offline`, version 1:

| Store | Key | Holds |
|---|---|---|
| `packs` | `destination_id` | The parsed pack, `pack_version`, `content_version`, `sha256`, `size_bytes`, `generated_at`, `expires_at`, `stale_after_days`, `downloaded_at`, `last_checked_at` |
| `drafts` | `client_draft_id` | See section 5.1 |
| `meta` | key | `guest_scope_secret`, `review_parameters` |

Requirements:
- Every call handles a missing or failing IndexedDB (private mode, quota, blocked storage). The app must not crash; say that saving is unavailable.
- Handle `QuotaExceededError` with a clear message and no partial pack.
- Move `getGuestScopeSecret()` from `localStorage` to `meta`, **keeping the existing value**. A new secret breaks draft recovery. The comment in `api/reviews.ts` already expects this.

Add a persistence display (PF 18.2): granted, refused or unknown, using `navigator.storage.persisted()` and `navigator.storage.estimate()`. If refused, warn that the browser may delete saved data.

---

## 4. R13: offline packs

**Gantt acceptance:** "Download/open/delete/freshness states work offline."

### 4.1 API

| Step | Call | Notes |
|---|---|---|
| Check | `GET /destinations/{id}/pack/manifest` | `public, max-age=60`, `ETag`, `304` |
| Download | `GET` the manifest's `pack_url` | Stored bytes, strong `ETag`, `Content-Digest`; about 12 KB for a seeded destination |
| Reconnect | `GET /packs/freshness?destination_id=..&destination_id=..` | 1 to 20 distinct ids; `AVAILABLE`, `WITHDRAWN` or `NOT_FOUND` |

Rate limits: 60, 20 and 30 a minute per network. Requests are `GET` with no credentials. Do not add these routes to the `sw.ts` allowlist; packs belong in IndexedDB only.

The fields differ from the proposal in `Handoff-Backend.md`: there is no `parts` and no `removed_review_ids`. Removals work because `content_version` changes when a review is hidden or withdrawn, and the device replaces the whole pack.

### 4.2 Download

1. Read the manifest and show `size_bytes` before downloading.
2. Fetch `pack_url` and read `arrayBuffer()`. **Hash the raw bytes, not re-serialized JSON.**
3. Compare `crypto.subtle.digest('SHA-256', bytes)` as lower-case hex with the manifest `sha256`. A mismatch is a failed download: keep the old pack.
4. Parse, then check `schema_version === 1`. An unknown version is a failed download.
5. Replace the stored pack in **one** IndexedDB transaction (FR14). Interrupting must leave the old pack intact.
6. Call `requestPersistentStorage()`.

`409 PACK_VERSION_SUPERSEDED` means a newer build appeared: read the manifest and retry once.

### 4.3 Update on reconnect

Run once when the app comes back online, and on app start while online. Call freshness with every stored id, in batches of 20.

| Answer | Action |
|---|---|
| `AVAILABLE`, `content_version` differs | Download again (4.2). Removals apply before the refreshed pack is shown as current. |
| `AVAILABLE`, same `content_version`, newer `pack_version` | Same content: download again to extend `expires_at`, or update the dates after a successful check of the new bytes |
| `AVAILABLE`, nothing changed | Update `last_checked_at` |
| `WITHDRAWN` (or `410 PACK_WITHDRAWN`) | Delete the pack and tell the user |
| `NOT_FOUND` | Remove the pack and tell the user it is no longer available |
| Network failure, `429`, `503` | Keep the pack; try later. Never delete on a failed check |

### 4.4 Reading offline

- Offline, the device recomputes each advisory state from its dates on the current **Asia/Dhaka** date, with the API.md 5.13 rules. `advisory_states` is only the state at build time. Do not trust it alone.
- Show the snapshot time and `advisories_verified_on` (RV 7.1).
- `reviews.items` media has no link. Show alt text or title and "Open when online" (RV 7.4).
- After `expires_at`, keep the pack but show it as out of date. Advisories must not appear current.

### 4.5 Pack states to show

`Not downloaded`, `Downloading`, `Download failed`, `Ready`, `Update available`, `Out of date` (past `expires_at`), `Withdrawn`.

Build `/offline-packs` and remove its Soon mark: list stored packs with size, snapshot time, state, Update and Delete, plus a storage summary. Add a Download button on the destination page.

**Decision needed (Abdullah and Muhtasim):** R12 saves every opened page, while Security 7.4 speaks of user-selected packs. Recommended: keep R12 as a convenience; when a page and a pack both exist, show the pack, and use a single saved-destinations list with no duplicates.

---

## 5. R15: offline drafts

**Gantt acceptance:** "Retry never creates duplicate review." Published-review edits stay online.

### 5.1 Draft record (RV 7.2)

| Field | Notes |
|---|---|
| `client_draft_id` | UUID, permanent for this draft |
| `receipt` | Generated once, before submission (PF 13.5) |
| `author` | `{ kind: 'guest' }` or `{ kind: 'member', user_id }` |
| `fields` | Destination and structured review fields, category ratings |
| `consent_version` | Revalidated at submission |
| `local_revision` | Increases on every local edit |
| `idempotency_key` | UUID; stored; renewed when `local_revision` changes |
| `state` | See 5.2 |
| `last_error`, `created_at`, `updated_at` | |

### 5.2 States

`DRAFT` → `READY` → `SUBMITTING` → `ACKNOWLEDGED`, or back to `READY` or `NEEDS_ATTENTION`. On app start, a draft left in `SUBMITTING` becomes `READY`; the retry is safe.

### 5.3 Making the form work offline

Today the form cannot do this:
- It reads `GET /review-parameters`, which is not cached. Store the last answer in `meta` (with its `version`) and ship a bundled fallback.
- The destination list comes from the network. Offline, offer saved destinations and packs.
- Save to `drafts` as the user types (debounced), including after a refresh.
- Show that drafts are not encrypted, with per-draft delete and clear-all (Security 7.4).
- Media is not part of offline drafts. Keep caption and filename where possible and ask the user to attach the file when online (RV 7.4).

### 5.4 Submitting after reconnect

Show pending drafts with a Submit button. Then:

1. Revalidate fields, consent version and that the destination is still published.
2. Use the stored `client_draft_id`, `receipt` and `idempotency_key`.
3. **Guests:** complete Turnstile now. It needs a connection, and a token is single use. The token is not part of the key's request, so a new token on retry is fine.
4. **Members:** check the session. If expired, keep the draft and ask for sign-in (RV 7.3).
5. Set `SUBMITTING` before sending; handle the answer below.

| Answer | Action |
|---|---|
| `201` | `ACKNOWLEDGED`, go to 5.5 |
| `200` with `duplicate_recovered: true` | An earlier attempt reached the server: same as `201` |
| `Idempotent-Replayed: true` | Same as the stored status |
| Network failure or timeout | Back to `READY`. **Keep the same key**; retry is safe |
| `409 IDEMPOTENCY_REQUEST_IN_PROGRESS` | Wait for `Retry-After`, retry with the same key |
| `409 IDEMPOTENCY_KEY_REUSED` | Should not happen; means a key bug. New key, `NEEDS_ATTENTION`, report it |
| `409 DRAFT_ALREADY_SUBMITTED` | Same draft id, different receipt. `NEEDS_ATTENTION`; the receipt is wrong, do not reuse this identity |
| `409 MEMBER_REVIEW_EXISTS` | `NEEDS_ATTENTION`; offer to change the visit month |
| `422 VALIDATION_FAILED` | `NEEDS_ATTENTION`; show the field errors |
| `403 CHALLENGE_FAILED` | Stay `READY`; run Turnstile again |
| `403 CSRF_INVALID` | `call()` already refetches and retries once |
| `401 AUTH_REQUIRED` | Stay `READY`; ask for sign-in |
| `403 ACCOUNT_RESTRICTED` | `NEEDS_ATTENTION`; show the server message |
| `404 NOT_FOUND` | `NEEDS_ATTENTION`; destination gone |
| `429 RATE_LIMITED`, `503` (including `GUEST_WRITES_PAUSED`) | Stay `READY`; honour `Retry-After` |

**A trap to design for:** `client_draft_id` is permanent. If a response was lost and the user edits the draft and submits again, the server returns the **first** stored review with `duplicate_recovered: true`; the edit is not applied. When the acknowledged content may differ from the local copy, tell the user the first version was received and offer to edit it with the receipt.

### 5.5 Receipt custody (PF 13.5)

1. After acknowledgement, show the receipt once. Offer copy, download and share.
2. When the user confirms, **or after 7 days**, delete the receipt from IndexedDB. Also delete the draft.
3. Explain that a lost receipt cannot be recovered and that a removal request exists.

Draft export excludes receipts of submitted reviews and includes an unsent receipt only on explicit confirmation (PF 18.2).

### 5.6 Sign-out

Sign-out clears session-derived state; public packs may stay (Security 7.4). **Decision needed:** what happens to a member's unsent drafts. Recommended: warn at sign-out, then delete or keep them; kept drafts show only to the same `user_id`.

---

## 6. Order of work

| # | Task | Depends on |
|---|---|---|
| 1 | Merge PR #37, deploy, confirm manifest answers on the live API | |
| 2 | `offline/db.ts`, scope-secret move, persistence display | |
| 3 | Pack download and verify, with tests | 2 |
| 4 | `/offline-packs`, Download and Delete buttons | 3 |
| 5 | Read from packs offline, advisory recomputation, Out of date state | 3 |
| 6 | Freshness on reconnect | 3 |
| 7 | Draft store, autosave, offline form | 2 |
| 8 | Pending list, Submit, answer table, receipt custody | 7 |
| 9 | Export, import, delete-all | 7 |
| 10 | R18: phone and airplane-mode tests | all |

---

## 7. Tests

**Unit (vitest):** hash match and mismatch; `schema_version` refusal; a failed replacement keeps the old pack; freshness actions; Dhaka-date advisory recomputation including the day boundary; expiry; every row of the 5.4 table; the same key across retries and a new key after an edit; `SUBMITTING` recovery at start; quota and missing-IndexedDB failures.

**Service worker:** confirm in Cache Storage that pack routes are not stored there (section 4.1).

**End to end in Chrome:** lost-response retry for a queued draft (a `fetch` wrapper that delivers the request and then fails it); offline with the DevTools Offline switch.

**Privacy:** Cache Storage and IndexedDB hold no session, auth, staff data or submitted receipts after a full run.

**Real device (R18):** Android Chrome and, if possible, iPhone Safari in airplane mode. `Handoff-Testing.md` has the R12 checklist; add pack and draft cases to it.

---

## 8. Definition of done

- [ ] R13 acceptance: download, open, delete and freshness states work offline
- [ ] R15 acceptance: no retry creates a duplicate review
- [ ] Interrupted download or a hash mismatch leaves the old pack intact
- [ ] Expired safety information never appears current
- [ ] Persistence status, draft-loss warning, export and delete are present
- [ ] Receipt deleted after confirmation or 7 days
- [ ] All new text in Bangla and English
- [ ] All CI jobs green; no ops code in the public bundle
- [ ] Sidebar Soon mark removed from Offline packs; `Handoff-Testing.md` known limits updated
- [ ] Real-phone airplane-mode test recorded

---

## 9. Open decisions

| Decision | Owner | Recommended |
|---|---|---|
| Maximum age, Decisions Step 8 | Project owners | Keep 7 days until measured; it is configuration |
| Pack and opened-page overlap (4.5) | Abdullah, Muhtasim | Pack wins; one list |
| Member drafts at sign-out (5.6) | Abdullah | Warn, then delete or keep |
