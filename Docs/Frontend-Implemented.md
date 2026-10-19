# Frontend Implementation Record

**Status:** Current as of 19 October 2026.
**Scope of this file:** what the public PWA actually does today, which defects were found and fixed, and the evidence for each claim. It mirrors `Docs/Backend-Implemented.md`.
**Rule:** this file claims only what the repository contains and a build, test or recorded browser run demonstrates. Anything not yet built is listed under "Not implemented" here and in `Docs/Implemented.md`.
**Owner:** Abdullah Bin Sorwar Choudhury (frontend, bilingual, offline).
**Related documents:** `Docs/api/API.md` (contract), `Docs/Architecture.md` section 10 (frontend structure), `Docs/Design.md` (tokens), `Docs/Decisions.md` (decisions), `Docs/Implemented.md` (project-wide status).

---

## 1. Gantt position on 19 October 2026

| ID | Task | Window | State |
|---|---|---|---|
| F03 | Bilingual information architecture and component plan | 12 to 14 Oct | **Overdue.** Design tokens exist in `Docs/Design.md`; the component map and Bangla-default flow approval do not. |
| R03 | Bilingual destination list and detail screens | 15 to 22 Oct | **Implemented** against the R02 API, with loading, error and empty states (section 2). |
| R05 | Account, verification and session screens | 18 to 23 Oct | **Blocked** by R04 (no authentication API exists). |
| R12 | Installable PWA shell, cached public destination views | 19 to 25 Oct | Not started. No manifest, service worker or IndexedDB yet. |
| R09 | Review form, list, filters, author controls | 20 to 27 Oct | **Guest path implemented** (section 3). Member path waits for R04 and R07; filters not started. |
| R13, R15 | Offline pack, offline drafts | 23 to 31 Oct | Not started. |

## 2. R03: Destination list and detail screens

| Item | Location |
|---|---|
| API module | `frontend/src/api/destinations.ts` (`listDestinations`, `listAllDestinations`, `getDestination`) |
| List page | `frontend/src/pages/DestinationsPage.tsx` |
| Detail page | `frontend/src/pages/DestinationDetailPage.tsx` |
| Overview | `frontend/src/pages/OverviewPage.tsx` (live counts from the same list) |
| Shared states | `frontend/src/components/common/StatusViews.tsx` (`LoadingState`, `ErrorState`, `EmptyState`, `describeError`) |
| Loader hook | `frontend/src/hooks/useApiResource.ts` (abort on change or unmount, `reload` for retry) |
| Display components | `frontend/src/components/destination/` (`RatingSummary`, `AdvisoryCard`, `ProvenanceNote`) |

Behaviour:

- Both languages arrive in one payload, so switching language never refetches and the page keeps its place ("English switch preserves context", Gantt R03).
- Every state is explicit: loading, network failure (offline message and retry), server error (server message in the interface language plus the request reference), not found (unknown or malformed id), empty list, and no filter match.
- Advisories appear before attractions. Each shows severity, state (`CURRENT`, `STALE` flagged as "not recently verified", `EXPIRED` labelled and never shown as current), validity date, source link and verification date. The page states the Dhaka `as_of` date and the staleness threshold.
- Guide items are grouped by category with per-item source and verification date (Platform Foundation 17).
- Contacts are `tel:` links with 44 px targets and their source.
- **Ratings follow Review.md 6.** Community Rating and Guest Feedback are separate pills, each with its count. Below five eligible Verified Member reviews the card says "Editorial seeded selection" instead of a score. The Bayesian formula (C = 3.5, m = 5) is applied only above that threshold.
- No images. The R02 API has no licensed image field, and the previous hotlinked Unsplash photos were unlicensed and did not show the named places (PF 17, PF 16.3). Text-first also suits the asset budget.

## 3. R09 (Guest path): review submission, receipt, status and withdrawal

