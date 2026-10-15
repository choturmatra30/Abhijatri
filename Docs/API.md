# Abhijatri API Contract (v1)

**Status:** Draft for F02 review, 15 October 2026. **Contract version:** `1.0.0-draft` (`info.version` is `0.1.0` until the first frontend integration). The machine-readable snapshot of implemented routes is `Docs/api/openapi-v1.json`; CI fails if it drifts from the code. Regenerate with `cd backend && uv run python scripts/export_openapi.py`.

## 1. Conventions

| Topic | Rule |
|---|---|
| Base path | `/api/v1`. Breaking changes require `/api/v2`; additive fields and endpoints stay in v1. |
| Format | JSON, UTF-8. Identifiers are UUIDs. Timestamps are UTC ISO-8601. Bangla text is NFC-normalised where the field is a name. |
| Errors | Today `{"detail": "<message>"}`. Structured `{code, message, details}` is planned for H04; clients must branch on HTTP status, not message text. |
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
| `POST /review-receipts/exchange` | receipt token in body | no-store | `ReceiptExchange` -> `ReceiptStatus` |
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
| `GET /review-receipts/status`, `POST /review-receipts/appeals` | R07 | receipt token | Decision and appeal window. |
| `POST /reviews/{review_id}/reports`, `POST /public/review-reports`, `POST /public/removal-requests` | R11 | Member / none | Duplicate-open-report control. |
| `POST /verifications`, `GET /staff/verifications`, `POST /staff/verifications/{id}/decisions` | R04 / R11 | Member / staff | Verified Member approval. |
| `POST /staff/users/{user_id}/roles` | R11 | Super administrator | Recent re-authentication, audit event. |
| `POST /reviews/{review_id}/media-intents` | Post-core | Verified Member | Only if the media pipeline starts. |

## 4. Change process

1. Change `schemas.py` / `api.py`, then run the export script and commit the new snapshot.
2. Note the change in `Docs/Decisions.md` if it is breaking or alters a rule.
3. Frontend (Abdullah) is notified through the PR; the contract test blocks undeclared drift.
