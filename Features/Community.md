# Abhijatri Community
**Execution:** Step 11 of `Features/Execution.md` (XFR-02). This document is the specification that step names, and it satisfies its required result: Verified users create or join private communities under membership, invitation, approval, visibility, moderation, removal, reporting, blocking and audit rules.
**Depends on:** R04 accounts and sessions; Verified Member verification (Review.md 2.3, A3); moderation and administration (Execution step 5); the shared media pipeline (Review.md 8, Execution step 10) for optional images; `can(actor, action, resource)` (Review.md 2.2).
**Boundaries:** Review.md 9.1 reserves the community tables "without changing review ownership or global authority". The Proposal excludes private chat, group tours and traveller monitoring from semester scope. A private community here is a moderated discussion space, not a chat: no real-time messaging, no direct messages and no presence or location. Group tours belong to `Features/Tourmates.md` (XFR-03).

## 1. Purpose

**Community members are identified; guests are not.** Guests are only counted per day (`guest_visits`: a number and a time). Reading requires a signed-in account, and writing requires Verified Member status, so the platform knows who is in each community (scope owner, 20 Oct 2026).

The Community answers the question a static guide cannot: **what is it like there now?** ("Is the Bandarban road open after rain?", "What does a CNG from Sreemangal to Lawachara cost this week?"). It is not a social network: there are no followers, no direct messages, no likes, no profile pages listing a member's activity and no engagement-ranked feeds. Feeds are chronological.

### 1.1 What makes it different

These four rules follow from the rest of Abhijatri and are what a generic forum does not do.

1. **Dated field reports.** Besides questions and tips, a Verified Member can post a *field report* that states the date they observed something (`observed_on`) and its subject (road, weather, crowd, price, closure, safety). Reports carry a visible age and go stale on the same Asia/Dhaka calendar rules as advisories (Schema.md 4). A stale report is labelled "may be out of date" and is never presented as current. This is the Proposal's rule that expired information must not look current, applied to community content.
2. **A bridge to verified information.** Staff can promote a field report into a *candidate* for a destination advisory or price record. Promotion never publishes anything by itself: staff verify the claim, then create the advisory or price record through the normal provenance path (`source_type`, `source_ref` pointing at the report, `verified_on`). Price reports become the "moderated community report" source (authority 0.6) that the Proposal's cost-confidence formula already defines. The community therefore improves the guide instead of competing with it.
3. **Answers from people who went.** A reply from a member who has a published review of the same destination shows a "Reviewed this place" marker, derived from the reviews table, never typed by the user. It is a factual link, not a rating or rank. The question's author can mark one reply as the accepted answer.
4. **Bangla-first and low-data.** Posts are plain text in Bangla, English or Banglish (`BN`, `EN`, `MIXED`, as for reviews). Feeds are text-first; images load only on request in low-data mode (Review.md 7.4).

## 2. Community kinds and visibility

| Kind | Created by | Who can read | How members join |
|---|---|---|---|
| `DESTINATION` (open) | Administrator. At most one per published destination. | Every signed-in Member | Verified Members join directly |
| `TOPIC` (open), for example "Solo women travellers" or "Hill tracts permits" | Administrator | Every signed-in Member | Verified Members join directly |
| `PRIVATE` | A Verified Member, who becomes its owner | Its active members only | By invitation from the owner or a community moderator, or by a join request they approve |

- A private community is invisible to non-members. Its pages and APIs return `404 NOT_FOUND` to anyone who is not an active member, so its existence is not leaked (Security.md 4.1). Only its name and short description are shown on an invitation.
- A Verified Member may own at most 3 private communities. A private community has at most 200 active members. Both limits are configuration values.
- An owner can transfer ownership to another active member, or archive the community. Platform staff can archive any community.

## 3. Actors and authority

| Actor | Can | Cannot |
|---|---|---|
| Guest | Nothing. Community pages ask them to sign in. | See any community content |
| Member (email verified, not Verified Member) | Read open communities; report content | Post, reply, join, or see private communities |
| Verified Member | Join or leave open communities; create a private community; accept invitations or request to join; post; reply; report; block another member; edit their own content while it is `PENDING` | Moderate. The Verified Member badge confers no community authority. |
| Community owner (private only) | Everything a community moderator can, in that community; appoint or remove its moderators; transfer ownership; archive it | Act in other communities; assign platform roles |
| Community moderator (a role scoped to **one** community) | Review, hide or restore content there; approve join requests; invite; mute or remove a member there | Act in other communities; ban across the platform; assign platform roles |
| Platform Moderator or Administrator | Everything a community moderator can, in every community; Administrators create or archive open communities, appoint their moderators, and ban accounts platform-wide | Bypass the audit trail |

