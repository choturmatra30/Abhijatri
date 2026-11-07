# Offline frontend guideline: finishing R13 and R15

**For:** Abdullah (frontend), with Muhtasim (API) and Irfan (R18 offline QA). **Date:** 6 November 2026.
**Goal:** finish the offline part of M1. A traveller with no signal can read a downloaded destination guide with its safety advisories, write a review, and send it later without ever creating a duplicate.

**How to use this document.** Work through sections 3 to 7 in order, using the task list in section 8. Section 9 has every test, including the manual test cases. Code blocks are starting skeletons, not finished or compiled code: adapt them to the codebase.

**Sources:** Platform Foundation (PF) 13.5 and 18, Review.md (RV) 4, 5.1 and 7, Security.md 7.4, API.md 3, 5.2 and 5.23, Gantt R13 and R15. If this guide and a spec disagree, the spec wins; tell Muhtasim.

---

## 1. Where things stand

| Area | State | Where |
|---|---|---|
| App shell, 40 precached entries, update prompt | Done, live | `frontend/src/sw.ts`, `components/common/UpdatePrompt.tsx` |
| Opened destination pages and reviews saved for 7 days | Done, live; checked in Chrome on 6 Nov | `sw.ts` `PUBLIC_API`, `offline/savedDestinations.ts` |
| Offline and server-down banners, not-saved states | Done, live | `components/common/StatusBanners.tsx`, `StatusViews.tsx` |
| Offline destination list | Done, live | `hooks/useDestinationCatalog.ts` |
| Persistent storage request | Done, but the result is not shown | `UpdatePrompt.tsx` |
| `Idempotency-Key` on review writes | Done in code, kept **in memory only** | `api/idempotency.ts`, `hooks/useIdempotencyKeys.ts` |
| Pack, manifest and freshness API (R14) | **Live** | API.md 5.23 |
| Key replay API (R16) | In PR #39; **live after that merge** | API.md 3 |
| IndexedDB | **Not started**; `src/` has no `indexedDB` use | |
| Offline packs page | **Placeholder**: `OfflinePacksPage.tsx` shows "not built yet"; the sidebar item is marked Soon | `pages/OfflinePacksPage.tsx`, `components/layout/Sidebar.tsx` |
| Offline drafts | **Not started**; offline, the reviews page shows an error state | `pages/ReviewsPage.tsx` |

**Backend readiness (audited on the live system, 6 Nov 2026).** No backend change is needed for R13 or R15. All 5 destinations downloaded through the website with `fetch` and WebCrypto: SHA-256, size, `schema_version` and versions all matched; freshness matched; no private fields and no media links in any pack. A `304` works despite gzip, a stale version gives `409`, an unknown id gives `404`. Median direct latency: manifest 0.43 s, pack 0.27 s. Not yet run inside a real browser with IndexedDB; that is task 3's first check.

**Release order:** merge PR #39 → confirm R16 live (section 7) → R13 → R15 → R18 phone tests. R15 depends on R13 (Gantt), and both depend on R16 being live.

---

## 2. Rules that must not be broken

1. IndexedDB holds only pack data, the user's own drafts (with the receipt of an unsent draft), the guest scope secret and the language preference (PF 18.1).
2. Never store sessions, auth responses, staff data or any response marked `no-store`. Never add `/auth`, receipts, reports, notifications or pack routes to the `sw.ts` allowlist.
3. Never work around `no-store` to make something work offline (Security 7.4).
4. An expired pack is never shown as current safety guidance. Label it (Security 7.4, PF 18.4).
5. Never pre-download map tiles (PF 18.3).
6. No background sync and no automatic submission. When the connection returns, show pending drafts and let the user submit (RV 7.3, API.md 5.2).
7. A draft stays on the device until the server acknowledges the review (RV 7.3).
8. Never tell the user storage is durable when `persist()` was refused (PF 18.2).
9. Everything visible works in Bangla and English, with Bangla digits in Bangla mode.
10. A failed check never deletes user data. Only a clear server answer does.

---

## 3. Architecture

```text
                 ┌──────────────── Browser ────────────────┐
  Network  ───►  │ Service worker (R12)                    │
                 │   app shell, opened pages, reviews      │
                 │ IndexedDB `abhijatri-offline` (new)     │
                 │   packs   drafts   meta                 │
                 │ React                                   │
                 │   offline/destinationSource.ts          │
                 │   picks the source for each screen      │
                 └─────────────────────────────────────────┘
```

**Which source wins:**

| Screen | Online | Offline or server down |
|---|---|---|
| Destination page | Network | Pack, then opened-page cache, then not-saved message |
| Destination reviews | Network | Pack snapshot, then opened-page cache |
| Destination list | Network | Packs plus opened pages, no duplicates |
| Review form | Network parameters | Stored parameters, then local fallback values |
| Receipt, account pages | Network only | Needs-connection message |

**Why a pack and an opened page both exist:** R12 saves what a user happens to open; a pack is a deliberate, verified download that holds more. Default: **keep both, and when both exist show the pack.** See section 10.

### New files

