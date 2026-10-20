# Abhijatri API Contract (v1)

**Status:** Approved target contract, 18 October 2026. **Contract version:** `1.0.0-draft` (`info.version` stays `0.1.0` until the first frontend integration).

**Sources:** `Docs/Platform-Foundation.md` (PF) sections 5.3, 12, 13, 14 and 16; `Features/Review.md` (RV) sections 4, 5, 9; `Docs/Security.md` 7.1. Where this document and those sources differ, the sources win and this document is corrected.

**Snapshot:** `Docs/api/openapi-v1.json` is the machine-readable snapshot of the routes in code. CI fails if it drifts. Regenerate with `cd backend && uv run python scripts/export_openapi.py`.

**Status labels used below:**

| Label | Meaning |
|---|---|
| Implemented | In code and matches this contract. |
| Change required | In code, but differs from this contract. Section 6 lists the differences. |
| Planned | Not in code. Built by the task named in the table. |

## 1. Conventions

| Topic | Rule | Source |
|---|---|---|
| Base path | `/api/v1`. Additive fields and endpoints stay in v1. Breaking changes need `/api/v2` or a managed compatibility period recorded in `Decisions.md`. | PF 12.1 |
| Format | JSON, UTF-8. Identifiers are UUIDs. Timestamps are UTC ISO-8601. Name fields are NFC-normalised. | PF 11 |
| Errors | Section 2. Clients branch on `code`, never on `message`. | PF 12.3 |
| Concurrency | Every mutation of a review sends `expected_version`. A stale value returns `409 REVIEW_VERSION_CONFLICT`. | RV 6.1 |
| Pagination | Opaque `after` cursor over `(published_at, id)` descending. `limit` 1 to 50, default 20. `next_cursor` is `null` on the last page. Cursors are not reused across sort orders. | RV 9.3 |
| Idempotency | Section 3. | PF 12.4 |
| Caching | Every response is `Cache-Control: no-store` unless the route is marked Public in Section 4. | Security 7.1, PF 16.4 |
| Language | `message` in errors is Bangla or English, chosen by `Accept-Language`. Bangla is the default. | PF 12.3 |
| Secrets | Receipt and guest scope secrets travel only in JSON request bodies. They never appear in URLs, fragments, cookies, headers, logs, analytics or error bodies. | PF 13.3, 13.4 |

### 1.1 Credentials

| Credential | Used by | How it is sent |
|---|---|---|
| None | Public reads, health | Nothing. Public `GET` routes are CORS simple requests: no custom headers, no credentials. |
| Guest scope secret | Guest submission | `guest_scope_secret` in the body. Supplemental signal only, not an abuse boundary (PF 14.1). |
| Guest receipt | Receipt operations | `receipt_secret` in the body (Section 5.1). |
| Member session | Member endpoints | Cookie `__Host-abhijatri_session` (`SameSite=Lax`) plus `X-CSRF-Token` on writes. |
| Staff session | `/staff/*` | Cookie `__Host-abhijatri_staff_session` (`SameSite=Strict`) plus `X-CSRF-Token` on writes. Member sessions never authorise staff routes and staff sessions never authorise member routes. |

Both cookies are host-only on `api.<owned-domain>`, `Secure`, `HttpOnly`, `Path=/`, with no `Domain` attribute (PF 5.3). No receipt cookie exists.

Until the staff authentication adapter lands (R04), staff routes accept the development-only `X-Test-Staff-Id` header when `APP_ENV` is `development` or `test`, and return `501 STAFF_AUTH_NOT_CONFIGURED` in production.

### 1.2 CORS and CSRF

| Setting | Value (PF 16.1) |
|---|---|
| Allowed origins | `https://app.<owned-domain>`, `https://admin.<owned-domain>`. Never a wildcard. |
| `allow_credentials` | `true` |
| Allowed methods | Only those routes use: `GET`, `POST`, `PUT`, `PATCH` |
| Allowed request headers | `Content-Type`, `Idempotency-Key`, `X-CSRF-Token`, `Accept-Language` |
| Preflight cache | 600 seconds |

CSRF uses a synchronizer token (PF 16.2). `GET /auth/csrf` returns `{ "csrf_token": "..." }` for the current session. Every state-changing cookie-authenticated request sends it in `X-CSRF-Token`. Guest submission and receipt endpoints use no cookies and need no CSRF token.

## 2. Error format

Every error, including validation errors, uses one shape (PF 12.3). FastAPI's default `{"detail": ...}` and default 422 bodies are replaced by exception handlers.

```json
{
  "error": {
    "code": "REVIEW_VERSION_CONFLICT",
    "message": "এই রিভিউটি ইতিমধ্যে পরিবর্তিত হয়েছে।",
    "request_id": "8d1f5a0e-2c7b-4c55-9b0f-0a3e2f6b1c44",
    "field_errors": []
  }
}
```

`field_errors` is a list of `{ "field": "...", "code": "..." }` and is empty when not a validation error. The `X-Request-ID` response header carries the same `request_id`. Errors never contain stack traces, SQL, secrets, internal paths, or whether an account exists.

