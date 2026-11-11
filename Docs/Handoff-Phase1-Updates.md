# Handoff: Phase 1 updates (backend and testing)

**From:** Abdullah (frontend). **Started:** 11 November 2026.
**For:** Muhtasim (backend), Irfan (testing), Shahriar (content, merges).
**What this is:** five updates were requested for the Phase 1 (M1) frontend. This file lists, for each one, what the frontend did, what it needs from the backend, and what to test. It is updated as each update is done. Evidence for the frontend work: `Frontend-Implemented.md` section 5n. Other open items stay in `Handoff-Backend.md` and `Handoff-Testing.md`.

| No. | Update requested | Frontend | Needs backend | Needs testing |
|---|---|---|---|---|
| 1 | Places inside a destination by type (restaurant, resort, ...), with name and Google Maps link; sorting to find the best | **Part done (11 Nov 2026):** type filter and search on the guide, Google Maps links, "Best rated first" on the destination list | **Yes: [P1](#p1-places-inside-a-destination)** | [T1](#t1-tests-for-update-1) |
| 2 | Remove the overall rating; calculate it from the parameter ratings | **Done in the web client (11 Nov 2026)** | **Yes: [P2](#p2-the-server-calculates-the-overall-rating)** | [T2](#t2-tests-for-update-2) |
| 3 | "Exit" instead of "Sign out" for a guest | **Done (11 Nov 2026)** | No | [T3](#t3-tests-for-update-3) |
| 4 | No search by review ID and receipt; "My reviews" with keyword search; remove the 20-character limit | Not started | To be listed | To be listed |
| 5 | Hamburger side menu for the moderation queue | Not started | To be listed | To be listed |

---

## Update 1: what the frontend does now

The API has no separate places today. A destination has guide entries (text under five types: `ATTRACTION`, `TRANSPORT`, `ACCOMMODATION`, `FOOD`, `LOCAL_PRACTICE`) and one map point for the whole destination. Reviews and ratings belong to the destination, not to a restaurant or a resort. So the frontend built what the current data allows:

| Part | Behaviour |
|---|---|
| Type filter (destination page) | Buttons for All and for each guide type that has entries, each with its count. One type is shown at a time. |
| Search (destination page) | Finds guide entries by words in the title or text, in Bangla or English. Works together with the type filter. Works offline, because it filters what is already on the device. |
| Google Maps link | The destination's map point opens in Google Maps (it opened OpenStreetMap before). A contact with a map point gets the same link. No seeded contact has a map point today. |
| Sorting (destination list) | "By name" (the server's order) or "Best rated first". Best rated: destinations with a Community Rating first, highest score first; the rest by Guest Feedback average, then by its review count. The two ratings are never combined into one number (Review.md 6.2); the page says so under the control. |

Not possible without the backend: a list of restaurants or resorts with their own names, map links and ratings, and sorting those by rating.

## P1: places inside a destination

**Owner:** Muhtasim (API, schema), Shahriar (place content and its sources). **Blocks:** the rest of update 1. **Priority:** to be decided by Shahriar; it is new scope after M1.

**What is missing.** A place is a named business or spot inside a destination, for example a restaurant or a resort. Today nothing in the schema or the API represents one.

**What the frontend needs.** The names below are a proposal; the backend decides the final contract in `Docs/api/API.md`.

1. **A list of places for a destination**, for example `GET /destinations/{destination_id}/places`, public and cacheable like the destination routes. Each place:
   - `id`
   - `type`: a fixed list. Proposal: `RESTAURANT`, `RESORT`, `HOTEL`, `ATTRACTION`, `TRANSPORT`, `OTHER`. Please confirm the list with Shahriar.
   - `name_bn`, `name_en`
   - `summary_bn`, `summary_en` (may be `null`)
   - `latitude`, `longitude` (may be `null`), or a `map_url`. The frontend builds the Google Maps link from the coordinates, so coordinates are enough.
   - `provenance` (source and verified date), the same shape as guide entries
   - the place's ratings, if places are to be rated (point 3)
2. **Filter and sort on the server**, if the list can be long: `type=`, `q=` (name search), `sort=best`, with the same cursor paging as the other lists. For a short list (under about 50 per destination) the frontend can filter and sort on the device and these are not needed.
3. **A decision on ratings for a place.** "Sorting to find the best" needs a rating for each place. Reviews are for a destination today (`destination_id`). The choices:
   - a review may name a place (an optional `place_id` on a review), and each place gets its own Community Rating and Guest Feedback under the rules of Review.md section 6; or
   - places are not rated, and are listed by name only.
   This changes the review form, the rating totals and the moderation screens, so it needs a decision in `Decisions.md` before any work.
4. **Offline packs.** If places are added, the pack content needs them too (`PackContent`, API.md 5.23), with a new `schema_version`.
5. **Sorting the destination list on the server** is not needed now: the list is five destinations and is sorted on the device.

**Done when:** the route is in `API.md` and `openapi-v1.json`, at least one destination has seeded places with sources, and the frontend can list them.

**Open question for Shahriar:** update 1 says "restaurant, resort". Are places part of the semester scope, or a later extension? The Gantt has vendor listings under "Extension: Vendors + Bookings" (VB01 to VB03, from 8 December). If places are the same thing as vendor offerings, P1 should be planned there.

## T1: tests for update 1

Run on the deployed site after this work is merged. Bangla and English each once.

| No. | Steps | Expected |
|---|---|---|
| T1.1 | Open Destinations. Set the sort control to "Best rated first". | Destinations with a Community Rating come first (highest first). Then destinations with Guest Feedback, highest average first. Then destinations with no rating, in name order. A line under the controls explains the order. |
| T1.2 | Set the control back to "By name". | The order is by English name, as before. |
| T1.3 | With "Best rated first" chosen, type a name in the search box. | The search still works and the result keeps the chosen order. |
| T1.4 | Open a destination. In "Travel guide", press each type button. | Only that type's entries show. The number on the button equals the number of entries shown. "All" shows everything. |
| T1.5 | Type a word that is in one entry (try a Bangla word, then an English word). | Only entries with that word in the title or text show, whichever language the page is in. |
| T1.6 | Choose a type, then search a word that is only in another type. | "Nothing in the guide matches" with a "Show everything" button. The button clears both. |
| T1.7 | Press "Open in Google Maps" in the destination header. | Google Maps opens in a new tab (or the Maps app on a phone) at the destination's point. |
| T1.8 | Airplane mode, open a saved destination or an offline pack. Use the type buttons and the search. | Both work offline. The Google Maps link needs a connection; that is expected. |
| T1.9 | Keyboard only: Tab to the type buttons and the search. | Each button can be reached and pressed with Enter or Space. A screen reader says which button is pressed. |
| T1.10 | Phone, 360 px wide. | The search and sort controls stack; the type buttons wrap; no sideways scrolling. |

**Checked by the frontend (11 Nov 2026):** T1.1, T1.2, T1.4, T1.6 and T1.7 in Chrome at desktop width, in Bangla, with the live data read through a read-only local proxy. **Not checked:** T1.8 to T1.10 (offline, keyboard with a screen reader, phone width).

---

## Update 2: what the frontend does now

Owner decisions (11 Nov 2026): the form does not ask for an overall rating; all seven category ratings are required; the overall rating is calculated from them; the Bayesian Community Rating and Guest Feedback still count the overall rating. Recorded in `Decisions.md` (2026-11-11) and as Review.md amendment A6, which still needs Shahriar's approval as scope owner.

| Part | Behaviour |
|---|---|
| Write a review | Seven category ratings, each 1 to 5, all required. No "Not applicable". No overall input. Under the list the form shows "Overall rating (calculated)": the stars, the whole number and the average to one decimal. |
| Formula | Mean of the seven ratings, rounded to the nearest whole number. Example: 5,5,5,5,4,4,4 gives 32 / 7 = 4.57, so 5. A mean of seven whole numbers never ends in exactly .5. |
| What is sent | The same request as before (API.md 5.2): `overall_rating` holds the calculated number and `category_ratings` holds all seven. |
| Edit a review | Ratings may be left alone. If the author changes any, all seven are required, and `overall_rating` is sent together with `category_ratings`. |
| Display | Unchanged everywhere. Older reviews keep the overall rating their author gave. |
| Saved drafts | A draft saved before this opens with its category ratings; the form asks for the missing ones. Its stored overall rating is ignored. |

## P2: the server calculates the overall rating

**Owner:** Muhtasim. **Priority:** medium. The web client works without it, but the rule is not enforced: a request made outside the web client can send any `overall_rating` with any number of categories.

1. **Calculate on the server.** On `POST /reviews/guest`, the Member create route and `PATCH` (API.md 5.2, 5.5): require all seven keys in `category_ratings` and set `overall_rating` to their mean, rounded to the nearest whole number. Please use the same formula as `overallFromCategories` in `frontend/src/api/reviews.ts`, so the number shown in the form is the number stored.
2. **Decide what happens to a sent `overall_rating`.** Proposal: keep accepting the field for now and refuse it only when it differs from the calculated value (`422`, field `overall_rating`). Deployed clients and saved offline drafts keep working, and the field can be removed later.
3. **`PATCH`:** `category_ratings: {}` (clear all) and a partial set should be refused once all seven are required. A `PATCH` that sends `overall_rating` alone should be refused.
4. **`GET /review-parameters` (API.md 5.15):** mark the categories as required and the overall rating as calculated, and update the `rating_rules` text, so the client and the server state the same rule. `backend/app/review_parameters.py` is the single source.
5. **Existing reviews.** They keep their stored overall rating (decision above). Please confirm that nothing recalculates them, including the nightly rating reconciliation (Review.md 6.3).
6. **Question: whole number or decimal?** Rounding loses detail (4.43 and 3.57 both become 4). If the Community Rating should use the exact mean, `overall_rating` would need a decimal column and the totals would change. The owner's decision is to keep the whole number; this is only a note in case the team wants more precision later.
7. **Documents to update after the change:** API.md 5.2, 5.5 and 5.15 (the line "The overall rating is never derived from the category ratings" already carries a note), `openapi-v1.json`, Review.md 3.1.

**Done when:** a request with six categories is refused; a request with seven stores the calculated overall rating whatever the client sent (or refuses a different one); the parity test for the review parameters passes.

## T2: tests for update 2

Run on the deployed site after this work is merged. Create test reviews only on a test destination or withdraw them afterwards.

| No. | Steps | Expected |
|---|---|---|
| T2.1 | Open Write a review. | Seven categories with five stars each. No overall rating to choose. No "Not applicable". |
| T2.2 | Rate three categories. | The line under the list says "3 of 7 rated; it appears when all are rated". |
| T2.3 | Fill everything else and press Submit with ratings missing. | Not sent. The message "Rate each of the seven categories from 1 to 5 stars" shows under the list, and focus goes to the first unrated category. |
| T2.4 | Rate 5,5,5,5,4,4,4. | "5 out of 5 (average 4.6)". |
| T2.5 | Change one 5 to 4 (5,5,5,4,4,4,4). | "4 out of 5 (average 4.4)". |
| T2.6 | Submit a review rated 3 in all seven. Check it with its receipt, and as a moderator. | Overall rating 3; all seven category ratings stored. |
| T2.7 | After it is published: the destination's Guest Feedback (or Community Rating for a Verified Member). | The average moves by the calculated overall rating, as for any review. |
| T2.8 | Member: My reviews, open a pending review, Edit, change only the title, Save. | Saved. The ratings and the overall rating are unchanged. |
| T2.9 | Same form: change one category rating on a review that has all seven. | Saved. The overall rating is the new calculated value. |
| T2.10 | Edit a review written before this update that has fewer than seven category ratings; change one rating and Save. | Not saved until all seven are rated; the message says so. |
| T2.11 | Guest: edit with a receipt, touch one rating only. | Same rule as T2.10. |
| T2.12 | Offline: write a review with all seven ratings, go online, submit it from Saved drafts. | Sent once, with the calculated overall rating. |
| T2.13 | Keyboard only, and with a screen reader. | Every star can be reached and chosen. The calculated overall rating is read out when it changes. |
| T2.14 | Phone, 360 px wide. | Stars are easy to press (44 px) and nothing scrolls sideways. |

**Checked by the frontend (11 Nov 2026):** T2.1, T2.2, T2.4, T2.5 and the message of T2.3, in Chrome at desktop width, in Bangla. **Not checked:** every test that submits or edits a review (T2.6 to T2.12), the focus move of T2.3, T2.13 and T2.14.

**Existing test documents to update (Irfan):** `R08-Rating-Test-Cases.docx` and any case that enters an overall rating by hand or submits a review with fewer than seven categories.

---

## Update 3: "Exit" for a guest

A guest who entered a name used to see "Sign out" in the sidebar card and on the `/guest` page. Both now read **Exit** (Bangla: "বের হোন"). A member still sees "Sign out". What the control does is unchanged: it forgets the typed name and opens the landing page; the guest tag, the visit dates and saved drafts stay.

**Backend:** nothing needed. A guest has no server session; no request is sent.

## T3: tests for update 3

| No. | Steps | Expected |
|---|---|---|
| T3.1 | Open `/guest`, enter a name, continue. Look at the sidebar card. | The card says "Welcome, <name> · Guest <tag>" with the buttons "Sign in" and "Exit". No "Sign out". |
| T3.2 | Open `/guest` again as that guest. | The links under the welcome read "Not <name>? Change name", "Exit" and "Start as a new guest". |
| T3.3 | Press "Exit" (sidebar, then repeat from `/guest`). | The landing page opens. The sidebar card shows "Guest <tag>" with the same tag as before and only "Sign in". |
| T3.4 | As a guest without a name. | No "Exit" and no "Sign out"; only "Sign in". |
| T3.5 | Sign in as a member. | The button reads "Sign out" and works as before, including the question about unsent drafts. |
| T3.6 | Repeat T3.1 in Bangla. | The button reads "বের হোন". |

**Checked by the frontend (11 Nov 2026):** T3.1 to T3.4 and T3.6 in Chrome at desktop width, in Bangla. **Not checked:** T3.5 (needs a member account) and the English label.
