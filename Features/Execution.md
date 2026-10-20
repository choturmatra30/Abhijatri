# Abhijatri Feature Execution Order

**Status:** Approved execution sequence  
**Approved:** 16 October 2026  
**Development freeze:** 3 January 2027  
**Formal testing:** 4 to 11 January 2027  
**Internal completion:** 17 January 2027  
**Submission contingency:** 18 January 2027

## 1. Scope

All features listed in this document are required deliverables. The order is based on technical dependency. `Quality-Release.md` is prepared at the beginning, applied throughout development, and closed after every product feature passes acceptance.

The extension traces below are mandatory additions to the project traceability matrix:

| Trace | Required capability |
|---|---|
| XFR-01 | Moderated image and video media |
| XFR-02 | Private verified communities and membership |
| XFR-03 | Tourmate groups and join-request management |
| XFR-04 | Vendor, agency, reservation, and ticket-request workflows |
| XFR-05 | Sandbox payment demonstration |

These traces must be added to the proposal and Gantt before they are counted as formal course acceptance items.

The proposal statement that email verification controls review submission must also be amended: verification controls Member capabilities, while a Guest may submit a moderated review with a display name and receipt.

## 2. Fixed Product Rules

1. A Guest can browse, create an offline text draft, and submit a review without registration or verification.
2. A Guest must provide a display name. Anonymous review publication is not allowed.
3. A Guest review is stored in PostgreSQL, passes moderation, and is managed through its receipt.
4. Guest ratings contribute only to the separately labelled Guest Feedback result.
5. Community Rating uses only eligible published Verified Member reviews.
6. Email verification proves control of an email address. Verified Member status requires a separate approved verification record.
7. Review, moderation, rating, and audit transitions use the locked and versioned rules in `Features/Review.md`.
8. Bangla is the default interface language. English is available throughout the product.
9. Public destination information, advisories, contacts, and approved packs support low-bandwidth and offline use.
10. Media binaries are stored in object storage. PostgreSQL stores ownership, object keys, metadata, moderation state, and removal state.
11. Payment implementation is sandbox-only. It accepts no real money and creates no claim of a production payment.
12. A feature is not complete until its approved specification, implementation, tests, security checks, and acceptance evidence agree.

## 3. Execution Order

| Order | Specification | Requirements and traces | Depends on | Required completion result |
|---:|---|---|---|---|
| 1 | `Docs/Platform-Foundation.md` | F01 to F07; platform NFRs | None | Repository, frontend shell, backend, PostgreSQL, environments, security gates, CI, API contract, bilingual foundation, PWA foundation, observability, deployment, backup, and traceability controls pass Gate A. |
| 2 | `Features/Destination.md` | FR01, FR02, FR15; R01 to R03 | 1 | Published bilingual destinations provide attractions, accommodation, food, transport, contacts, coordinates, seasonality, restrictions, dated advisories, provenance, and administrative maintenance. |
| 3 | `Features/Identity-Access-Verification.md` | FR03, FR16; R04, R05 | 1 | Registration, email verification, sign-in, sign-out, reset, sessions, roles, staff MFA, verification records, badges, profile settings, and account deletion pass authorization tests. Guest review remains independent of authentication. |
| 4 | `Features/Review.md` | FR04 to FR07, FR12, FR13; R06 to R09, R15 to R17 | 2; member paths also use 3 | Guest, Member, and Verified Member review submission with the seven category ratings and a free-text note, Verified Member image attachment (Review.md amendments A1, A2), receipts, offline drafts, retry safety, moderation states, withdrawal, appeals, reporting, and stable public retrieval work end to end. |
| 5 | `Features/Moderation-Administration.md` | FR05, FR06, FR16; R10, R11, H06 | 3, 4 | Protected staff queues manage reviews, reports, appeals, verification, destinations, translations, advisories, prices, roles, and audit records with recorded reasons and permission tests. |
| 6 | `Features/Offline-PWA.md` | FR10, FR12 to FR15, FR17; R12 to R15, R18 | 2, 4 | Installable PWA, versioned IndexedDB packs, offline review drafts, atomic updates, cache invalidation, storage refusal, deletion, freshness, and reconnect behaviour pass real-device testing. |
| 7 | `Features/Rating-Discovery.md` | FR07; R08, H02 | 2, 4, 5 | Community Rating and Guest Feedback remain separate; Bayesian scores, counts, eligibility, Top Rated results, View More, filters, historical places, and permission-based nearby discovery pass correctness and privacy tests. |
| 8 | `Features/Cost-Planner.md` | FR08, FR09; E01 to E08, E11, E12 | 2, 5 | The deterministic planner returns source-dated, itemised BDT estimates by traveller context and pricing unit, including shared and per-person costs, freshness, assumptions, and confidence. |
| 9 | `Features/Saved-Trip-Brief.md` | FR11; E09, E13 | 6, 8 | A user can save, reopen, copy, export, and delete an estimate with free-text notes and optional contacts online and offline. It is not an itinerary planner. |
| 10 | `Features/Media.md` | XFR-01 | 3, 4, 5 | Verified Member image and video uploads use constrained upload intent, quarantine, validation, metadata removal, trusted processing, moderation, quotas, object storage, public delivery, deletion, and audit. Offline review drafts retain text only and request media reattachment online. |
| 11 | `Features/Community.md` | XFR-02 | 3, 5, 10 | Verified users can create or join private communities under membership, invitation, approval, visibility, moderation, removal, reporting, blocking, and audit rules. |
| 12 | `Features/Tourmates.md` | XFR-03 | 3, 5, 11 | Verified organisers and approved agencies can create tours, define capacity and eligibility, receive join requests, approve or reject members, close recruitment, show permitted participant details, support women-only tours, report or block users, and use protected group discussion. |
| 13 | `Features/Vendors-Bookings.md` | XFR-04 | 3, 5, 8 | Verified organisations manage vendor or agency profiles, staff membership, offerings, prices, reservation or ticket requests, status transitions, cancellation, commission records, disputes, and audit without claiming unsupported live inventory. |
| 14 | `Features/Payments.md` | XFR-05 | 13 | Sandbox payment initiation, provider callback verification, idempotency, status reconciliation, failure handling, retry, cancellation, demonstration receipts, and audit pass without processing real money. |
| 15 | `Features/Quality-Release.md` | O4 to O8; H07 to H11, T01 to T09, C01 to C08; XFR-01 to XFR-05 | 1 to 14 | Complete traceability, automated tests, security testing, offline and device testing, accessibility, performance, usability, backup and restore, release evidence, defect closure, deployment rehearsal, and final demonstration pass the release gate. |