| HTTP | `code` | When |
|---|---|---|
| 401 | `AUTH_REQUIRED` | Missing or invalid session. |
| 403 | `FORBIDDEN` | Authenticated but not permitted. |
| 403 | `SELF_MODERATION_FORBIDDEN` | A moderator acts on their own review. |
| 403 | `CSRF_INVALID` | Missing or wrong `X-CSRF-Token`. |
| 403 | `CHALLENGE_FAILED` | Turnstile token missing, expired, reused or invalid. |
| 404 | `NOT_FOUND` | Route, destination or review does not exist. |
| 404 | `RECEIPT_NOT_FOUND` | Receipt does not match the review. Same response as a missing review, so existence is not leaked. |
| 409 | `REVIEW_VERSION_CONFLICT` | `expected_version` is stale. |
| 409 | `INVALID_TRANSITION` | The decision is not allowed from the current state. |
| 409 | `DRAFT_ALREADY_SUBMITTED` | Duplicate draft with a different receipt (Section 5.2). |
| 409 | `RESERVED_DISPLAY_NAME` | Display name is reserved (for example `Admin`, `Moderator`). |
| 409 | `IDEMPOTENCY_KEY_REUSED` | Same `Idempotency-Key` with a different request body. |
| 409 | `DUPLICATE_OPEN_REPORT` | The same scope already has an open report on this review. |
| 409 | `APPEAL_WINDOW_CLOSED` | Appeal sent after the 30-day window. |
| 413 | `PAYLOAD_TOO_LARGE` | Request body exceeds the configured limit. |
| 422 | `VALIDATION_FAILED` | Schema validation failed; see `field_errors`. |
| 422 | `INVALID_CURSOR` | `after` cannot be decoded. |
| 422 | `INVALID_RECEIPT_FORMAT` | Receipt is not `abr1_` plus 43 base64url characters, or is a known weak value. |
| 429 | `RATE_LIMITED` | A limit in Section 7 was hit. `Retry-After` is set. |
| 503 | `GUEST_WRITES_PAUSED` | Pending ceiling reached or emergency switch on (PF 14.3, 14.6). Public reads continue. |
| 500 | `INTERNAL_ERROR` | Unexpected failure. |
| 501 | `STAFF_AUTH_NOT_CONFIGURED` | Staff route in production before R04. |
| 503 | `SERVICE_UNAVAILABLE` | Database unavailable or pool exhausted. `Retry-After` is set. |
| 504 | `REQUEST_TIMEOUT` | Request exceeded the server timeout. |

## 3. Idempotency

Retryable writes accept `Idempotency-Key: <UUID>` (PF 12.4).

- The server stores a digest of the key scoped by actor or guest scope, the endpoint, a request fingerprint, a result reference, the creation time and an expiry 72 hours later.
- A unique constraint on (scope, endpoint, key digest) enforces uniqueness.
- The same key with the same body returns the stored response. The same key with a different body returns `409 IDEMPOTENCY_KEY_REUSED`.
- Idempotency only replays recent responses. Permanent duplicate prevention for reviews is the `client_draft_id` uniqueness in RV 4.1.

## 4. Endpoints

### 4.1 Platform

| Method and path | Credential | Cache | Status |
|---|---|---|---|
| `GET /health` (also `HEAD`) | none | no-store | Implemented |
| `GET /health/ready` (also `HEAD`) | none | no-store | Change required |
| `GET /auth/csrf` | member or staff session | no-store | Planned (R04) |
| `POST /guest-visits` | guest scope (no cookie, no name) | no-store | Implemented 20 Oct 2026 (section 5.14) |
| `GET /guest-visits/stats` | none | Public, short TTL | Implemented 20 Oct 2026 (section 5.14) |

`/health` returns `{ "status": "ok" }`. `/health/ready` checks the database and returns `503 SERVICE_UNAVAILABLE` if it is down. It must also report the deployed build and the database migration revision, because the deploy workflow polls it for both (PF 22.1):

```json
{ "status": "ok", "build": "82ecb52", "db_revision": "0002" }
```

### 4.2 Guest reviews and receipts

| Method and path | Credential | Cache | Status |
|---|---|---|---|
| `POST /reviews/guest` | guest scope + receipt + Turnstile | no-store | Change required: only `Idempotency-Key` replay (order-of-checks step 3, WP4) is pending. Client receipt, `201`/`200`, `409`, Turnstile, durable limits, ceilings and the emergency switch are done (WP3, WP5). |
| `POST /review-receipts/status` | receipt | no-store | Implemented (WP3). Replaced the legacy `POST /review-receipts/exchange`, which is removed. |
| `POST /reviews/{review_id}/withdraw` | receipt | no-store | Implemented (WP3, WP5 receipt limits). Idempotency-Key replay is added with WP4. |
| `PATCH /reviews/{review_id}/pending` | receipt or owner | no-store | Planned (R07) |
| `POST /review-receipts/appeals` | receipt | no-store | Planned (R07) |

### 4.3 Public reads

