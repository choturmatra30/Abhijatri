# Handoff: Phase 1 updates (backend and testing)

**From:** Abdullah (frontend). **Started:** 11 November 2026.
**For:** Muhtasim (backend), Irfan (testing), Shahriar (content, merges).
**Update, 12 November 2026 (backend):** P2, P4a, P4b, P4c, P4d and P5 are built and tested (`Decisions.md` 2026-11-12; API.md 5.2, 5.5, 5.5a, 5.15). The web client now has the keyword search, the Reported filter and a guest "My reviews"; the note fallback is 1. **Still open:** P1 (places). All manual test cases are in `QA-Phase1-Manual-Test-Cases.md`.
**What this is:** five updates were requested for the Phase 1 (M1) frontend. This file lists, for each one, what the frontend did, what it needs from the backend, and what to test. It is updated as each update is done. Evidence for the frontend work: `Frontend-Implemented.md` section 5n. Other open items stay in `Handoff-Backend.md` and `Handoff-Testing.md`.

| No. | Update requested | Frontend | Needs backend | Needs testing |
|---|---|---|---|---|
| 1 | Places inside a destination by type (restaurant, resort, ...), with name and Google Maps link; sorting to find the best | **Part done (11 Nov 2026):** type filter and search on the guide, Google Maps links, "Best rated first" on the destination list | **Yes: [P1](#p1-places-inside-a-destination)** | [T1](#t1-tests-for-update-1) |
| 2 | Remove the overall rating; calculate it from the parameter ratings | **Done in the web client (11 Nov 2026)** | **Yes: [P2](#p2-the-server-calculates-the-overall-rating)** | [T2](#t2-tests-for-update-2) |
| 3 | "Exit" instead of "Sign out" for a guest | **Done (11 Nov 2026)** | No | [T3](#t3-tests-for-update-3) |
| 4 | No search by review ID and receipt; "My reviews" with keyword search; remove the 20-character limit | **Part done (11 Nov 2026):** members are sent to "My reviews". The rest waits for the backend | **Yes: [P4a](#p4a-a-guests-own-reviews-without-the-review-id-and-receipt), [P4b](#p4b-keyword-search-in-my-reviews), [P4c](#p4c-which-of-my-reviews-were-reported), [P4d](#p4d-remove-the-20-character-minimum-of-the-review-note)** | [T4](#t4-tests-for-update-4) |
| 5 | Hamburger side menu for the moderation queue | **Done in `staff/` (11 Nov 2026)**; not live until the bundle is rebuilt | **Yes: [P5](#p5-rebuild-the-staff-bundle-and-review-the-change)** | [T5](#t5-tests-for-update-5) |

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

---

## Update 4: finding your own reviews

Requested: a user should not search for a review by review ID and receipt; "My reviews" shows their published, rejected, reported and hidden reviews, with keyword search; remove the 20-character limit. Owner decisions (11 Nov 2026) are in `Decisions.md`.

**What the frontend did now (members only):**

| Part | Behaviour |
|---|---|
| Sidebar, "Reviews" group | A member sees "Write a review" and "My reviews". A guest still sees "Write a review" and "Check with receipt". |
| Write a review page | For a member the link under the form goes to My reviews. |
| My reviews | Unchanged filters: status (all statuses, including Published, Rejected and Hidden) and destination. A new line at the end links to "Check with receipt" for a review written as a guest before the account existed. |

**What is not built, and why:** everything below needs the server. "Check with receipt" stays for guests until P4a is done, so no guest loses access to a review.

## P4a: a guest's own reviews without the review ID and receipt

**Owner:** Muhtasim (API), with a security decision by Muhtasim and Shahriar. **Blocks:** removing "Check with receipt" for guests. **Priority:** high for this update.

**Problem.** A guest has no account. Today a guest proves ownership with the review ID and the receipt (API.md 5.1, 5.3). Receipts of submitted reviews are never stored on the device (PF 13.5), so the app cannot remember them for the guest.

**What the frontend needs:** a way to list the reviews made from this browser, so the guest can open "My reviews" and see each review's status. Two possible designs; the backend chooses:

1. **List by guest scope.** A route such as `POST /reviews/guest/mine` with `guest_scope_secret` in the JSON body (never in the URL, API.md section 1). The server matches the stored guest scope digest and returns the same summary fields as `GET /reviews/mine` (`id`, `destination_id`, `status`, `version`, `overall_rating`, `title`, `visit_month`, `created_at`, `published_at`, `appeal_deadline`), with the same `status`, `destination_id`, `after` and `limit` options.
   - **Security question:** PF 14.1 and Platform-Foundation line "A client-generated guest scope is not a primary abuse boundary" treat the scope as a supplemental signal. Using it to read a guest's own review statuses makes it a read credential. Is that acceptable for read-only status? The scope secret lives in `localStorage` and IndexedDB (Decisions 2026-11-08).
   - **Actions still need proof.** Edit, withdraw and appeal use the receipt today. Either they keep needing the receipt (then the guest still types it for those actions), or the scope secret is accepted for them too. Please decide; the second choice changes PF 13.
2. **Keep receipts on the device.** Change PF 13.5 so the device may keep the receipts of submitted reviews (for example encrypted, with a clear warning and a "forget" control). The app then lists and manages the guest's reviews with no new route, using `POST /review-receipts/status` for each. This is a policy change, not an API change, and it weakens the current rule that a stolen device cannot reveal receipts.

Both designs work only on the browser that wrote the review. A guest on a new device still needs the receipt or an account.

**Done when:** the decision is in `Decisions.md`, the route (or the PF 13.5 change) is documented, and a guest can see the status of reviews written from this browser without typing an ID or a receipt.

## P4b: keyword search in "My reviews"

**Owner:** Muhtasim. **Blocks:** the search box (the owner decided not to build a search on the device). **Priority:** medium.

- Add `q=` to `GET /reviews/mine` (and to the guest list of P4a): match the title and the text of the current revision, case-insensitive, Bangla and English. Proposal: 1 to 100 characters after trimming; an empty `q` means no filter.
- Keep the existing `status`, `destination_id`, `after` and `limit`; the cursor must stay valid for a given `q`.
- Optional and useful: include a short `body_excerpt` in each item, so the list can show where the word was found.

**Done when:** `GET /reviews/mine?q=sunrise` returns only the member's reviews with that word in the title or text. The frontend then adds the search box (about one day).

## P4c: which of my reviews were reported

**Owner:** Muhtasim, with a privacy decision by Shahriar. **Blocks:** the "Reported" filter. **Priority:** low to medium.

The author of a review is not told today that someone reported it. The request is a filter in "My reviews" for reviews that other people reported.

- **Decision needed first:** should an author see that a review was reported, and when? Risks: an author can guess who reported it, or edit the review to avoid a decision. A safer rule could be to show it only after a moderator has decided the report.
- **If yes, the frontend needs:** a field on each list item, for example `reported: true` or `open_report_count`, and a filter `reported=true` on `GET /reviews/mine`. Never the reporter's identity or the report text.
- "Hidden" needs nothing new: it is already a status and is in the status filter.

## P4d: remove the 20-character minimum of the review note

**Owner:** Muhtasim. **Priority:** medium; small change.

- `NOTE_MIN = 20` in `backend/app/review_parameters.py` is used by the create and edit schemas (`schemas.py`) and published by `GET /review-parameters`. Proposal: `NOTE_MIN = 1`, so the note stays required but may be short. **Please confirm the number with Abdullah before changing it.**
- The frontend reads `note.min_length` from `/review-parameters` and needs no change while online. Its offline fallback is 20 in three files (`GuestReviewForm.tsx`, `ReviewEditForm.tsx`, `GuestEntryPage.tsx`); Abdullah changes these in the same release as the backend change. Changing them earlier would let the form send notes the server refuses.
- Documents to update with the change: API.md 5.2 ("`body` 20 to 6000") and 5.15, `openapi-v1.json`, and the parity test of the review parameters.
- Not included: the appeal statement's own minimum of 20 characters (API.md 5.6). Say so if that should change too.

## T4: tests for update 4

Run on the deployed site after this work is merged.

| No. | Steps | Expected |
|---|---|---|
| T4.1 | As a guest, open the sidebar "Reviews" group. | "Write a review" and "Check with receipt". |
| T4.2 | Sign in as a member; open the "Reviews" group. | "Write a review" and "My reviews". No "Check with receipt". |
| T4.3 | Member: press "My reviews" in the group. | `/account/reviews` opens; the group stays open and "My reviews" is highlighted. |
| T4.4 | Member: open Write a review and look under the form. | The link reads "Already reviewed? Find it in My reviews" and opens My reviews. |
| T4.5 | Guest: the same place. | The link reads "Already reviewed? Check it with your receipt". |
| T4.6 | Member: My reviews, status filter Published, then Rejected, then Hidden. | Only reviews with that status are listed each time. |
| T4.7 | Member: bottom of My reviews. | A line "Wrote a review as a guest, before you had an account? Check it with its receipt"; the link opens the receipt page. |
| T4.8 | Type `/reviews/receipt` in the address bar as a member. | The page still opens (a member may hold an older guest receipt). |
| T4.9 | Sign out. | The group shows "Check with receipt" again. |

**Checked by the frontend (11 Nov 2026):** none in a browser; all of these need a member account. Types, unit tests and build pass. **After the backend work:** tests for the guest list, the search box, the "Reported" filter and a short note will be added here.

---

## Update 5: side menu for the moderation dashboard

The staff dashboard (`staff/`, served by the API at `/staff`) showed its ten sections as a row of buttons in the top bar. They are now in a side menu that a hamburger button opens and closes.

| Part | Behaviour |
|---|---|
| Hamburger button | Top left, before the title. Says "Open menu" or "Close menu" to a screen reader. |
| Wide screen (960 px and more) | The menu starts open on the left, beside the page. The button hides it to give the page the full width. |
| Narrow screen | The menu starts closed. The button slides it over the page. It closes when a section is chosen, on Escape, or on a press outside it. |
| Sections | The same ones, in the same order, with the same role rule (Staff and Notifications only for a superadmin). The current section is highlighted and its name is shown next to the title. |
| Not changed | Every screen, every API call, sign-in, the language and Sign out buttons. |

Files: `staff/src/App.tsx`, `staff/src/styles.css`. Nothing else in `staff/` changed.

## P5: rebuild the staff bundle and review the change

**Owner:** Muhtasim (the staff app and the bundle), Shahriar (merge and deploy). **Priority:** medium; the change is not live until this is done.

1. **Review.** The staff app is Muhtasim's; this change was made by Abdullah at the owner's request. Please read the diff of `staff/src/App.tsx` (the shell only).
2. **Rebuild the bundle.** The API serves the copy in `backend/app/staff_site`, which is a committed build. Run `make staff-bundle`, commit `backend/app/staff_site`, and deploy. Abdullah did not run it, because it rewrites files under `backend/`.
3. **Content-Security-Policy.** The change adds no inline style and no new script, font or image, so `STAFF_HEADERS` in `backend/app/staff_site.py` needs no change. It uses the `inert` attribute (supported by current Chrome, Edge, Firefox and Safari).
4. **Check with a real sign-in.** The frontend check used a stand-in API with a made-up session, so it could not open real tasks. Please confirm the queue, a lease countdown and a decision still work with the menu open and closed.

**Done when:** `/staff` on the deployed API shows the hamburger button and the side menu.

## T5: tests for update 5

Run on the deployed `/staff` after P5, signed in as staff.

| No. | Steps | Expected |
|---|---|---|
| T5.1 | Sign in as a superadmin on a laptop. | A side menu on the left with ten sections; Queue is highlighted; the top bar reads "Moderation dashboard · Queue". No row of section buttons in the top bar. |
| T5.2 | Sign in as a moderator. | Eight sections: no Staff and no Notifications. |
| T5.3 | Choose each section in turn. | The screen changes, the chosen section is highlighted, the top bar shows its name, and the menu stays open. |
| T5.4 | Press the hamburger button. | The menu hides and the page uses the full width. Press again: it returns. |
| T5.5 | Claim a task, then open and close the menu, then decide the task. | The claim, the countdown and the decision are not affected. |
| T5.6 | Phone or a window under 960 px wide. | The menu is closed at first. The button opens it over the page with a dark backdrop. |
| T5.7 | Narrow: choose a section. Then open the menu and press outside it. Then open it and press Escape. | Each closes the menu. After a choice, the chosen section is shown. |
| T5.8 | Narrow, keyboard only: open the menu and press Tab repeatedly. | Focus starts on the current section and stays inside the menu; the page behind cannot be reached. After closing, focus is on the hamburger button. |
| T5.9 | Switch to Bangla. | The menu shows the Bangla section names; the button's label is Bangla for a screen reader. |
| T5.10 | Both widths. | Nothing scrolls sideways. |

**Checked by the frontend (11 Nov 2026):** T5.1, T5.3, T5.4, T5.6, T5.7, the focus part of T5.8 and T5.10, in Chrome with a stand-in API (a made-up superadmin session and empty lists). **Not checked:** T5.2, T5.5, T5.9, Tab staying inside the menu, a real phone.