| Item | Location |
|---|---|
| API module | `frontend/src/api/reviews.ts` |
| Page | `frontend/src/pages/ReviewsPage.tsx` |
| Form | `frontend/src/components/reviews/GuestReviewForm.tsx` |
| Receipt shown once | `frontend/src/components/reviews/ReceiptPanel.tsx` |
| Status and withdrawal | `frontend/src/components/reviews/ReceiptStatusPanel.tsx` |
| Public feed on the detail page | `frontend/src/components/reviews/ReviewFeedSection.tsx` |
| Labels | `frontend/src/components/reviews/reviewLabels.ts` |

Contract points met (API.md 5.1 to 5.4, 5.8; PF 13):

- **Receipt.** `generateReceipt()` makes `abr1_` plus 32 bytes from `crypto.getRandomValues`, unpadded base64url (48 characters). The server never issues one.
- **Retry safety.** One `client_draft_id` and receipt per draft. A failed or lost submission is retried with the same pair, so the server returns the stored review (`duplicate_recovered: true`) instead of a duplicate. A fresh pair is created only after success or `DRAFT_ALREADY_SUBMITTED`.
- **All required fields:** destination UUID, display name (1 to 80), language, traveller type, comfort tier, visit month (`YYYY-MM-01`, not after the current Asia/Dhaka month), title (3 to 160), body (20 to 6000, counted in code points like the server), rating 1 to 5, consent version `2026-10-01`. Client checks mirror the server; server `field_errors` are mapped back onto the matching inputs.
- **Receipt custody.** The receipt is shown once after acknowledgement, with copy and save-as-file, and a "saved it" confirmation before closing. It is held only in memory and never written to storage, a URL or a log (PF 13.3, 13.5).
- **Status and withdrawal** use `POST /review-receipts/status` and `POST /reviews/{id}/withdraw` with the receipt in the body and the `expected_version` from the status response. Withdrawal asks for confirmation.
- **Feed.** Published reviews, newest first, cursor "show more", Guest label, plain text only (React escapes it; no user HTML is rendered).
- The submission notice states moderation, the public display name and Guest label, the separate Guest Feedback, and that a lost receipt cannot be recovered.
- Inputs have associated labels, `aria-invalid` and `aria-describedby` for errors, a radio-group star rating with labelled 44 px targets, and focus moves to the receipt heading after submission.

## 4. Destination content seed (supports R01 and R03)

R01 belongs to Shahriar Islam. To give R03 real data to show, sourced seed content was added. **It still needs the R01 content review.** Every record has `reviewer = NULL` until that review happens.

| Item | Location |
|---|---|
| Content | `backend/scripts/destination_seed_content.py` |
| Loader | `backend/scripts/seed_destinations.py` (idempotent; matches by English name so the existing smoke-test record keeps its id and reviews) |
| Tests | `backend/tests/test_seed_content.py` (52 checks: semester scope, column lengths, phone format, advisory window, provenance) |

Content: Cox's Bazar, Sajek Valley, Sylhet, Sundarbans and Bandarban, each with region, summary, seasonality, restrictions, coordinates, 3 to 5 guide items, 1 to 2 advisories and national contacts (999, Tourist Police 01320-222222, Shastho Batayon 16263, and the 1090 disaster line for coastal and flood-prone places). Every record cites a source a reviewer can open; all were checked on 19 October 2026. Local office numbers that could not be confirmed were left out rather than guessed. Prices are excluded (they belong to E02 to E06).

The Sajek advisory "Road blockade eased until 21 October" is time-bound and expires on 22 October 2026. That is intended and demonstrates expiry.

## 5. Defects found and fixed