| Method and path | Credential | Cache | Status |
|---|---|---|---|
| `GET /destinations/{destination_id}/reviews` | none | Public, short TTL | Implemented (error body aside) |
| `GET /destinations` | none | Public, short TTL | Implemented (R02) |
| `GET /destinations/{destination_id}` | none | Public, short TTL | Implemented (R02) |
| `GET /destinations/{destination_id}/pack/manifest` | none | Public, versioned | Planned (R14) |
| `GET /review-parameters` | none | Public, short TTL | Implemented 20 Oct 2026 (section 5.15) |

Public responses vary by `Accept-Language` and are purged on moderation or deletion (Security 7.1).

### 4.4 Reports and removal

| Method and path | Credential | Cache | Status |
|---|---|---|---|
| `POST /public/review-reports` | guest scope + Turnstile | no-store | Planned (R11) |
| `POST /public/removal-requests` | guest scope + Turnstile | no-store | Planned (R11) |
| `POST /reviews/{review_id}/reports` | member | no-store | Planned (R11) |

### 4.5 Members and verification

| Method and path | Credential | Cache | Status |
|---|---|---|---|
| `POST /auth/register`, `/auth/verify-email`, `/auth/login`, `/auth/logout`, `/auth/password-reset/request`, `/auth/password-reset/confirm` | none or member | no-store | Planned (R04). Shapes are set by `Features/Identity-Access-Verification.md`. |
| `POST /reviews/member` | member | no-store | Planned (R07) |
| `GET /reviews/{review_id}` | owner or staff | no-store | Planned (R07) |
| `POST /verifications` | member | no-store | Planned (R04) |

### 4.6 Staff

| Method and path | Credential | Cache | Status |
|---|---|---|---|
| `GET /staff/moderation/reviews` | staff | no-store | Change required |
| `POST /staff/moderation/reviews/{review_id}/decisions` | staff | no-store | Implemented (error body aside) |
| `PUT /staff/moderation/reviews/{review_id}/conflict` | staff | no-store | Implemented (error body aside) |
| `GET /staff/verifications` | staff | no-store | Planned (R11) |
| `POST /staff/verifications/{verification_id}/decisions` | staff | no-store | Planned (R11) |
| `POST /staff/users/{user_id}/roles` | super administrator, recent reauthentication | no-store | Planned (R11) |

`POST /reviews/{review_id}/media-intents` (Verified Member only, constrained presigned upload into quarantine) is in core scope since Review.md amendment A1 (20 Oct 2026). Planned with R07 and the media pipeline; its shape is set when Review.md section 8 is implemented.

## 5. Request and response shapes

### 5.1 Guest receipt

The client generates the receipt before the first submission: 32 bytes from `crypto.getRandomValues`, encoded as unpadded base64url, with the prefix `abr1_`. The result is 48 characters (PF 13.2).

The server:

- validates the prefix, length and character set, and rejects known weak values;
- stores only `(key_id, HMAC-SHA-256 digest)` under a versioned keyring, with the context label `abhijatri:review-receipt:v1`;
- never generates, returns or reissues a receipt.

The guest scope digest uses the same keyring with the label `abhijatri:guest-scope:v1` and its own `guest_scope_key_id` (PF 13.4).

A receipt allows status, withdrawal, appeal, and editing while the review is `PENDING` or `CHANGES_REQUESTED`. It reveals only its own review. A lost receipt cannot be recovered; the user files a removal request instead.

### 5.2 `POST /reviews/guest`

```http
POST /api/v1/reviews/guest
Content-Type: application/json
Idempotency-Key: 4a7e0b52-3f6d-4c1a-9a2e-6c1f0d7b8e21
```

```json
{
  "destination_id": "6f1c2c9e-0c0e-4a3b-9a55-2f4f7e1d2b10",
  "client_draft_id": "0b9b2b1e-7a43-4c2e-8b57-0e0d8f6d6a11",
  "guest_scope_secret": "<43 to 200 character random secret kept by the client>",
  "receipt_secret": "abr1_<43 base64url characters>",
  "turnstile_token": "<token from the managed widget>",
  "guest_display_name": "Sadia Rahman",
  "language": "BN",
  "traveller_type": "FAMILY",
  "comfort_tier": "STANDARD",
  "visit_month": "2026-09-01",
  "title": "Good family trip",
  "body": "At least twenty characters of plain text, up to 6000.",
  "overall_rating": 4,
  "category_ratings": { "FOOD": 4, "SAFETY_PERCEPTION": 5 },
  "consent_version": "2026-10-01"
}
```

Field rules: `guest_display_name` 1 to 80 characters; `title` 3 to 160; `body` 20 to 6000, plain text; `overall_rating` 1 to 5; `visit_month` is the first day of a month and not in the future in the display time zone. Unknown fields return 422.

**`category_ratings` (implemented 20 Oct 2026, Review.md amendment A2):** optional object whose keys are the `ReviewCategory` values (Section 8) and whose values are integers 1 to 5; at most seven keys. A missing key means not applicable; an empty object is the same as omitting the field. An unknown key or a value outside 1 to 5 returns `422 VALIDATION_FAILED` with a field error under `category_ratings`. Ratings are stored per revision in `review_category_ratings`. On publication they move the per-category Guest Feedback (or, for an eligible Verified Member, Community) aggregate in the same transaction as the overall rating, and leave it on hide, withdrawal or conflict. The client sends the field when `VITE_REVIEW_CATEGORY_RATINGS=true`. `body` is the reviewer's free-text note. A Guest submission never carries images.