| File | Purpose |
|---|---|
| `src/api/packs.ts` | Manifest, pack bytes, freshness |
| `src/offline/db.ts` | Opens IndexedDB; the only file that touches it directly |
| `src/offline/packStore.ts` | Read, save, delete, list packs |
| `src/offline/packs.ts` | Download, verify, update |
| `src/offline/advisoryState.ts` | Recomputes advisory state from dates |
| `src/offline/packAdapter.ts` | Pack → `DestinationProfile` and `PublicReview` |
| `src/offline/destinationSource.ts` | Chooses pack, cache or network |
| `src/offline/parameters.ts` | Stored review parameters |
| `src/offline/draftStore.ts` | Read, save, delete drafts |
| `src/offline/submitDraft.ts` | Sends a draft and applies the answer table |
| `src/offline/storageStatus.ts` | Persistence and quota display data |
| `src/hooks/useOfflinePacks.ts`, `useDrafts.ts`, `useReconnect.ts` | React state over the stores |
| `src/components/offline/PackCard.tsx`, `PackDownloadButton.tsx`, `StorageStatus.tsx`, `PendingDrafts.tsx` | UI |

**New dependencies:** `idb@^8` (runtime, a thin promise wrapper), `fake-indexeddb@^6` (dev, for tests in the Node test environment).

---

## 4. Shared foundation

### 4.1 Types

Add to `src/types/index.ts`. These match `backend/app/schemas.py`.

```ts
export interface PackManifest {
  schema_version: number;
  destination_id: string;
  pack_version: number;
  content_version: string;
  sha256: string;
  size_bytes: number;
  generated_at: string;
  expires_at: string;
  max_age_seconds: number;
  stale_after_days: number;
  advisories_verified_on: string | null;
  languages: ('bn' | 'en')[];
  review_snapshot: { count: number; limit: number };
  pack_url: string;
}

export interface PackAdvisory extends Omit<Advisory, 'state'> {}

export interface PackMedia { id: string; kind: 'image' | 'video'; alt_text: string; caption: string | null }

export interface PackReview {
  id: string;
  author_type: 'GUEST' | 'MEMBER';
  guest_tag: string | null;
  author_display_name: string | null;
  overall_rating: number;
  category_ratings: CategoryRatings;
  published_at: string;
  title: string;
  body: string;
  media: PackMedia[];
}

export interface PackDocument {
  schema_version: number;
  destination_id: string;
  pack_version: number;
  content_version: string;
  generated_at: string;
  generated_on: string;
  expires_at: string;
  max_age_seconds: number;
  stale_after_days: number;
  advisories_verified_on: string | null;
  languages: ('bn' | 'en')[];
  destination: Omit<DestinationProfile, 'guide_items' | 'advisories' | 'contacts' | 'as_of' | 'stale_after_days' | 'last_updated'>;
  guide_items: GuideItem[];
  advisories: PackAdvisory[];
  advisory_states: { id: string; state: AdvisoryState }[];
  contacts: Contact[];
  reviews: { limit: number; count: number; items: PackReview[] };
}

export type PackFreshnessStatus = 'AVAILABLE' | 'WITHDRAWN' | 'NOT_FOUND';

export interface PackFreshnessItem {
  destination_id: string;
  status: PackFreshnessStatus;
  pack_version: number | null;
  content_version: string | null;
  sha256: string | null;
  size_bytes: number | null;
  generated_at: string | null;
  expires_at: string | null;
  pack_url: string | null;
}
```

Check the `Omit` on `destination` against `PackDestination` when you implement it: that block has `content_licence`, `content_verified_on`, `community_rating` and `guest_feedback` too.

### 4.2 IndexedDB

```ts
// src/offline/db.ts
import { openDB, type DBSchema, type IDBPDatabase } from 'idb';

export interface StoredPack {
  destination_id: string;
  pack: PackDocument;
  sha256: string;
  size_bytes: number;
  downloaded_at: string;
  last_checked_at: string | null;
  update_available: boolean;
}

export type DraftState = 'DRAFT' | 'READY' | 'SUBMITTING' | 'NEEDS_ATTENTION' | 'ACKNOWLEDGED';

export interface StoredDraft {
  client_draft_id: string;
  receipt: string;
  author: { kind: 'guest'; scope_secret: string; display_name: string } | { kind: 'member'; user_id: string };
  fields: DraftFields;              // destination, month, ratings, title, body, language
  consent_version: string;
  local_revision: number;
  idempotency_key: string;
  key_revision: number;             // the local_revision the key belongs to
  state: DraftState;
  last_error: string | null;
  review_id: string | null;         // set on acknowledgement
  acknowledged_at: string | null;
  created_at: string;
  updated_at: string;
}

interface OfflineDb extends DBSchema {
  packs: { key: string; value: StoredPack };
  drafts: { key: string; value: StoredDraft; indexes: { by_state: DraftState } };
  meta: { key: string; value: unknown };
}

export function openOfflineDb(): Promise<IDBPDatabase<OfflineDb>> {
  return openDB<OfflineDb>('abhijatri-offline', 1, {
    upgrade(db) {
      db.createObjectStore('packs', { keyPath: 'destination_id' });
      const drafts = db.createObjectStore('drafts', { keyPath: 'client_draft_id' });
      drafts.createIndex('by_state', 'state');
      db.createObjectStore('meta');
    },
  });
}
```

`meta` keys: `guest_scope_secret`, `review_parameters`.

**Failure handling.** Private mode, blocked storage, quota and a browser that lost the database all reject. Every store function catches this and returns an honest result such as `{ ok: false, reason: 'quota' | 'unavailable' }`. The app must keep working, and the UI says saving is unavailable. Handle `QuotaExceededError` separately so the message is "storage is full".

**Schema changes.** Bump the version and write a migration in `upgrade`. Never delete a store holding unsent drafts.

### 4.3 Move the guest scope secret

