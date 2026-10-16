# Abhijatri API Contract (v1)

**Status:** Current implementation contract with approved target amendments, 16 October 2026. **Contract version:** `1.0.0-draft` (`info.version` is `0.1.0` until the first frontend integration). The machine-readable snapshot of implemented routes is `Docs/api/openapi-v1.json`; CI fails if it drifts from the code. Regenerate with `cd backend && uv run python scripts/export_openapi.py`. `Docs/Platform-Foundation.md` and `Features/Review.md` define the target receipt and error contracts that must land before frontend integration.

## 1. Conventions

| Topic | Rule |
|---|---|
| Base path | `/api/v1`. Breaking changes require `/api/v2`; additive fields and endpoints stay in v1. |
| Format | JSON, UTF-8. Identifiers are UUIDs. Timestamps are UTC ISO-8601. Bangla text is NFC-normalised where the field is a name. |
| Errors | Today `{"detail": "<message>"}`. The approved target is `{"error":{"code","message","request_id","field_errors"}}` from Platform Foundation 12.3; clients branch on `code`, never message text. |
| Status codes | 200/201 success; 401 unauthenticated; 403 forbidden; 404 not found or receipt mismatch (no existence leak); 409 state or version conflict; 422 validation; 501 staff authentication not configured; 503 database unavailable. |
| Concurrency | Mutations of a review carry `expected_version`; a stale value returns 409. |
| Pagination | Opaque `after` cursor over `(published_at, id)` descending; `limit` 1-50, default 20. |
| Idempotency | Offline submissions are deduplicated by permanent `client_draft_id`. A general `Idempotency-Key` header is planned (R16); expiry policy to be recorded. |
| Caching | Responses are private and non-cacheable unless a route is listed as Public below. |
| CORS | Explicit origin allow-list; credentials not allowed until session cookies are introduced (R04). |

## 2. Implemented endpoints

| Method and path | Credential | Cache | Request / response (see `backend/app/schemas.py`) |
|---|---|---|---|
| `GET /health` | none | no-store | `HealthResponse` |
| `GET /health/ready` | none | no-store | `HealthResponse`; 503 if the database is down |
| `POST /reviews/guest` | Guest scope secret in body | no-store | `GuestReviewCreate` -> `GuestReviewCreated` (201, one-time `receipt_token`) |
| `GET /destinations/{destination_id}/reviews` | none | Public | `ReviewFeed` |
| `POST /review-receipts/exchange` | receipt token in body | no-store | Legacy implemented endpoint; replaced by `POST /review-receipts/status` before frontend integration. |
| `POST /reviews/{review_id}/withdraw` | receipt token in body | no-store | `WithdrawRequest` -> `ReceiptStatus` |
| `GET /staff/moderation/reviews` | staff | no-store | `list[ModerationResult]` |
| `POST /staff/moderation/reviews/{review_id}/decisions` | staff | no-store | `ModerationRequest` -> `ModerationResult` |
| `PUT /staff/moderation/reviews/{review_id}/conflict` | staff | no-store | `ConflictFlagRequest` -> `ModerationResult` |

Staff credential today is the development-only `X-Test-Staff-Id` header (`APP_ENV` development or test). In production these routes return 501 until the real authentication adapter lands (R04).

## 3. Planned endpoints

| Method and path | Task | Credential | Notes |
|---|---|---|---|
| `GET /destinations` | R02 | none, Public | List with bilingual names and rating summary. |
| `GET /destinations/{id}` | R02 | none, Public | Detail, current advisories, contacts, source dates. |
| `POST /auth/register`, `/auth/verify-email`, `/auth/login`, `/auth/logout`, `/auth/password-reset/request`, `/auth/password-reset/confirm` | R04 | Member | Cookie session, CSRF, rate limits; proposed shape, to be reviewed. |
| `GET /destinations/{id}/pack/manifest` | R14 | none, Public | Version, generated date, content hash, freshness. |
| `POST /reviews/member` | R07 | Member | Verified-user review; ownership checks. |
| `GET /reviews/{review_id}` | R07 | owner or staff | Private until published. |
| `PATCH /reviews/{review_id}/pending` | R07 | receipt or owner | Only `PENDING` or `CHANGES_REQUESTED`; version-checked; creates a revision. |
| `POST /review-receipts/status`, `POST /review-receipts/appeals` | R07 | receipt token in body | Decision and appeal window; no receipt session or GET credential. |
| `POST /reviews/{review_id}/reports`, `POST /public/review-reports`, `POST /public/removal-requests` | R11 | Member / none | Duplicate-open-report control. |
| `POST /verifications`, `GET /staff/verifications`, `POST /staff/verifications/{id}/decisions` | R04 / R11 | Member / staff | Verified Member approval. |
| `POST /staff/users/{user_id}/roles` | R11 | Super administrator | Recent re-authentication, audit event. |
| `POST /reviews/{review_id}/media-intents` | Post-core | Verified Member | Only if the media pipeline starts. |

## 4. Change process

1. Change `schemas.py` / `api.py`, then run the export script and commit the new snapshot.
2. Note the change in `Docs/Decisions.md` if it is breaking or alters a rule.
3. Frontend (Abdullah) is notified through the PR; the contract test blocks undeclared drift.

## 5. Enumerations