## 4. Execution Gates

### Gate 1: Foundation

- Platform Foundation approved.
- Secrets rotated and repository scan clean.
- Frontend and backend build in CI.
- PostgreSQL migrations and security checks pass.
- Bangla, English, PWA, API, and test foundations run.

### Gate 2: Destination and Review Vertical Slice

- One bilingual destination is published.
- One Guest review completes draft, submission, moderation, publication, receipt status, withdrawal, and rating exclusion correctly.
- One Verified Member review contributes to Community Rating after moderation.
- One destination pack and one offline review draft work in airplane mode and reconnect safely.

### Gate 3: Planner and Saved Brief

- Pricing catalogue and deterministic calculations pass hand-worked cases.
- One saved trip brief works online and offline.
- Destination, review, rating, estimate, and saved-brief flows work together.

### Gate 4: Media and Community

- Media quarantine, processing, moderation, publication, and removal pass.
- Private-community membership and permissions pass.
- Tour creation, join requests, capacity, privacy, reporting, blocking, and discussion pass.

### Gate 5: Vendor, Booking, and Payment Demonstration

- Vendor and agency verification and scoped staff permissions pass.
- Reservation and ticket-request transitions pass.
- Sandbox payment success, failure, retry, callback, and reconciliation pass.
- No flow transfers real money or claims live inventory.

### Gate 6: Testing Entry

By 3 January 2027:

- all feature specifications are approved
- all required flows are implemented
- every requirement maps to test IDs
- test data and environments are frozen
- no untriaged blocker remains

### Gate 7: Release

From 4 to 11 January, execute functional, non-functional, security, privacy, accessibility, offline, device, usability, and regression tests. From 12 to 17 January, permit only defect corrections, approved low-risk improvements, documentation, deployment stabilization, and demonstration preparation. Use 18 January only as submission contingency.

## 5. Per-Feature Definition of Done

A feature is complete only when:

1. its specification is approved
2. its data ownership and permissions are defined
3. migrations and API contracts are versioned
4. Bangla and English interfaces are complete
5. online, weak-network, offline, and failure behaviour are defined where applicable
6. privacy, security, abuse, moderation, and deletion rules pass
7. unit, integration, authorization, concurrency, and end-to-end tests pass as applicable
8. acceptance evidence is linked to requirement and test IDs
9. no blocker or critical defect remains
10. documentation matches the implemented behaviour