`getGuestScopeSecret()` in `api/reviews.ts` reads `localStorage`, and PF 18.1 places it in IndexedDB. Copy it to `meta` **keeping the existing value**. A new value would change the visitor's guest tag and break recovery of their reviews. `getGuestScopeSecret` is synchronous and is used in several places, so keep `localStorage` as the synchronous reader for now and write through to `meta`. This is a safe first step; a full async move is separate work.

### 4.4 Storage status (PF 18.2)

`offline/storageStatus.ts` returns `navigator.storage.persisted()` and `navigator.storage.estimate()`. Show on `/offline-packs`: persistence granted, refused or unknown, and space used. When refused, warn that the browser may delete saved data. `requestPersistentStorage()` already exists in `offline/savedDestinations.ts`; reuse it.

---

## 5. R13: offline packs

**Gantt acceptance:** "Download/open/delete/freshness states work offline." **Also:** request persistent storage.

### 5.1 API client

```ts
// src/api/packs.ts
import { API_BASE_URL, ApiError, apiRequest } from './client';

// `no-cache` skips the browser's own copy. It does not bypass Vercel's edge cache (section 5.1a).
export const getPackManifest = (id: string, signal?: AbortSignal) =>
  apiRequest<PackManifest>(`/api/v1/destinations/${encodeURIComponent(id)}/pack/manifest`, { cache: 'no-cache', signal });

// `destination_id` repeats, which the `params` option cannot express, so the query is built here.
export const getPackFreshness = (ids: string[], signal?: AbortSignal) => {
  const query = ids.map((id) => `destination_id=${encodeURIComponent(id)}`).join('&');
  return apiRequest<{ items: PackFreshnessItem[] }>(`/api/v1/packs/freshness?${query}`, { cache: 'no-cache', signal });
};

/** Raw bytes: the hash must cover exactly what the server sent, never re-serialized JSON. */
export async function fetchPackBytes(packUrl: string, signal?: AbortSignal): Promise<ArrayBuffer> {
  const response = await fetch(`${API_BASE_URL}${packUrl}`, { signal, cache: 'no-cache' });
  if (!response.ok) { /* parse the error body as apiRequest does and throw ApiError */ }
  return response.arrayBuffer();
}
```

`apiRequest` cannot be reused for the download because it parses JSON. Share its error parsing rather than copying it: export a small `toApiError(response)` from `client.ts`.

| Route | Limit | Notes |
|---|---|---|
| Manifest | 60 a minute per network | `304` on matching `If-None-Match` |
| Pack | 20 a minute per network | About 12 KB for a seeded destination; strong `ETag`, `Content-Digest` |
| Freshness | 30 a minute per network | 1 to 20 distinct ids; repeats are `422` |

### 5.1a What the live system does (measured)

- **Vercel caches these responses.** `public, max-age=60` is honoured at the edge: repeat requests answered `X-Vercel-Cache: HIT`. So a manifest, freshness answer or pack can be up to about 60 seconds old, whatever `cache` option the browser uses. That is the accepted public TTL, not a bug.
- **`ETag` arrives weak.** The server sends a strong `ETag`; the gzip step turns it into `W/"..."`. Do not compare `ETag` yourself; the server's `304` already handles it.
- **Hash what `fetch` gives you.** `arrayBuffer()` returns decoded bytes, and those are what `sha256` covers. Verified through gzip on all 5 packs.
- **A cold start can be slow.** One manifest plus pack took up to 20 s after idle, against under a second normally. Give a download its own deadline of about 30 s and one automatic retry. `READ_TIMEOUT_MS` (20 s) is too close.
- **Limits rarely trigger on the website.** Thirty downloads through the site by one user got no `429`, because traffic reaches the API from Vercel's addresses. Still handle `429`.

### 5.1b Contract notes

The response shape differs from the proposal in `Handoff-Backend.md`. There is **no `parts` and no `removed_review_ids`**. Removals work because `content_version` changes when a review is hidden or withdrawn, and the device replaces the whole pack.

### 5.2 Download and verify

```ts
// src/offline/packs.ts
const SCHEMA_VERSION = 1;

async function sha256Hex(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export async function downloadPack(id: string, signal?: AbortSignal, retried = false): Promise<void> {
  const manifest = await getPackManifest(id, signal);
  try {
    const bytes = await fetchPackBytes(manifest.pack_url, signal);
    if ((await sha256Hex(bytes)) !== manifest.sha256) throw new PackIntegrityError();
    const pack = JSON.parse(new TextDecoder().decode(bytes)) as PackDocument;
    if (pack.schema_version !== SCHEMA_VERSION) throw new PackFormatError();
    await savePack(pack, manifest);          // one transaction; the old pack stays until it commits
    await requestPersistentStorage();
  } catch (error) {
    if (!retried && error instanceof ApiError && error.code === 'PACK_VERSION_SUPERSEDED') {
      await delay(RETRY_AFTER_SUPERSEDED_MS); // the edge may still hold the old manifest (5.1a)
      return downloadPack(id, signal, true);
    }
    throw error;
  }
}
```

`RETRY_AFTER_SUPERSEDED_MS` is about 5 seconds. If the second attempt also gets `409`, a cached manifest is still pointing at the old build: show Download failed with Retry, and keep any old pack. It clears within about 60 seconds.

`crypto.subtle` needs a secure context. HTTPS and `localhost` work; plain `http://` over a local network does not, so test phones through the deployed site.

Show `size_bytes` before downloading. Keep the old pack on any failure.

### 5.3 Updating on reconnect