Community authority lives in `community_memberships.role`, never in `platform_roles` (Review.md 2.2). Owners and community moderators are ordinary members and use the **member** session. Platform staff use the separate staff session with MFA (Security.md 4.3). Every check goes through `can()`:

```text
can(actor, "community.read", c)     -> c is open and actor is a signed-in Member, OR actor has an ACTIVE or MUTED membership in c
can(actor, "community.post", c)     -> active Verified Member AND ACTIVE membership in c (not MUTED)
can(actor, "community.moderate", c) -> membership.role in (OWNER, MODERATOR), OR platform MODERATOR or higher on a staff session
can(actor, "community.manage", c)   -> membership.role = OWNER (private), OR platform ADMINISTRATOR on a staff session
```

If a member's Verified Member status is revoked, their memberships stay but they can no longer post or reply. A private community whose owner loses Verified Member status keeps working; its moderators can still moderate, and staff can transfer ownership.

## 4. Data model (future migration)

| Table | Key columns | Constraints and notes |
|---|---|---|
| `communities` | `id`, `slug`, `kind` (`DESTINATION`, `TOPIC`, `PRIVATE`), `destination_id` (nullable FK), `name_bn`, `name_en`, `description_bn`, `description_en`, `status` (`ACTIVE`, `ARCHIVED`), `created_by`, `created_at`, `version` | Unique `slug`. `DESTINATION` requires `destination_id`, unique per destination. A `PRIVATE` community may name a destination. |
| `community_memberships` | `community_id`, `user_id`, `role` (`OWNER`, `MODERATOR`, `MEMBER`), `status` (`ACTIVE`, `MUTED`, `LEFT`, `REMOVED`), `joined_at`, `muted_until`, `version` | PK `(community_id, user_id)`. Exactly one `OWNER` for a `PRIVATE` community (partial unique index); none for open ones. |
| `community_invitations` | `id`, `community_id`, `invitee_user_id`, `invited_by`, `status` (`PENDING`, `ACCEPTED`, `DECLINED`, `REVOKED`, `EXPIRED`), `created_at`, `expires_at` | Invitee must be a Verified Member. One pending invitation per community and invitee. Expires after 14 days. |
| `community_join_requests` | `id`, `community_id`, `user_id`, `message`, `status` (`PENDING`, `APPROVED`, `REJECTED`, `WITHDRAWN`), `decided_by`, `created_at`, `decided_at` | One pending request per community and user. Only for `PRIVATE` communities reached through a shared link (section 6). |
| `community_posts` | `id`, `community_id`, `author_user_id`, `kind` (`QUESTION`, `TIP`, `FIELD_REPORT`), `report_subject` (nullable), `observed_on` (nullable date), `title`, `body`, `language`, `status`, `accepted_reply_id` (nullable), `version`, `created_at`, `published_at` | Plain text. Title 5–120 and body 20–4000 code points. `FIELD_REPORT` requires `observed_on` and `report_subject`, and `observed_on` is not in the future or older than 30 days at posting. Feed index `(community_id, status, published_at DESC, id DESC)`. |
| `community_replies` | `id`, `post_id`, `author_user_id`, `body`, `status`, `version`, `created_at`, `published_at` | One level, no nested threads. Body 2–2000 code points. |
| `community_blocks` | `blocker_user_id`, `blocked_user_id`, `created_at` | PK on both. Platform-wide between two accounts (section 7). |
| `community_media` | Same columns as `review_media` (Review.md 8) with `post_id` in place of the review revision | At most 3 images per post; same quarantine, re-encoding and moderation. |
| `community_reports` | `id`, `target_kind` (`POST`, `REPLY`), `post_id` (nullable FK), `reply_id` (nullable FK), `reporter_user_id`, `reason` (the Review.md 5.4 list), `details`, `status`, `created_at` | Check: exactly one of `post_id` and `reply_id`, matching `target_kind`. One open report per reporter and target. |
| `community_moderation_actions` | `id`, `community_id`, `target_kind` (`POST`, `REPLY`, `MEMBERSHIP`, `JOIN_REQUEST`, `COMMUNITY`), `post_id`, `reply_id`, `member_user_id` (nullable FKs), `actor_user_id`, `actor_authority` (`COMMUNITY_ROLE` or `PLATFORM_ROLE`), `decision`, `previous_state`, `new_state`, `reason_code`, `note`, `created_at` | Append-only, FKs `RESTRICT`. Check: the FK named by `target_kind` is set and the others are null. Its own enums (section 5), separate from the review `moderation_actions` table. |
| `community_promotions` | `id`, `post_id`, `promoted_by`, `target` (`ADVISORY_CANDIDATE`, `PRICE_CANDIDATE`), `status` (`OPEN`, `ACCEPTED`, `DECLINED`), `result_ref` (nullable), `created_at`, `decided_at` | Staff-only. `result_ref` points at the advisory or price record staff created after verification. |
| (reused) `audit_events`, `outbox_events` | — | `audit_events` is the planned shared append-only log (Schema.md 3). `outbox_events.aggregate_id` is already a logical reference and needs no change. |