| # | Defect | Cause | Fix | Evidence |
|---|---|---|---|---|
| D1 | Guest review submission always failed, then showed a fake receipt (before the merge) or a raw error (after). | Sent slug ids (`sajek-valley`) where the API requires UUIDs; omitted `guest_display_name`, `language`, `visit_month`, `title`, `receipt_secret`, `consent_version`; sent a non-existent `travel_date` (rejected as `UNKNOWN_FIELD`); expected a server `receipt_token` the API no longer returns. | Rebuilt the flow on the contract (section 3). | Browser run, section 7. |
| D2 | API errors were never parsed. | `client.ts` expected `{code, message, details}`; the API returns `{error: {code, message, request_id, field_errors}}`. | `ApiError` now carries `code`, `requestId`, `fieldErrors`; network failures become `NETWORK_ERROR`. | `npm run build`; error states seen in the browser run. |
| D3 | Public GETs triggered a CORS preflight. | `Content-Type: application/json` was sent on every request. | Sent only with a body, so public reads stay CORS simple requests (PF 16.1). | Code review of `client.ts`. |
| D4 | Error messages ignored the interface language. | No `Accept-Language` header. | Sent from the current `<html lang>`. | Bangla and English messages seen in the browser run. |
| D5 | The local frontend could not reach the local backend (every request blocked by CORS). | `CORS_ALLOWED_ORIGINS` in the local `backend/.env` was `http://localhost:5173/`; browsers send the origin without a trailing slash, so it never matched. | `Settings.cors_origins` strips trailing slashes (`backend/app/config.py`). | `tests/test_config.py::test_cors_origins_ignore_trailing_slashes`; header `access-control-allow-origin: http://localhost:5173` observed. |
| D6 | Destination pages showed invented ratings ("4.85 Bayesian Score", "342 reviews", "Bayesian Verified"). | Hardcoded mock data. | Pages read the API; ratings follow section 2. | Browser run. |
| D7 | The interface claimed offline features that do not exist ("PWA Offline Ready", "IndexedDB Cache: offline packs and drafts stored locally", a pack download that only called `alert()`). | Mock UI. | Claims removed from the navbar, sidebar and detail page until R12 and R13 deliver them. | `Navbar.tsx`, `Sidebar.tsx`, `DestinationDetailPage.tsx`. |
| D8 | Mock data looked like an API module. | `SEEDED_DESTINATIONS` lived in `src/api/destinations.ts`. | Moved to `src/data/prototypeDestinations.ts` as `PROTOTYPE_DESTINATIONS`, used only by the planner, offline-packs and saved-trips prototypes. | `grep` shows no API page imports it. |
| D9 | Untyped, unused date helper. | `src/utils/formatDate.js` in a TypeScript project, imported nowhere. | Replaced by `src/utils/format.ts` (Asia/Dhaka dates, Bangla digits). | Build. |
| D10 | System Status reported the Railway API as "Unreachable" although it was up. | `isAllowedBackendUrl` (`src/api/health.ts`) accepts only `localhost`, `api.abhijatri.example` or the `VITE_API_BASE_URL` host, so the Railway URL was refused before any request was sent. | Extra hosts can be allowed with `VITE_ALLOWED_BACKEND_HOSTS` (comma-separated hostnames; documented in `frontend/.env.example`). The allow-list itself is kept. | Browser run on 19 Oct 2026: `https://abhijatri-backend.up.railway.app/` showed "Live & Connected", database ready, 238 ms. |
| D11 | Every non-OK health result showed the same "Unreachable" heading and hid the reason. | `HealthCheckPage` never rendered `healthResult.error`. | A refused URL now has status `blocked` ("URL not allowed (not tested)") with a bilingual explanation; other failures show their error text. | Browser run: `https://evil.example.com` showed the blocked message and sent no request. |

## 6. Defects found, reported to their owners, not fixed here