Create `hooks/useReconnect.ts`, mounted once near the app root. It runs when the `online` event fires and on app start while online, debounced so a flapping connection runs it once. Skip it when no packs are stored.

Call freshness with every stored id, in batches of 20, then:

| Answer | Action |
|---|---|
| `AVAILABLE`, `content_version` differs | `downloadPack`. Removals apply before the refreshed pack is shown as current |
| `AVAILABLE`, same content, newer `pack_version` | `downloadPack`: same content, later `expires_at` |
| `AVAILABLE`, nothing changed | Update `last_checked_at` |
| `WITHDRAWN`, or `410 PACK_WITHDRAWN` | Delete the pack and tell the user |
| `NOT_FOUND` | Remove the pack and tell the user it is no longer available |
| Network failure, `429`, `503` | Keep the pack; try on the next reconnect. Never delete on a failed check |

Download one at a time so a device with many packs stays under the limit of 20 a minute. On `429`, stop and honour `Retry-After`.

### 5.4 Advisory state offline

`advisory_states` is the state on the day the pack was built, and it goes stale. Always recompute on the current **Asia/Dhaka** date, with the API.md 5.13 rules.

```ts
// src/offline/advisoryState.ts
export const dhakaToday = (now = new Date()): string =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Dhaka' }).format(now); // YYYY-MM-DD

const daysBetween = (from: string, to: string) => (Date.parse(to) - Date.parse(from)) / 86_400_000;

export function advisoryState(a: PackAdvisory, today: string, staleAfterDays: number): AdvisoryState {
  if (today > a.valid_until) return 'EXPIRED';
  if (today < a.effective_on) return 'NOT_YET_EFFECTIVE';
  return daysBetween(a.provenance.verified_on, today) > staleAfterDays ? 'STALE' : 'CURRENT';
}
```

**Show only `CURRENT` and `STALE`.** The live route never returns the other two, and a pack holds advisories that start during its lifetime, so an upcoming one appears on its start date and an expired one disappears, with no network. Keep the code as dates: the device clock can be wrong, but nothing better exists offline.

### 5.5 Reading packs

```ts
// src/offline/packAdapter.ts
export function packToProfile(stored: StoredPack, today: string): DestinationProfile {
  const { pack } = stored;
  return {
    ...pack.destination,
    guide_items: pack.guide_items,
    contacts: pack.contacts,
    advisories: pack.advisories
      .map((a) => ({ ...a, state: advisoryState(a, today, pack.stale_after_days) }))
      .filter((a) => a.state === 'CURRENT' || a.state === 'STALE'),
    as_of: today,
    stale_after_days: pack.stale_after_days,
    last_updated: pack.generated_at,
  };
}

export const packReviewToPublic = (r: PackReview): PublicReview => ({
  ...r, status: 'PUBLISHED', media: [], // pack media has no link; pass r.media to the "Open when online" row
});
```

`stale_after_days` is at the top of the pack, not inside `destination`. `active_advisory_count` for the list uses the same recomputed result.

### 5.6 Plugging it in

**`pages/DestinationDetailPage.tsx`:** one line changes.

```ts
// before: getDestination(id, { signal })
// after:  loadDestination(id, { signal })
```

```ts
// src/offline/destinationSource.ts
export async function loadDestination(id: string, { signal }: { signal?: AbortSignal }) {
  const stored = await readPack(id);
  const usePackFirst = navigator.onLine === false;
  if (stored && usePackFirst) return { profile: packToProfile(stored, dhakaToday()), source: 'pack' as const, stored };
  try {
    return { profile: await getDestination(id, { signal }), source: 'network' as const, stored };
  } catch (error) {
    const kind = failureKind(error);
    if (stored && (kind === 'offline' || kind === 'timeout')) {
      return { profile: packToProfile(stored, dhakaToday()), source: 'pack' as const, stored };
    }
    throw error;
  }
}
```

Offline, reading the pack first avoids the 4-second service worker wait. Keep a `404` as a real not-found; do not hide it behind a pack. The page shows a banner when `source === 'pack'`: snapshot time, `advisories_verified_on`, and the Out of date label when past `expires_at`.

**`hooks/useDestinationCatalog.ts`:** merge `savedDestinations()` with stored packs, keyed by id, preferring the pack.

**`components/reviews/ReviewFeedSection.tsx`:** when the feed fails offline and a pack exists, show `pack.reviews.items` with the snapshot time (RV 7.1). Hide Load more and filters that need the server. Pack media has no link: show alt text or caption and "Open when online" (RV 7.4).

**`pages/OfflinePacksPage.tsx`:** replace the `FeatureUnavailable` placeholder. Remove `soon` from the `/offline-packs` item in `Sidebar.tsx`, and update the "Soon" on `LandingPage.tsx` if it refers to packs.

**Destination page:** add `PackDownloadButton`.

### 5.7 Pack states

| State | When | Shown as |
|---|---|---|
| Not downloaded | No stored pack | Download button with size |
| Downloading | In progress | Progress, Cancel |
| Download failed | Network, hash or format failure | Reason, Retry; any old pack remains |
| Ready | Stored, before `expires_at` | Snapshot time, Update, Delete |
| Update available | Last check found new content | Update |
| Out of date | Past `expires_at` | Label; advisories are not shown as current |
| Withdrawn | Server said so | Notice; pack removed |

Delete needs a confirmation and removes only that pack. Packs do not depend on sign-in: they hold no account data and may remain after sign-out (Security 7.4).

---

## 6. R15: offline drafts

**Gantt acceptance:** "Retry never creates duplicate review." **Also:** published-review edits stay online.