| Name | Values |
|---|---|
| `ReviewStatus` | `PENDING`, `UNDER_REVIEW`, `CHANGES_REQUESTED`, `PUBLISHED`, `HIDDEN`, `REJECTED`, `WITHDRAWN`, `DELETED` |
| `ReviewLanguage` | `BN`, `EN`, `MIXED` |
| `TravellerType` | `SOLO`, `STUDENT`, `COUPLE`, `FAMILY`, `GROUP` |
| `ComfortTier` | `ECONOMY`, `STANDARD`, `PREMIUM` |
| Moderation `decision` on `/decisions` | `PUBLISH`, `REJECT`, `HIDE`, `RESTORE` (case-insensitive; anything else returns 422) |
| Conflict changes | Use `PUT .../conflict` with `conflict_declared`; `SET_CONFLICT` and `CLEAR_CONFLICT` are recorded in the audit trail, not accepted by `/decisions`. |

Allowed transitions on `/decisions`: `PUBLISH` and `REJECT` from `PENDING` or `UNDER_REVIEW`; `HIDE` from `PUBLISHED`; `RESTORE` from `HIDDEN`. Any other combination returns 409. `reason_code` is 2-60 characters (free text code; a fixed catalogue is planned with R10). A moderator cannot act on their own review (403).

Note: `decision` is typed as a string in the OpenAPI snapshot even though only four values are accepted; tightening it to an enum is a compatible change planned with R10.

## 6. Worked examples (implemented endpoints)

Guest submission below documents the current implementation only. The approved target adds the client-generated `receipt_secret` to the request and removes server issuance from the response, as specified in Platform Foundation 13.

```http
POST /api/v1/reviews/guest
Content-Type: application/json

{
  "destination_id": "6f1c2c9e-0c0e-4a3b-9a55-2f4f7e1d2b10",
  "client_draft_id": "0b9b2b1e-7a43-4c2e-8b57-0e0d8f6d6a11",
  "guest_scope_secret": "<43+ character random secret kept by the client>",
  "guest_display_name": "Sadia Rahman",
  "language": "BN",
  "traveller_type": "FAMILY",
  "comfort_tier": "STANDARD",
  "visit_month": "2026-09-01",
  "title": "Good family trip",
  "body": "At least twenty characters of plain text, up to 6000.",
  "overall_rating": 4,
  "consent_version": "2026-10-01"
}
```

Response `201`:

```json
{
  "review_id": "d3a8f0a4-5d0e-4c43-9a0b-1f7e55c0a001",
  "status": "PENDING",
  "version": 1,
  "receipt_token": "<shown once; store it, only its HMAC is kept server-side>",
  "duplicate_recovered": false
}
```

Retrying the same `client_draft_id` with the same `guest_scope_secret` returns the existing review with `duplicate_recovered: true` and no second review. Reserved display names (for example `Admin`, `Moderator`) return 409.

Moderation decision (staff):

```http
POST /api/v1/staff/moderation/reviews/{review_id}/decisions
X-Test-Staff-Id: <staff user uuid>      # development and test only

{ "expected_version": 1, "decision": "PUBLISH", "reason_code": "OK", "note": null }
```

Response `200`: `{ "review_id": "...", "status": "PUBLISHED", "version": 2, "counted_rating": null }`. `counted_rating` is `null` for Guest reviews (they feed Guest Feedback, not Community Rating) and the 1-5 value for eligible Verified Member reviews. A stale `expected_version` returns 409.

Public feed:

```json
{
  "items": [
    { "id": "...", "guest_display_name": "Sadia Rahman", "status": "PUBLISHED",
      "overall_rating": 4, "published_at": "2026-10-15T08:30:00Z",
      "title": "Good family trip", "body": "..." }
  ],
  "next_cursor": "MjAyNi0xMC0xNVQwODozMDowMCswMDowMHwuLi4",
  "guest_rating_average": 4.0,
  "guest_rating_count": 1
}
```

`next_cursor` is `null` on the last page. Pass it back as `?after=<cursor>`; an invalid cursor returns 422.

## 7. Proposed shapes (planned endpoints, subject to review)

These are proposals for R02, R04 and R14 so the frontend can build against stable names. They are not implemented and may change before the owning task starts.

```json
// GET /api/v1/destinations
{ "items": [ { "id": "uuid", "name_bn": "...", "name_en": "...",
               "community_rating": { "average": null, "count": 0, "display": "SEEDED" },
               "guest_feedback": { "average": 4.0, "count": 1 },
               "last_updated": "2026-10-15" } ],
  "next_cursor": null }

// GET /api/v1/destinations/{id}
{ "id": "uuid", "name_bn": "...", "name_en": "...", "summary_bn": "...", "summary_en": "...",
  "advisories": [ { "id": "uuid", "text_bn": "...", "text_en": "...", "source": "...",
                    "source_date": "2026-10-01", "expires_at": "2026-12-01" } ],
  "contacts": [ { "kind": "POLICE", "name": "...", "phone": "999", "source_date": "2026-10-01" } ],
  "content_licence": "..." }

// POST /api/v1/auth/register       { "email": "...", "password": "...", "display_name": "..." } -> 202
// POST /api/v1/auth/login          { "email": "...", "password": "..." } -> 204 + Set-Cookie (HttpOnly, Secure, SameSite=Lax)
// GET  /api/v1/destinations/{id}/pack/manifest
{ "destination_id": "uuid", "pack_version": 3, "generated_at": "2026-10-15T08:30:00Z",
  "content_hash": "sha256:...", "max_age_hours": 168, "resources": [ { "path": "...", "bytes": 1024 } ] }

// Structured error (planned H04)
{ "code": "REVIEW_VERSION_CONFLICT", "message": "review version changed", "details": { "current_version": 3 } }
```