Response `201`:

```json
{
  "review_id": "d3a8f0a4-5d0e-4c43-9a0b-1f7e55c0a001",
  "status": "PENDING",
  "version": 1,
  "duplicate_recovered": false
}
```

The response contains no receipt. The client already holds it.

**Order of checks (PF 14.4):**

1. Validate the schema and the receipt format.
2. Look up an existing review for (guest scope digest, `client_draft_id`). If found, compare receipt digests: a match returns `200` with the existing review and `duplicate_recovered: true`; a mismatch returns `409 DRAFT_ALREADY_SUBMITTED` without the review id. Turnstile is not checked and nothing is counted.
3. Look up an `Idempotency-Key` replay. If found, return the stored response without counting it.
4. Validate the Turnstile token (hostname and action checked).
5. Increment rate-limit counters in their own committed transaction.
6. Check limits and pending ceilings.
7. Create the review.

A retry after a lost response is recovered at step 2 and needs no new challenge. Queued offline drafts are not auto-submitted; the user submits them on reconnection and completes the challenge.

### 5.3 `POST /review-receipts/status`

```json
{ "review_id": "d3a8f0a4-5d0e-4c43-9a0b-1f7e55c0a001", "receipt_secret": "abr1_..." }
```

Response `200`:

```json
{
  "review_id": "d3a8f0a4-5d0e-4c43-9a0b-1f7e55c0a001",
  "status": "REJECTED",
  "version": 2,
  "published_at": null,
  "decision_reason": "PERSONAL_INFORMATION",
  "appeal_deadline": "2026-11-17T08:30:00Z"
}
```

`decision_reason` is the public-safe reason code and `appeal_deadline` is 30 days after rejection. Both are `null` unless the review was rejected (RV 4.2). A wrong receipt returns `404 RECEIPT_NOT_FOUND`.

### 5.4 `POST /reviews/{review_id}/withdraw`

```json
{ "receipt_secret": "abr1_...", "expected_version": 2 }
```

Response `200`: the same body as 5.3. Withdrawal removes the review from public view and its rating contribution in one transaction.

Withdrawal is idempotent. If the review is already `WITHDRAWN` or `DELETED`, the server returns `200` with the current state **before** checking `expected_version`, so a retry after a lost response succeeds.

### 5.5 `PATCH /reviews/{review_id}/pending`

Allowed only while the review is `PENDING` or `CHANGES_REQUESTED` (RV 4.2, 5.2). Creates a new `review_revision`. Published reviews cannot be edited in the MVP; the author withdraws and submits a new review.

```json
{
  "receipt_secret": "abr1_...",
  "expected_version": 2,
  "title": "Good family trip",
  "body": "Edited text, at least twenty characters.",
  "overall_rating": 4,
  "visit_month": "2026-09-01"
}
```

Response `200`: `{ "review_id": "...", "status": "PENDING", "version": 3 }`. A member owner sends no `receipt_secret` and uses their session instead. Any other state returns `409 INVALID_TRANSITION`.

### 5.6 `POST /review-receipts/appeals`

```json
{ "review_id": "...", "receipt_secret": "abr1_...", "statement": "Plain text, 20 to 2000 characters." }
```

Response `201`: `{ "appeal_id": "...", "status": "OPEN" }`. Only for a `REJECTED` review within its appeal window; otherwise `409 APPEAL_WINDOW_CLOSED`.

### 5.7 Reports and removal requests

Report reasons (RV 5.4): `SPAM`, `HARASSMENT`, `FALSE_INFORMATION`, `PRIVATE_INFORMATION`, `IMPERSONATION`, `SAFETY_MISINFORMATION`, `COPYRIGHT`, `CONFLICT_OF_INTEREST`, `OTHER`.

`POST /public/review-reports`:

```json
{
  "review_id": "...",
  "guest_scope_secret": "...",
  "turnstile_token": "...",
  "reason": "PRIVATE_INFORMATION",
  "details": "Optional plain text, up to 1000 characters.",
  "contact_email": null
}
```

`POST /public/removal-requests` uses the same body without `reason`, with `details` explaining the request, and is the recovery path for a lost receipt. Both return `202 { "status": "RECEIVED" }`. A report never removes a review by itself. Duplicate open reports from the same scope return `409 DUPLICATE_OPEN_REPORT`.

`POST /reviews/{review_id}/reports` is the member version: same `reason` and `details`, no guest scope or Turnstile, session and CSRF instead.

### 5.8 `GET /destinations/{destination_id}/reviews`

Query: `after` (optional cursor, at most 200 characters), `limit` (1 to 50, default 20).