### 6.1 States

```text
DRAFT ──user finishes──► READY ──Submit──► SUBMITTING ──201/200──► ACKNOWLEDGED
                           ▲                    │
                           └── retryable ───────┤
                                                └── needs a change ──► NEEDS_ATTENTION
```

On app start, a draft left in `SUBMITTING` becomes `READY`. The retry is safe. These are device states; `LOCAL_DRAFT` in RV 5.1 is the review-level name for all of them.

### 6.2 Identity rules

These are what make "no duplicates" true. All are stored on the draft and survive a restart.

| Value | Rule |
|---|---|
| `client_draft_id` | Created once, never changes |
| `receipt` | Created once, before submission (PF 13.5) |
| `scope_secret` | **Copied from the device when the draft is created; never re-read** |
| `idempotency_key` | Created with the draft. **New key when `local_revision` changes**, same key for every retry of the same content |

**Trap 1: changing guest identity.** "Start as a new guest" (`startAsNewGuest`, `resetGuestScopeSecret`) replaces the scope secret. Server uniqueness is `(guest scope, client_draft_id)`, so sending an existing draft under the new scope looks like a new review. If a response was lost, that creates a **duplicate**. Always send the scope stored on the draft.

**Limit to design for: three new guest drafts a day per scope.** `guest_submit_per_scope_per_day` is 3, so a traveller who queued four reviews gets `429 RATE_LIMITED` on the fourth, with a long `Retry-After`. Retrying an already-sent draft is free. Keep the draft as `READY`, show when it can be sent, and never present this as a failure of the review.

**Trap 2: an edit after a lost response.** The server keeps the first version. If a response was lost and the user edits the draft and submits again, the answer is `200` with `duplicate_recovered: true` and the edit is **not applied**. When the local content may differ from what was first sent, say that the first version was received and offer to edit it with the receipt. Track this with `key_revision`.

The in-memory `hooks/useIdempotencyKeys.ts` stays for the receipt panel and member pages, which act online. Drafts use the stored key instead.

### 6.3 Making the form work offline

Today `pages/ReviewsPage.tsx` loads destinations first and shows `ErrorState` when that fails, so the form never appears offline. `GuestReviewForm.tsx` keeps its draft in `useState` and loses it on refresh.

1. **Destinations:** use `useDestinationCatalog` so offline the choice is saved destinations and packs. With none saved, explain that a guide must be saved first.
2. **Parameters:** `getReviewParameters()` already falls back to built-in values. Store the last answer in `meta` (`offline/parameters.ts`) and read it when the network fails, so limits and category prompts stay current.
3. **Autosave:** debounce about 500 ms into `drafts`, and restore on return. Bump `local_revision` on each saved change.
4. **Turnstile:** do not render the widget offline. Show a note that the security check runs when sending.
5. **Disclosure:** state that drafts are stored unencrypted on the device, with per-draft Delete and Clear all (Security 7.4).
6. **Media:** offline drafts are text only. Keep the intended caption and filename where possible, and ask the user to attach the file when online (RV 7.4).
7. **Editing:** published reviews stay online only; never offer an offline edit of one (RV 7.3).

### 6.4 Submitting after reconnect

`components/offline/PendingDrafts.tsx` lists `READY` and `NEEDS_ATTENTION` drafts. Show it on the reviews page, with a count in the banner when the connection returns. Nothing is sent until the user presses Submit.

```ts
// src/offline/submitDraft.ts  (outline)
export async function submitDraft(draft: StoredDraft, turnstileToken: string | null) {
  await assertStillValid(draft);                  // fields, consent version, destination published
  const key = draft.key_revision === draft.local_revision ? draft.idempotency_key : await renewKey(draft);
  await setState(draft, 'SUBMITTING');
  const payload = toPayload(draft);               // uses the draft's own scope secret and receipt
  try {
    const created = draft.author.kind === 'guest'
      ? await submitGuestReview({ ...payload, turnstile_token: turnstileToken ?? undefined }, key)
      : await submitMemberReview(toMemberPayload(payload), key);
    return acknowledge(draft, created);
  } catch (error) {
    return applyFailure(draft, error);            // the table below
  }
}
```

