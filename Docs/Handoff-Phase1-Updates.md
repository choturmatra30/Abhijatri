# Handoff: Phase 1 updates (backend and testing)

**From:** Abdullah (frontend). **Started:** 11 November 2026.
**For:** Muhtasim (backend), Irfan (testing), Shahriar (content, merges).
**What this is:** five updates were requested for the Phase 1 (M1) frontend. This file lists, for each one, what the frontend did, what it needs from the backend, and what to test. It is updated as each update is done. Evidence for the frontend work: `Frontend-Implemented.md` section 5n. Other open items stay in `Handoff-Backend.md` and `Handoff-Testing.md`.

| No. | Update requested | Frontend | Needs backend | Needs testing |
|---|---|---|---|---|
| 1 | Places inside a destination by type (restaurant, resort, ...), with name and Google Maps link; sorting to find the best | **Part done (11 Nov 2026):** type filter and search on the guide, Google Maps links, "Best rated first" on the destination list | **Yes: [P1](#p1-places-inside-a-destination)** | [T1](#t1-tests-for-update-1) |
| 2 | Remove the overall rating; calculate it from the parameter ratings | Not started | To be listed | To be listed |
| 3 | "Exit" instead of "Sign out" for a guest | Not started | To be listed | To be listed |
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