```json
{
  "items": [
    {
      "id": "...",
      "guest_display_name": "Sadia Rahman",
      "status": "PUBLISHED",
      "overall_rating": 4,
      "published_at": "2026-10-15T08:30:00Z",
      "title": "Good family trip",
      "body": "...",
      "category_ratings": { "FOOD": 4, "SAFETY_PERCEPTION": 5 }
    }
  ],
  "next_cursor": "MjAyNi0xMC0xNVQwODozMDowMCswMDowMHwuLi4",
  "guest_rating_average": 4.0,
  "guest_rating_count": 1,
  "guest_category_averages": [
    { "category": "FOOD", "average": 4.0, "count": 1 },
    { "category": "SAFETY_PERCEPTION", "average": 5.0, "count": 1 }
  ]
}
```

`category_ratings` is `{}` when the reviewer rated no category. `guest_category_averages` lists only categories with at least one counted rating, in the Section 8 order, each with its own count.

Only `PUBLISHED` reviews appear. Guest ratings feed Guest Feedback only, never Community Rating (RV 6.2). The response carries a short public `Cache-Control` TTL (Security 7.1), not `no-store`.

### 5.9 `GET /staff/moderation/reviews`

Query: `after` (cursor over submission time and id, ascending), `limit` (1 to 50, default 20). Returns reviews in `PENDING` or `UNDER_REVIEW`, oldest first.

```json
{
  "items": [
    {
      "review_id": "...",
      "destination_id": "...",
      "status": "PENDING",
      "version": 1,
      "author_kind": "GUEST",
      "guest_display_name": "Sadia Rahman",
      "language": "BN",
      "overall_rating": 4,
      "visit_month": "2026-09-01",
      "title": "Good family trip",
      "body": "...",
      "conflict_declared": false,
      "submitted_at": "2026-10-15T07:10:00Z"
    }
  ],
  "next_cursor": null
}
```

Moderators need the content to decide, so the queue returns it. The response is `no-store`.

**Current code (20 Oct 2026):** a bare list (at most 100, oldest first) of `review_id`, `status`, `version`, `counted_rating`, `destination_id`, `guest_display_name`, `overall_rating`, `title`, `body`, `category_ratings` and `created_at`. Paging and the remaining fields above are still a change required (Section 6).

### 5.10 `POST /staff/moderation/reviews/{review_id}/decisions`

```json
{ "expected_version": 1, "decision": "PUBLISH", "reason_code": "OK", "note": null }
```

`decision` is one of `PUBLISH`, `REJECT`, `HIDE`, `RESTORE`. `reason_code` is 2 to 60 characters; `note` is at most 500.

Allowed transitions: `PUBLISH` and `REJECT` from `PENDING` or `UNDER_REVIEW`; `HIDE` from `PUBLISHED`; `RESTORE` from `HIDDEN`. Anything else returns `409 INVALID_TRANSITION`.

Response `200`:

```json
{ "review_id": "...", "status": "PUBLISHED", "version": 2, "counted_rating": null }
```

`counted_rating` is `null` for guest reviews and the 1 to 5 value for an eligible Verified Member review. Every decision records actor, reason, note, previous state, new state and time in the audit log, in the same transaction as the rating delta.

### 5.11 `PUT /staff/moderation/reviews/{review_id}/conflict`

```json
{ "expected_version": 2, "conflict_declared": true, "reason_code": "OWNER_LINK", "note": null }
```

Response `200`: same shape as 5.10. Changing the flag on a published review locks the review and the destination aggregate, removes any previous `counted_rating`, recalculates eligibility and applies the new delta in one transaction (RV 6.1). The audit log records it as `SET_CONFLICT` or `CLEAR_CONFLICT`.

### 5.12 `GET /destinations`

Query: `after` (optional cursor, at most 300 characters), `limit` (1 to 50, default 20). Returns `PUBLISHED` destinations ordered by `name_en`, then `id`. The cursor is over `(name_en, id)` and is not reusable on other routes. An undecodable cursor returns `422`.

```json
{
  "items": [
    {
      "id": "6f1c2c9e-0c0e-4a3b-9a55-2f4f7e1d2b10",
      "name_bn": "কক্সবাজার",
      "name_en": "Cox's Bazar",
      "region_bn": "চট্টগ্রাম বিভাগ",
      "region_en": "Chattogram Division",
      "summary_bn": "...",
      "summary_en": "...",
      "latitude": 21.4272,
      "longitude": 92.0058,
      "community_rating": { "average": null, "count": 0, "category_averages": [] },
      "guest_feedback": {
        "average": 4.5, "count": 2,
        "category_averages": [{ "category": "FOOD", "average": 4.5, "count": 2 }]
      },
      "active_advisory_count": 1,
      "last_updated": "2026-10-19T06:00:00Z"
    }
  ],
  "next_cursor": null
}
```

All text fields carry both languages in every response, so the client picks the language and an offline pack needs only one fetch. Profile fields are `null` until content is entered (R01). `community_rating.average` stays `null` until Verified Member ratings exist; Guest Feedback is never mixed into it (RV 6.2). `active_advisory_count` counts published advisories that are in effect and not expired on the Asia/Dhaka date.

### 5.13 `GET /destinations/{destination_id}`

Query: `include_expired` (boolean, default `false`). Returns one `PUBLISHED` destination. A draft, archived or unknown destination returns `404` with the same body, so existence is not leaked.