The existing `moderation_actions` table is **not** changed. Its `review_id` is a required FK and its status columns use the review status enum, so community decisions get their own table.

Every table has row-level security enabled, like every other table (Schema.md 4). `UPDATE`, `DELETE` and `TRUNCATE` on `community_moderation_actions` are revoked from the application identity, as for other audit records (Security.md 4.4).

## 5. Content lifecycle

```text
PENDING -> PUBLISHED -> HIDDEN -> PUBLISHED (restore)
        -> REJECTED (reason, 30-day appeal)
PUBLISHED -> WITHDRAWN (author) | DELETED (policy)
```

Community decisions: `PUBLISH`, `REJECT`, `HIDE`, `RESTORE`, `DELETE`, `MUTE`, `UNMUTE`, `REMOVE_MEMBER`, `APPROVE_JOIN`, `REJECT_JOIN`, `ARCHIVE`.

- **Trusted publishing.** A Verified Member's first 3 posts in a community, and every `FIELD_REPORT` with subject `SAFETY` or `CLOSURE`, are pre-moderated. Other content publishes immediately and stays reportable. A report with reason `PRIVATE_INFORMATION`, `HARASSMENT` or `SAFETY_MISINFORMATION` hides the content until a recorded decision. This keeps the moderation load manageable without auto-publishing a newcomer's content or an unchecked safety claim.
- **Edits.** Content can be edited only while `PENDING`. Published content is withdrawn and re-posted, as for reviews (Review.md 5.2).
- **Moderation.** Each decision writes a `community_moderation_actions` row and an audit event in the same transaction as the state change, with actor, the authority used, reason code, previous and new state, and time.
- **Field report freshness.** Age and staleness are derived at read time from `observed_on` on the Asia/Dhaka date, never stored. Starting values: weather, crowd and road reports are stale after 3 days; price reports after 30 days; closure and safety reports after 7 days. These are configuration values.
- **Retention.** Rejected content follows the review rule: 30-day appeal window, then the body is tombstoned. Hidden and deleted content is never served to members.

## 6. API (`/api/v1`)

All member routes use the member session cookie plus `X-CSRF-Token` on writes. Staff routes use the staff session. Only `GET`, `POST`, `PUT` and `PATCH` are used, matching the CORS allowlist (API.md 1.2). Every mutation of a versioned row sends `expected_version` (API.md 1). Every response is `Cache-Control: no-store`.

**Member routes**