Before sending: guests complete Turnstile (a token is single use and is not part of the key's request); members check the session and, if it expired, keep the draft and ask for sign-in (RV 7.3). Consent is checked against `CONSENT_VERSION`; if it changed, ask for consent again.

| Answer | State | User sees |
|---|---|---|
| `201` | `ACKNOWLEDGED` | Receipt panel (6.5) |
| `200`, `duplicate_recovered: true` | `ACKNOWLEDGED` | Receipt panel; note if the local copy differs (Trap 2) |
| `Idempotent-Replayed: true` | Same as the stored status | Same |
| Network failure, timeout | `READY`, **same key** | "Could not send. Your draft is safe." |
| `409 IDEMPOTENCY_REQUEST_IN_PROGRESS` | `READY` | Wait `Retry-After`, then retry with the same key |
| `409 IDEMPOTENCY_KEY_REUSED` | `NEEDS_ATTENTION`, new key | A bug in the key rules: log the `request_id` |
| `409 DRAFT_ALREADY_SUBMITTED` | `NEEDS_ATTENTION` | Same draft id, different receipt: this identity is spent |
| `409 MEMBER_REVIEW_EXISTS` | `NEEDS_ATTENTION` | Offer to change the visit month |
| `409 RESERVED_DISPLAY_NAME` | `NEEDS_ATTENTION` | Field error on the name |
| `422 VALIDATION_FAILED` | `NEEDS_ATTENTION` | Field errors |
| `422 INVALID_RECEIPT_FORMAT` | `NEEDS_ATTENTION` | Should not happen; log it |
| `403 CHALLENGE_FAILED` | `READY` | Run the security check again |
| `403 CSRF_INVALID` | Handled | `call()` refetches and retries once |
| `401 AUTH_REQUIRED` | `READY` | Ask for sign-in |
| `403 ACCOUNT_RESTRICTED`, `EMAIL_NOT_VERIFIED` | `NEEDS_ATTENTION` | Server message |
| `404 NOT_FOUND` | `NEEDS_ATTENTION` | Destination no longer available |
| `429 RATE_LIMITED` | `READY` | Honour `Retry-After`; say when it can be sent (daily draft limit in 6.2) |
| `503 GUEST_WRITES_PAUSED`, `SERVICE_UNAVAILABLE` | `READY` | Try later |

Branch on `code`, never on `message`. Set `SUBMITTING` **before** sending, so a crash mid-send is recovered as a retry. Disable Submit while sending so one tap is one attempt.

### 6.5 Receipt custody (PF 13.5)

`ReceiptPanel.tsx` keeps the receipt in memory, which is right for an online submit. For a queued draft:

1. After acknowledgement, show the receipt once and offer copy, download and share. Warn that a lost receipt cannot be recovered and that a removal request exists.
2. When the user confirms, **or after 7 days**, delete the draft and its receipt. Run the 7-day cleanup on app start.

### 6.6 Export, import, delete (PF 18.2)

- Export a JSON file of unsent drafts.
- Exclude receipts of submitted reviews. Include an unsent draft's receipt **only after explicit confirmation**, because it is needed to send that draft later.
- Import where practical; reject a file that fails validation, and never overwrite a newer local draft with the same id.
- Per-draft delete and Clear all, each with a confirmation.
- Show a draft-loss warning when persistence was refused.

### 6.7 Sign-out

Sign-out clears session-derived state; public packs may stay (Security 7.4). Default: warn when unsent member drafts exist, then let the user keep or delete them. Kept member drafts show only to the same `user_id`. See section 10.

---

## 7. R16 release check

Do this once PR #39 is merged and deployed.

```bash
curl -s -D - -o /dev/null -H "Origin: https://abhijatri.vercel.app" https://abhijatri-backend.up.railway.app/api/v1/health | grep -i expose-headers
```

It must print `Idempotent-Replayed, Retry-After`. Then run test group R in section 9.

**Use GET, not `curl -I`.** `-I` sends a HEAD request, which this API answers with `405` and `no-store`, so header checks made with it are wrong (that is how B5 in `Handoff-Backend.md` was raised by mistake). Corrected 7 November 2026; on that date this check passed on the live API: `access-control-expose-headers: Idempotent-Replayed, Retry-After`.

**What the frontend already does:** one key per user action, reused on retry, renewed when the request changes (`api/idempotency.ts`), on guest and member submit, edit, withdraw and guest appeal. No further work is needed for those. The limit is that the key lives in memory, so a page refresh loses it; R15 fixes this for drafts.

---

## 8. Task plan

Points follow the Gantt: R13 is 6, R15 is 5. Keep each row one small pull request.

| # | Task | Files | Pts | Needs | Done when |
|---|---|---|---|---|---|
| 1 | Add `idb`, `fake-indexeddb`, types, `db.ts` with failure handling | `types`, `offline/db.ts` | 0.5 | PR #39 | Store tests pass, including storage unavailable |
| 2 | Scope secret write-through, storage status | `api/reviews.ts`, `storageStatus.ts` | 0.5 | 1 | Existing guest tag unchanged |
| 3 | API client, download, verify, replace | `api/packs.ts`, `packStore.ts`, `packs.ts` | 1.5 | 1 | Bad hash keeps the old pack |
| 4 | Advisory recomputation and adapter | `advisoryState.ts`, `packAdapter.ts` | 1 | 1 | Day-boundary tests pass |
| 5 | Read packs on detail, list and reviews | `destinationSource.ts`, detail page, `useDestinationCatalog`, `ReviewFeedSection` | 1 | 3, 4 | Pack opens in airplane mode |
| 6 | Packs page, states, Delete, sidebar | `OfflinePacksPage.tsx`, components | 1 | 3 | P group passes |
| 7 | Reconnect freshness | `useReconnect.ts` | 0.5 | 3 | Hidden review disappears after reconnect |
| 8 | Draft store, autosave, restore | `draftStore.ts`, `GuestReviewForm.tsx` | 1 | 1 | A draft survives a restart offline |
| 9 | Offline form | `ReviewsPage.tsx`, `parameters.ts` | 1 | 5, 8 | The form opens with no connection |
| 10 | Pending list, Submit, answer table | `submitDraft.ts`, `PendingDrafts.tsx` | 2 | 8, R16 live | Retry test creates one review |
| 11 | Receipt custody, export, delete | `ReceiptPanel.tsx`, components | 1 | 10 | Receipt gone after 7 days |
| 12 | Phone tests, docs | `Handoff-Testing.md`, `Frontend-Implemented.md` | | all | Section 11 complete |

**Suggested pull requests:** A (1, 2), B (3, 4), C (5, 6, 7), D (8, 9), E (10, 11).

---

## 9. Tests

### 9.1 Automated

The Vitest setup runs in Node with no DOM, so test logic in plain modules, using `fake-indexeddb/auto`.

| Module | Must cover |
|---|---|
| `packs.ts` | Hash match and mismatch; unknown `schema_version`; a failed save keeps the old pack; `409` retries once |
| `packStore.ts` | Save, read, delete; replacing is one transaction; quota and unavailable storage |
| `advisoryState.ts` | Each state; the first and last valid day; a time just before and after midnight Dhaka, when the UTC date differs |
| `packAdapter.ts` | Expired and upcoming hidden; `stale_after_days` read from the top level |
| `useReconnect` logic | Each row of table 5.3; a failed check deletes nothing |
| `draftStore.ts` | Autosave, `local_revision`, `SUBMITTING` recovery at start |
| `submitDraft.ts` | **Every row of table 6.4**; same key on retry; new key after an edit; a stored scope is sent after a scope reset; refused Turnstile keeps the draft |
| Receipt custody | Deleted on confirm, and after 7 days; not before |
| Export | Submitted receipts excluded; unsent receipt only with confirmation |

Add `npm audit` to your routine: CI now fails on moderate or above. The one remaining `deepmerge` advisory is low, is build-time only, and has no upstream fix.

### 9.2 How to test with no internet

- **Use the deployed site, `https://abhijatri.vercel.app`.** With Wi-Fi off, `localhost` still reaches your own server, so nothing is truly offline.
- **On a laptop:** turn Wi-Fi off and unplug any cable. DevTools → Network → Offline is a quick alternative.
- **On a phone:** airplane mode, with Wi-Fi and mobile data both off.
- **Server down with internet on:** on localhost, stop the backend.
- **Start fresh:** DevTools → Application → Storage → Clear site data, while online.
- **Slow network:** DevTools → Network, custom profile 400 kbps both ways, 400 ms latency.
- **`npm run dev` has no service worker.** Use `npm run preview:offline`.
- The site opens in Bangla; press **English** to match the text below. For each case record device, browser, pass or fail, and a screenshot of any failure.

### 9.3 Available now: O group (R12)

**Setup, with internet on:**
1. Open the site and wait for the "ready for offline" notice, then press OK.
2. Open **Destinations**, then **Bandarban**.
3. Wait until the page loads, then scroll down to the reviews.
4. Turn off Wi-Fi and mobile data, or use airplane mode on a phone.

| # | Steps (no internet) | Expected |
|---|---|---|
| O1 | Reload the Bandarban page | Page opens, not the browser's "no internet" page. A banner starts "You are offline." |
| O2 | Scroll through Bandarban | Advisories, restrictions and emergency contacts all show |
| O3 | Open **Destinations** | Only Bandarban, with "You are offline. Showing the 1 destination(s) saved on this device" |
| O4 | Open the home page and **Overview** | Both open and only Bandarban appears; Overview hides the site-wide count tiles |
| O5 | Search "zzzz" in Destinations | "No destination matches…" with Clear search |
| O6 | Type the address of a destination you never opened, for example `/destinations/a3933bfe-c594-5826-ac28-f889ab588737` | "This destination is not saved on this device…", never "Something went wrong" |
| O7 | Press **Write a review** | "Sending a review needs a connection. Come back here when you are online." (replaced by D group after R15) |
| O8 | Open **Receipt** and check a status | "You are offline. Try again when your connection is back." No crash |
| O9 | If signed in, open **My reviews** and Notifications | A needs-connection message, not a sign-in page |
| O10 | Look at images on the home page and any review photos | No broken-image icons. Panels are dark; review photos say they show when back online |
| O11 | Switch language and theme, then reload | Both are kept |
| O12 | Close the browser fully, reopen it and open Bandarban | It still opens |
| O13 | Leave it offline for a few hours, then reopen | It still opens |
| O14 | Reconnect | "Back online…" banner; all 5 destinations return |

| # | Steps | Expected |
|---|---|---|
| O15 | Online: Clear site data. Reload, wait for the notice, open no destination. Go offline, open Destinations | "No destinations saved on this device" and how saving works |
| O16 | Online, open two destinations, go offline, open Destinations | Exactly those two, and the count says 2 |
| O17 | Phone: install the app, open Bandarban, airplane mode, force-close, reopen from the home screen | Opens full screen with Bandarban readable |
| O18 | Online, sign in and use account pages, then DevTools → Application → **Cache Storage** | No URL contains `session`, `account`, `receipt`, `notification`, `report` or `guest` |
| O19 | Leave a saved page unopened online for 7 days, then open it offline | No longer offered (long-running, optional) |

### 9.4 After R13: P group

| # | Steps | Expected |
|---|---|---|
| P1 | Online, open a destination | Download button shows the size |
| P2 | Download it | State goes Downloading → Ready; appears on `/offline-packs` |
| P3 | Go offline, reload, open it | Full guide opens with no 4-second wait; snapshot time and "verified on" date show |
| P4 | Offline, open the reviews | Up to 20 published reviews; media shows "Open when online"; no filters needing the server |
| P5 | Offline, open `/offline-packs` | The pack lists with size, snapshot time, state and storage status |
| P6 | Delete the pack, offline | Confirmation, then gone; other packs remain |
| P7 | Download with the connection dropped midway | Download failed, Retry; an older pack stays intact |
| P8 | Online: fake a bad hash by editing the manifest answer in a test build | Refused; old pack intact |
| P9 | Hide a review as staff, wait a minute, reconnect | Review disappears before the pack shows as current |
| P10 | Archive a destination as staff, reconnect | Pack removed with a notice |
| P11 | Advisory ending today: open offline, then set the device date to tomorrow | Disappears the next Dhaka day, with no network |
| P12 | Set the device date past `expires_at`, open offline | Labelled out of date; advisories not shown as current |
| P13 | Fill the device storage, download | "Storage is full"; no crash; old packs intact |
| P14 | Private window, download | Honest "saving unavailable"; site still works |
| P15 | Sign out | Public packs remain; no account data left |
| P16 | Phone: download, airplane mode, restart the phone, reopen | Pack opens |

### 9.5 After R15: D group

| # | Steps | Expected |
|---|---|---|
| D1 | Offline, open Write a review | The form opens; only saved destinations are offered |
| D2 | Offline, with nothing saved | Explains a guide must be saved first |
| D3 | Type a draft, reload offline | Text is restored |
| D4 | Close the app, restart the device, reopen offline | Draft still there, not sent |
| D5 | Reconnect | Pending draft is listed with a count; **nothing is sent automatically** |
| D6 | Submit as a guest | Security check, then the receipt once; the draft leaves the list |
| D7 | Lose the connection during Submit, then Submit again | Exactly one review; recovered message |
| D8 | Submit twice quickly | One attempt, one review |
| D9 | Force-close during Submit, reopen | Draft back to ready; retry creates one review |
| D10 | Press "Start as a new guest" with a draft unsent, then submit | Sent under its original scope; one review |
| D11 | Lose the response, edit the draft, submit | Told the first version was received; offered edit with the receipt |
| D12 | Member with an expired session | Draft kept; sign-in asked; then it sends |
| D13 | Member, month already reviewed | Asked to change the month; draft kept |
| D14 | Submit a draft with an invalid field | Field error shown; draft kept |
| D15 | Destination archived while offline | Clear message; draft kept until deleted |
| D16 | Delete one draft; Clear all | Each asks first; gone from IndexedDB |
| D17 | Export with and without the receipt option | Receipt only with confirmation; no submitted receipts |
| D18 | Confirm you saved the receipt | Receipt gone from IndexedDB |
| D19 | Do not confirm, set the device date 8 days ahead, reopen | Receipt deleted |
| D20 | Sign out with unsent member drafts | Warned; keep or delete; others cannot see them |
| D21 | Phone: airplane mode, write, restart, reconnect, submit | One review |
| D22 | Queue four guest drafts offline, reconnect, submit all | Three send; the fourth stays ready and says when it can be sent |

### 9.6 After PR #39 is live: R group

This needs internet. To lose a response on purpose, paste this in the DevTools Console. The next matching request reaches the server, then the browser reports a failure.

```js
const realFetch = window.fetch; let lose = 1;
window.fetch = async (url, init) => {
  const response = await realFetch(url, init);
  if (lose > 0 && init?.method && init.method !== 'GET' && /reviews|review-receipts/.test(String(url))) {
    lose -= 1; throw new TypeError('simulated lost response');
  }
  return response;
};
```

| # | Steps | Expected |
|---|---|---|
| R1 | Run the snippet, submit a guest review, press Submit again | Connection error first; then the same review with the receipt. One review in My reviews or by receipt |
| R2 | Open the receipt panel, run the snippet, edit, press Save again | "Saved"; not "already changed"; Network shows `Idempotent-Replayed: true` |
| R3 | Same with withdraw | Withdrawn, with the same marker |
| R4 | Network tab | `Idempotency-Key` on each write; the same value on a retry |
| R5 | Change the text after a failed save, save again | A new key; no `409 IDEMPOTENCY_KEY_REUSED` |
| R6 | Register or reset with `password123` | "This password appears in a known data breach." The reset link still works |

### 9.7 Privacy audit (must pass)

After a full run, check DevTools → Application:

- **Cache Storage:** no session, account, receipt, notification, report or guest URL; no pack routes.
- **IndexedDB:** only `packs`, `drafts` and `meta`. No tokens, no submitted receipts, no staff data.
- **After sign-out:** no session-derived data.

---

## 10. Open decisions

Each has a default so the work is not blocked.

| Decision | Owner | Default used here |
|---|---|---|
| Maximum age, Decisions Step 8 | Project owners | 7 days; it is configuration |
| Pack and opened-page overlap: Security 7.4 speaks of user-selected packs, and R12 saves every opened page | Abdullah, Muhtasim | Keep both; the pack wins; one list |
| Member drafts at sign-out | Abdullah | Warn, then keep or delete |

**Out of M1 scope:** the tour-chat offline queue in `Features/Verified Users Interface.md` 14.2. When that work starts, reuse `offline/db.ts` with a new store rather than a second database.

---

## 11. Definition of done

- [ ] PR #39 merged; section 7 check passes; R group passes
- [ ] R13 acceptance: download, open, delete and freshness states work offline
- [ ] R15 acceptance: no retry creates a duplicate review (D7, D8, D9, D10)
- [ ] An interrupted download or a hash mismatch leaves the old pack intact
- [ ] Expired safety information never appears current (P11, P12)
- [ ] Persistence status, draft-loss warning, export and delete are present
- [ ] Receipt deleted after confirmation or 7 days
- [ ] All new text in Bangla and English; Bangla digits in Bangla mode
- [ ] Privacy audit passes
- [ ] All CI jobs green; no ops code in the public bundle
- [ ] Sidebar Soon mark removed; `Handoff-Testing.md` known limits and `Frontend-Implemented.md` updated
- [ ] Real-phone airplane-mode tests recorded (O17, P16, D21)