```json
{
  "id": "6f1c2c9e-0c0e-4a3b-9a55-2f4f7e1d2b10",
  "name_bn": "...", "name_en": "...",
  "region_bn": "...", "region_en": "...",
  "summary_bn": "...", "summary_en": "...",
  "seasonality_bn": "...", "seasonality_en": "...",
  "restrictions_bn": "...", "restrictions_en": "...",
  "latitude": 21.4272, "longitude": 92.0058,
  "community_rating": { "average": null, "count": 0, "category_averages": [] },
  "guest_feedback": { "average": null, "count": 0, "category_averages": [] },
  "guide_items": [
    {
      "id": "...", "category": "ATTRACTION", "sort_order": 0,
      "title_bn": "...", "title_en": "...", "body_bn": "...", "body_en": "...",
      "provenance": {
        "source_type": "TEAM_RESEARCH", "source_ref": "https://example.org/source",
        "publisher": "Abhijatri content team",
        "effective_on": "2026-10-01", "verified_on": "2026-10-15", "next_review_on": "2027-01-15",
        "licence": "CC-BY-4.0"
      }
    }
  ],
  "advisories": [
    {
      "id": "...", "severity": "CAUTION",
      "title_bn": "...", "title_en": "...", "text_bn": "...", "text_en": "...",
      "effective_on": "2026-10-01", "valid_until": "2026-12-01",
      "state": "CURRENT",
      "provenance": { "source_type": "OFFICIAL", "source_ref": "...", "publisher": "...",
                      "effective_on": "2026-10-01", "verified_on": "2026-10-15",
                      "next_review_on": null, "licence": "..." }
    }
  ],
  "contacts": [
    {
      "id": "...", "kind": "TOURIST_POLICE",
      "name_bn": "...", "name_en": "...", "phone": "+880 341-62000",
      "address_bn": null, "address_en": null, "latitude": null, "longitude": null,
      "provenance": { "...": "same shape as above" }
    }
  ],
  "content_licence": "CC-BY-4.0",
  "content_verified_on": "2026-10-15",
  "as_of": "2026-10-19",
  "stale_after_days": 30,
  "last_updated": "2026-10-19T06:00:00Z"
}
```

Rules:

- Only published guide items, advisories and contacts appear. `guide_items` are ordered by category, then `sort_order`; `advisories` by severity (most severe first), then `valid_until`; `contacts` by kind, then name.
- **Advisory state** is computed on read from the Asia/Dhaka date `as_of`, never stored:

| `state` | Meaning |
|---|---|
| `CURRENT` | In effect (`effective_on <= as_of <= valid_until`) and verified within `stale_after_days`. |
| `STALE` | In effect, but last verified more than `stale_after_days` ago. The client shows it distinctly with its `verified_on` date. |
| `EXPIRED` | `as_of > valid_until`. Returned only with `include_expired=true`; never presented as current. |
| `NOT_YET_EFFECTIVE` | `as_of < effective_on`. Never returned by this route. |

- Every advisory and contact carries `provenance` (PF 17). `researcher` and `reviewer` names stay internal and are never returned.
- Contacts are public institution and emergency numbers only; no personal contacts are stored.
- `phone` matches `^\+?[0-9][0-9 -]{2,30}$` (for example `999`).
- Both public destination routes send `Cache-Control: public, max-age=60` and a weak `ETag`; a matching `If-None-Match` returns `304` with no body. They are CORS simple requests (no custom headers, no credentials). Because the payload carries both languages, it does not vary by `Accept-Language`.
- `category_averages` (in both rating objects, list and profile) has the same shape and rules as `guest_category_averages` in 5.8: only counted categories, Section 8 order, each with its count. Guest and Community category averages are never merged.
- `community_rating` also carries `score` and `seeded_selection` (added 20 Oct 2026).
  - `score` is the Bayesian Community Rating `(sum + 5 × 3.5) / (count + 5)` (RV 6.1). It is `null` until `count >= 5`.
  - `seeded_selection` is `true` while the score is `null`. The client then shows "Seeded Destination Selection" instead of a score (RV 6.4).
  - Clients display these values and never compute the rating themselves.

### 5.14 `POST /guest-visits` and `GET /guest-visits/stats`

These routes support the landing-page welcome for guests: "Welcome, <name> · Guest #N" (Review.md 3.2 step 1). **The guest's name never reaches the server.** The client keeps it on the device. The server only gives each guest device a stable number.

```http
POST /api/v1/guest-visits
Content-Type: application/json
```

```json
{ "guest_scope_secret": "<the same 43 to 200 character secret used for Guest reviews>" }
```

Response `200`:

```json
{ "guest_number": 128, "total_guests": 128 }
```

- **Strict body.** Any other field, including `name`, returns `422 UNKNOWN_FIELD`.
- **Stable number.** The same secret always returns the same `guest_number`; a new device gets the next number. Calling it on every app start is safe.
- **What is stored.** The server stores only an HMAC digest of the secret, under the key ring with its own label `abhijatri:guest-visit:v1`, so it cannot be linked to a review's scope digest. It also stores the key id, the number, and the first and last visit times. No name, address or user row is stored.
- **Limits.** The in-memory burst limit `RATE_LIMIT_GUEST_VISIT` (default `20/minute`) applies first, then a durable `GUEST_VISITS_PER_NETWORK_PER_HOUR` (default 60), which returns `429 RATE_LIMITED` with `Retry-After`.
- **Caching.** `Cache-Control: no-store`. No cookie or CSRF token is used.