| Method and path | Who |
|---|---|
| `GET /communities` (open communities plus the caller's private ones), `GET /communities/{slug}` | Member |
| `POST /communities` (creates a `PRIVATE` community) | Verified Member |
| `POST /communities/{slug}/membership` (join an open community), `POST /communities/{slug}/membership/leave` | Verified Member |
| `GET /communities/{slug}/posts?after=&kind=` (cursor over `(published_at, id)`, limit 1–50, default 20) | Member who can read it |
| `POST /communities/{slug}/posts`, `PATCH /community-posts/{id}/pending`, `POST /community-posts/{id}/withdraw` | Verified Member (author) |
| `PUT /community-posts/{id}/accepted-reply` | Author of the `QUESTION` |
| `GET /community-posts/{id}/replies`, `POST /community-posts/{id}/replies` | Reader reads; Verified Member writes |
| `POST /community-posts/{id}/media-intents` | Verified Member (author) |
| `POST /community-reports` | Member who can read the target |
| `POST /community-blocks`, `POST /community-blocks/{user_id}/remove` | Verified Member |
| `GET /community-invitations`, `POST /community-invitations/{id}/accept`, `POST /community-invitations/{id}/decline` | Invitee |
| `POST /communities/{slug}/join-requests`, `POST /community-join-requests/{id}/withdraw` | Verified Member with the community's share link |

**Community moderation routes (member session, community role)**

| Method and path | Who |
|---|---|
| `GET /communities/{slug}/moderation/queue` | Owner or community moderator |
| `POST /communities/{slug}/moderation/{target_kind}/{id}/decisions` | Owner or community moderator |
| `POST /communities/{slug}/invitations`, `POST /community-invitations/{id}/revoke` | Owner or community moderator |
| `GET /communities/{slug}/join-requests`, `POST /community-join-requests/{id}/decisions` | Owner or community moderator |
| `PUT /communities/{slug}/moderators`, `POST /communities/{slug}/owner-transfer`, `POST /communities/{slug}/archive` | Owner |
| `POST /communities/{slug}/share-link` (rotates the link; the old one stops working) | Owner |

The share link carries a random token in the JSON body of the join request, never in a logged query string. It lets a Verified Member *request* to join; it never admits them by itself.

**Staff routes (staff session)**

| Method and path | Who |
|---|---|
| `GET /staff/community/queue`, `POST /staff/community/{target_kind}/{id}/decisions` | Platform Moderator or higher |
| `POST /staff/community/posts/{id}/promotions`, `POST /staff/community/promotions/{id}/decisions` | Platform Moderator or higher |
| `POST /staff/communities`, `PUT /staff/communities/{id}/moderators`, `POST /staff/communities/{id}/archive` | Administrator, with recent reauthentication |

**New error codes** (added to API.md section 2 in the same change): `403 VERIFIED_MEMBER_REQUIRED`, `403 COMMUNITY_MEMBERSHIP_REQUIRED`, `403 COMMUNITY_MUTED`, `403 BLOCKED_BY_AUTHOR`, `409 DUPLICATE_OPEN_REPORT` (reused), `409 ALREADY_MEMBER`, `409 COMMUNITY_FULL`, `409 PRIVATE_COMMUNITY_LIMIT`, `409 INVITATION_NOT_PENDING`, `422 FIELD_REPORT_DATE_INVALID`. A private community the caller cannot read returns `404 NOT_FOUND`, never 403.

**Rate limits** (per account and per network digest, configuration values): posts 10 per day; replies 60 per day; reports 20 per day; invitations 30 per day per community; private community creation 1 per day.

## 7. Privacy and safety

- Community content is visible to signed-in readers only. It never enters service-worker caches, shared caches or offline packs (Security.md 7.1, 7.4), and sign-out clears it from memory.
- No direct messages, no real-time chat, no activity profile pages, no "who is here now", and no location sharing. Field reports name a place, never a person's position (Proposal: no traveller monitoring).
- **Blocking.** When A blocks B, neither sees the other's posts or replies, B cannot reply to A's posts, and neither can invite the other. A block is private: B is not told. Blocking does not hide content from moderators.
- Phone numbers, names of private individuals and other personal details in posts are flagged for moderator redaction (Review.md 5.3).
- Members see other members only by display name and badge. A private community's member list is visible to its members and moderators only.
- **Account deletion.** Community authorship follows the account-deletion decision still open in `Docs/Decisions.md` and Security.md 3.6. Decide it once for reviews and community content together. Either way, the deletion removes public personal linkage from posts and replies, transfers or archives any private community the account owns, and records an audit event. Public launch of the Community is blocked until that decision is made and tested.

## 8. Build order (after Execution steps 3, 5 and 10)

1. Migration with the section 4 tables; `can()` rules; communities, membership, invitations and join requests.
2. Posts and replies (text), field-report validation and freshness, pre-moderation, reports and blocks.
3. Community moderation routes and staff routes, reusing the review moderation service pattern with the separate action table.
4. Promotions to advisory and price candidates.
5. Images through the shared media pipeline.
6. Frontend in Bangla and English: community list, community page with chronological feed, post composer with field-report fields, invitation and join-request screens, moderation screens.

## 9. Acceptance

- A Member who is not a Verified Member cannot post, reply, join or create a community (403 from the API, even if the UI is bypassed).
- A non-member gets 404 for every route of a private community, including its posts, replies and media.
- A join request or share link never admits a member without an owner's or moderator's approval.
- A community owner or moderator cannot act outside their community, and cannot reach any `/staff/*` route with a member session.
- A blocked user cannot reply to the blocker's posts, and neither sees the other's content.
- Hidden, rejected, withdrawn and deleted content never appears in any feed.
- A field report older than its staleness window is labelled stale on the Asia/Dhaka date, and never shown as current.
- A promoted report changes no advisory or price until staff create the record through the provenance path.
- The "Reviewed this place" marker appears only when the author has a published review of that destination.
- Every moderation action has a `community_moderation_actions` row and audit event created in the same transaction.
- No community response is publicly cacheable or stored offline.