| # | Finding | Owner | Detail |
|---|---|---|---|
| B1 | `counted_rating` is returned as the rating value for Guest reviews. | Backend (Muhtasim) | API.md 5.10 says it is `null` for Guest reviews. The aggregates are correct (only Guest Feedback moves); the service keeps the value to subtract it later. Either the contract text or the response needs to change. |
| B2 | `tests/test_config.py::test_unset_environment_fails_closed` fails unless `DATABASE_URL` is set in the shell. | Backend (Muhtasim) | The test does not clear `DATABASE_URL`, and production now requires an explicit one. CI passes only because CI sets the variable. |
| B4 | The Railway deployment (`https://abhijatri-backend.up.railway.app`) runs backend code from before the `backend-dev` merge. | Railway owner (Muhtasim or Shahriar) | Checked 19 Oct 2026: `/health` and `/health/ready` return `200` and CORS allows `http://localhost:5173`, but `GET /destinations` is `404`, `POST /review-receipts/exchange` (removed) still exists, `POST /review-receipts/status` is `404`, errors use the old `{"detail": ...}` shape, and `GET /destinations/{id}/reviews` returns `500` for every valid id. Redeploy from current code. If it shares the Supabase database migrated to `0005` on 19 Oct, its old receipt routes will also fail (`0004` renamed `review_receipts.token_hash` to `digest`). The current frontend cannot use this deployment until then. |
| B3 | The local `backend/.env` lists `https://abhijatri-backend.up.railway.app/` as an allowed CORS origin. | Whoever owns that `.env` | That is the API's own address, not a browser origin. The architecture also names Render, not Railway; the deployment target needs one answer. |

## 7. Verification evidence (19 October 2026)

All runs were local against an embedded PostgreSQL 16 server (the project targets 17; the embedded build was used because Docker is not installed on this machine).

**Shared Supabase database, 19 October 2026** (the project in the local `backend/.env`, `APP_ENV=development`): it was at `0002_enable_rls` with no destinations or reviews. With the team's approval, `alembic upgrade head` applied `0003` to `0005`, then `seed_destinations.py` loaded 5 destinations, 21 guide items, 6 advisories, 18 contacts and 5 rating rows. `GET /destinations` and the Sajek profile returned `200` from that database. This was run from a developer machine, not the protected migration workflow (PF 22); staging and production must still migrate only through that workflow.

| Check | Result |
|---|---|
| `alembic upgrade head` on an empty database | 0001 to 0005 applied |
| `seed_destination.py`, then `seed_destinations.py` twice | Five destinations; the second run reused every id (idempotent) |
| Backend unit tests (`-m "not integration"`, with `DATABASE_URL` set as in CI) | 180 passed |
| Backend integration tests (`-m integration`) | 54 passed |
| `ruff check .` | clean |
| `npm run build` (strict `tsc` and Vite) | clean; initial JS 84 KB gzip (budget 200 KB), CSS 6.3 KB gzip |
| API lifecycle by script | submit `201`, same-draft retry `200` with `duplicate_recovered: true`, unknown field `422 UNKNOWN_FIELD`, status `200`, staff publish `200`, public feed shows the review, Guest Feedback `5.0 (1)`, Community Rating unchanged |
| Browser run (Microsoft Edge through Playwright, against Vite and the local API) | Overview, list and Sajek detail rendered in Bangla and English; "Write a review" preselected Sajek; empty-form validation shown; review submitted through the UI; receipt matched `abr1_` plus 43 characters; status "Waiting for moderation"; withdrawal reached "Withdrawn"; unknown destination showed "Destination not found"; no horizontal overflow at 390 px; only console error was that deliberate 404 |

## 8. Not implemented

| Item | Task |
|---|---|
| Cloudflare Turnstile widget. Production requires `turnstile_token`; local development has it disabled. | R09 follow-up. Needs the site key and the CSP entry in PF 16.3. |
| Guest scope secret in IndexedDB. It is in `localStorage` until the draft store exists. | R15 |
| Offline drafts, installable PWA, service worker, destination packs | R12, R13, R15 |
| Member review path, account screens | R05, R07, R09 (after R04) |
| Review filters, edit-pending, appeals, reports | R09, R07, R11 |
| Staff (admin) build | Gate A item "public and staff skeletons building in CI" |
| Self-hosted fonts (CSP `style-src 'self'`, 40 KiB Bangla font budget) | F03 or R12 |
| Frontend lint and unit tests in CI | PF 27 items 2 and 5 |
| Planner, offline packs and saved trips still use prototype data | E08, R13, E09 |
| Public deployment. `frontend/vercel.json` is ready; deploying and adding the Vercel origin to the API's `CORS_ALLOWED_ORIGINS` is with Shahriar Islam (`Architecture.md` section 5). | Interim Vercel deploy |