`GET /api/v1/guest-visits/stats` returns `{ "total_guests": 128, "guests_today": 9 }`. `guests_today` counts first visits since midnight on the display-time-zone date. The response is public, with a short TTL (Security 7.1).

**Intended client flow (frontend not yet changed):**
1. The guest enters a name on the landing page.
2. The client saves the name locally.
3. The client calls `POST /guest-visits` with `getGuestScopeSecret()`.
4. The client opens the welcome view with the name and `guest_number`.
5. If the call fails, the welcome still shows the name, without a number.

### 5.15 `GET /review-parameters`

This route returns the review form and the rating rules, so the client renders them from the server and never hard-codes them. `POST /reviews/guest` validates against the same constants (`backend/app/review_parameters.py`). A test fails if the published limits and the validation schema ever disagree. The response is public, with a short TTL.

```json
{
  "version": "2026-10-20",
  "overall_rating": { "required": true, "min": 1, "max": 5 },
  "categories": [
    {
      "code": "CLEANLINESS",
      "name": { "bn": "পরিচ্ছন্নতা", "en": "Cleanliness" },
      "prompt": { "bn": "...", "en": "How clean were the area, stay and toilets?" },
      "required": false, "min": 1, "max": 5
    }
  ],
  "note": { "field": "body", "required": true, "min_length": 20, "max_length": 6000 },
  "title": { "field": "title", "required": true, "min_length": 3, "max_length": 160 },
  "display_name": { "field": "guest_display_name", "required": true, "min_length": 1, "max_length": 80 },
  "traveller_types": [{ "value": "SOLO", "label": { "bn": "একা", "en": "Solo" } }],
  "comfort_tiers": [{ "value": "ECONOMY", "label": { "bn": "সাশ্রয়ী", "en": "Economy" } }],
  "languages": [{ "value": "BN", "label": { "bn": "বাংলা", "en": "Bangla" } }],
  "rating_rules": {
    "guest_feedback": "...", "community_rating": "...", "category_averages": "...",
    "community_prior_mean": 3.5, "community_prior_weight": 5, "community_min_reviews": 5
  }
}
```

**How the rating is calculated** (RV 3.1, A2 and 6):
- A review has one required overall rating from 1 to 5, any of the seven optional category ratings (1 to 5; missing means not applicable), and a required note (`body`).
- **Guest Feedback** is the mean overall rating of published Guest reviews.
- **Community Rating** is the Bayesian `score` over eligible Verified Member reviews (5.12). It is shown only from five reviews.
- **Category averages** are computed per audience and never merged.
- The overall rating is never derived from the category ratings.

## 6. Changes required in the current code

The routes marked "Change required" in Section 4 differ from this contract as follows. Each item is a code defect, not a reason to change this contract.

| Route | Current behaviour | Required | Source |
|---|---|---|---|
| All | ~~`{"detail": ...}` errors and FastAPI's default 422 body~~ Done 19 Oct (WP2): every error uses the Section 2 body, `app/errors.py` | Section 2 format | PF 12.3 |
| All writes | `Idempotency-Key` allowed by CORS but ignored | Section 3 | PF 12.4 |
| `POST /reviews/guest` | ~~Server generates `receipt_token`, returns it, and issues a new one on every duplicate retry~~ Done 19 Oct (WP3): client `receipt_secret`, nothing returned, never reissued, match `200` / mismatch `409`. Order-of-checks steps 3 to 6 (idempotency, Turnstile, counters, limits) pending WP4/WP5 | Client `receipt_secret`, nothing returned, never reissued, Section 5.2 order of checks | PF 13.1 to 13.3, 14.4 |
| `POST /reviews/guest` | ~~No Turnstile; limits keyed on remote address only~~ Done 19 Oct (WP5): server-side Turnstile, durable per-scope and per-network limits, pending ceilings, emergency switch | Turnstile plus Section 7 limits | PF 14.1, 14.3 |
| Receipt and scope digests | ~~One pepper, no `key_id`, no context labels~~ Done 19 Oct (WP3): versioned keyring (`RECEIPT_KEYS`, `RECEIPT_KEY_CURRENT`), labels, `key_id`/`guest_scope_key_id`, unique `(key_id, digest)`, re-digest on use | Keyring with `key_id` and labels | PF 13.4 |
| `POST /review-receipts/exchange` | ~~Legacy name; returns no reason or deadline~~ Removed 19 Oct (WP3); `POST /review-receipts/status` (5.3) added | Remove; add `POST /review-receipts/status` (5.3) | PF Annex A.7, RV 4.2 |
| `POST /reviews/{review_id}/withdraw` | ~~Checks `expected_version` before the already-withdrawn check, so a retry returns 409~~ Done 19 Oct (WP3) | 5.4 | PF 12.4 |
| `GET /destinations/{destination_id}/reviews` | ~~Middleware sets `no-store`~~ Done 19 Oct: `Cache-Control: public, max-age=60` | Short public TTL | Security 7.1 |
| `POST /reviews/guest` | ~~Rejects `category_ratings` as an unknown field~~ Done 20 Oct: accepted, stored per revision, counted on publish, returned in 5.8, 5.12, 5.13 | Accept and store the optional `category_ratings` (5.2) | RV 3.1, amendment A2 |
| `POST /reviews/{review_id}/media-intents` | Absent | Verified Member image upload intent | RV 8, amendment A1 |
| `GET /staff/moderation/reviews` | Returns content (title, body, display name, overall and category ratings) since 20 Oct, but still a bare list capped at 100 without cursor | 5.9 | RV 9.3 |
| `GET /health/ready` | Returns `status` only | Add `build` and `db_revision` | PF 22.1 |
| CORS | `allow_credentials=false`; no `X-CSRF-Token` or `Accept-Language` header | Section 1.2, with the R04 authentication milestone | PF 16.1 |
| Client address | ~~Uvicorn runs with `--proxy-headers` and `FORWARDED_ALLOW_IPS` defaulting to `*`~~ Done 19 Oct (WP5): `--no-proxy-headers`; `app/client_address.py` reads only the configured provider-appended entry; the forged-header test on staging is still outstanding (Gate A) | Provider-appended address only | PF 14.2 |

