# Abhijatri Community (design)

**Status:** Design only, 20 October 2026. Nothing here is implemented. It is written now, as the project owner asked, so that the Community can be built quickly after Verified Member status (Review.md 2.3) and authentication (R04) exist.
**Depends on:** R04 accounts and sessions; Verified Member verification (Review.md 2.3, A3); the image pipeline (Review.md 8) for optional images; `can(actor, action, resource)` (Review.md 2.2).
**Boundaries:** Review.md 9.1 already reserves `communities`, `community_memberships`, `community_posts` and `community_comments` "without changing review ownership or global authority". The Proposal places private chat, group tours and traveller monitoring outside semester scope, and so does this design.

## 1. Purpose

Verified Members can discuss destinations and travel topics in moderated, public-to-members spaces. The Community is a place for trustworthy follow-up questions ("Is the Bandarban road open after rain?"). It is not a social network: there are no followers, no direct messages, no feeds ranked by engagement and no likes in the MVP.

## 2. Actors and authority

| Actor | Can | Cannot |
|---|---|---|
| Guest | Nothing. Community pages ask them to sign in. | See posts. |
| Member (email verified, not Verified Member) | Read communities and posts | Post, comment or join |
| Verified Member | Join or leave; post; comment; report; edit their own content while it is pending | Moderate. Their badge confers no community authority. |
| Community moderator (a role **scoped to one community**) | Review, hide or restore content in that community; mute a member there | Act in other communities; assign platform roles |
| Platform Moderator or Administrator | Everything a community moderator can, in every community; create or archive communities; appoint community moderators | Bypass the audit trail |

Community authority lives in `community_memberships.role`, never in `platform_roles` (Review.md 2.2: no global authority from local roles). Every check goes through `can()`:

```text
can(actor, "community.post", community)    -> active Verified Member AND active membership AND not muted
can(actor, "community.moderate", community) -> membership.role = MODERATOR OR platform MODERATOR+
```

## 3. Data model (future migration)

| Table | Key columns | Constraints and notes |
|---|---|---|
| `communities` | `id`, `slug`, `kind` (`DESTINATION` or `TOPIC`), `destination_id` (nullable FK), `name_bn`, `name_en`, `description_bn`, `description_en`, `status` (`ACTIVE` or `ARCHIVED`), `created_by`, `created_at` | Unique `slug`. A `DESTINATION` community requires `destination_id`; at most one per destination. |
| `community_memberships` | `community_id`, `user_id`, `role` (`MEMBER` or `MODERATOR`), `status` (`ACTIVE`, `LEFT`, `MUTED`, `BANNED`), `joined_at`, `muted_until` | PK `(community_id, user_id)`. Changing the role or a ban is audited. |
| `community_posts` | `id`, `community_id`, `author_user_id`, `title`, `body`, `language`, `status` (`PENDING`, `PUBLISHED`, `HIDDEN`, `REJECTED`, `WITHDRAWN`, `DELETED`), `version`, `created_at`, `published_at` | Plain text only. Body 20–4000 code points. Index `(community_id, status, published_at DESC, id DESC)` for the feed. |
| `community_comments` | `id`, `post_id`, `author_user_id`, `body`, `status`, `version`, `created_at` | One level deep, no threads. Body 2–2000 code points. |
| `community_media` | Same columns as `review_media` (Review.md 8), with `post_id` instead of a review revision | At most 3 images per post; same quarantine, re-encoding and moderation |
| `community_reports` | `id`, `target_kind` (`POST` or `COMMENT`), `target_id`, `reporter_user_id`, `reason` (the Review.md 5.4 list), `status`, `created_at` | One open report per reporter and target |
| (reused) `moderation_actions`, `audit_events`, `outbox_events` | Generalised with a `target_kind` column | One audit trail for reviews and community content |

All tables have row-level security enabled, like every other table (Schema.md 4).

## 4. Content lifecycle

```text
PENDING -> PUBLISHED -> HIDDEN -> PUBLISHED (restore)
        -> REJECTED (reason, 30-day appeal)
PUBLISHED -> WITHDRAWN (author) | DELETED (policy)
```

- **Trusted publishing.** A Verified Member's first 3 posts in a community are pre-moderated. After that, posts publish immediately and stay reportable. A severe report hides a post until someone decides. This keeps moderation load manageable without auto-publishing a new account's content.
- **Edits.** A post can be edited only while `PENDING`. Published content is withdrawn and re-posted, the same as reviews (Review.md 5.2).
- **Moderation.** Every decision records actor, reason code, previous and new state, and time, in the same transaction as the state change.

## 5. API sketch (`/api/v1`, cookie session plus CSRF)

| Method and path | Who |
|---|---|
| `GET /communities`, `GET /communities/{slug}` | Member |
| `POST /communities/{slug}/membership`, `DELETE /communities/{slug}/membership` | Verified Member |
| `GET /communities/{slug}/posts?after=` (cursor over `(published_at, id)`) | Member |
| `POST /communities/{slug}/posts`, `PATCH /community-posts/{id}/pending`, `POST /community-posts/{id}/withdraw` | Verified Member (author) |
| `GET /community-posts/{id}/comments`, `POST /community-posts/{id}/comments` | Member reads; Verified Member writes |
| `POST /community-posts/{id}/media-intents` | Verified Member (author) |
| `POST /community-reports` | Member |
| `GET /staff/community/queue`, `POST /staff/community/{kind}/{id}/decisions` | Community moderator or platform staff |
| `POST /staff/communities`, `PUT /staff/communities/{id}/moderators` | Administrator, with recent reauthentication |

Errors use the API.md section 2 body. Every write is rate-limited per account and per network (posts: 10 per day; comments: 60 per day). No route is public-cached, and none is included in offline packs.

## 6. Privacy and safety

- Community content is visible to signed-in members only. It never enters service-worker caches or offline packs (Security.md 7.4).
- There are no direct messages, no profile pages listing a member's activity, and no location sharing.
- Phone numbers and personal details in posts are flagged for moderator redaction (Review.md 5.3).
- Account deletion removes or anonymises authorship following the decision still open in Security.md 3.6.

## 7. Build order (after R04 and Verified Member approval)

1. Migration with the tables in section 3; `can()` rules; membership endpoints.
2. Posts and comments (text) with pre-moderation and reports.
3. Staff queue and decisions, reusing the review moderation service pattern.
4. Images through the shared media pipeline.
5. Frontend: community list, community page with feed, post composer, moderation screens.

## 8. Acceptance (for the future build)

- A Member who is not a Verified Member cannot post or join (403 from the API, even if the UI is bypassed).
- A community moderator cannot act outside their community.
- Hidden, rejected, withdrawn and deleted content never appears in any feed.
- Every moderation action has an audit record created in the same transaction.
- No community response is cacheable publicly or stored offline.