## 7. Rate limits

Limits are configuration values. Starting values (PF 14.3):

| Action | Per credential | Per network digest | Other control |
|---|---|---|---|
| Guest review submission | 3 new drafts per guest scope per 24 h | 30 per hour, 100 per 24 h | Fresh Turnstile token per new draft |
| Guest reports | 10 per guest scope per hour | 60 per hour | Fresh Turnstile token |
| Guest removal requests | 3 per guest scope per 24 h | 20 per 24 h | Fresh Turnstile token |
| Receipt operations | 20 per receipt digest per hour | 100 per hour | Progressive delay after repeated failures |
| Pending guest reviews | 50 per destination, 500 total | n/a | Administrator alert at 80 % |

The client address is the provider-appended entry only (PF 14.2). IPv6 is truncated to /64 and stored only as a keyed digest. Public reads and staff routes have independent limits. Hitting a pending ceiling returns `503 GUEST_WRITES_PAUSED` for guest submissions only.

## 8. Enumerations

| Name | Values |
|---|---|
| `ReviewStatus` | `PENDING`, `UNDER_REVIEW`, `CHANGES_REQUESTED`, `PUBLISHED`, `HIDDEN`, `REJECTED`, `WITHDRAWN`, `DELETED` |
| `RatingEligibility` | `NOT_EVALUATED`, `ELIGIBLE`, `INELIGIBLE_GUEST`, `INELIGIBLE_UNVERIFIED`, `INELIGIBLE_DUPLICATE`, `INELIGIBLE_CONFLICT`, `INELIGIBLE_REPORTED`, `INELIGIBLE_REMOVED` |
| `ReviewLanguage` | `BN`, `EN`, `MIXED` |
| `TravellerType` | `SOLO`, `STUDENT`, `COUPLE`, `FAMILY`, `GROUP` |
| `ComfortTier` | `ECONOMY`, `STANDARD`, `PREMIUM` |
| `ReviewCategory` | `CLEANLINESS`, `ACCESSIBILITY`, `HOSPITALITY`, `FOOD`, `TRANSPORT`, `SAFETY_PERCEPTION`, `VALUE` (implemented 20 Oct 2026; also the display order of category averages) |
| `GuideCategory` | `ATTRACTION`, `ACCOMMODATION`, `FOOD`, `TRANSPORT`, `LOCAL_PRACTICE` |
| `AdvisorySeverity` | `INFO`, `CAUTION`, `WARNING`, `CRITICAL` |
| `AdvisoryState` | `CURRENT`, `STALE`, `EXPIRED`, `NOT_YET_EFFECTIVE` (Section 5.13) |
| `ContactKind` | `POLICE`, `TOURIST_POLICE`, `AMBULANCE`, `FIRE`, `HOSPITAL`, `COAST_GUARD`, `FOREST_OFFICE`, `LOCAL_GUIDE`, `OTHER` |
| `SourceType` | `OFFICIAL`, `TEAM_RESEARCH`, `OPEN_LICENCE`, `VENDOR_LICENSED`, `OTHER` |
| Moderation `decision` | `PUBLISH`, `REJECT`, `HIDE`, `RESTORE` |
| Report `reason` | Section 5.7 |
| Platform roles | `MODERATOR`, `ADMINISTRATOR`, `SUPER_ADMINISTRATOR` |

`LOCAL_DRAFT` exists only on the device and is never sent to the API.

## 9. Change process

1. Change the code, run the export script and commit the new `Docs/api/openapi-v1.json`.
2. Update this document in the same pull request. CI fails if an implemented path is missing here.
3. Record breaking or rule-changing changes in `Docs/Decisions.md`.
4. The frontend owner is notified through the pull request.
