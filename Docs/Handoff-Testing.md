# Testing handoff: R12 offline and installable app

**From:** Abdullah (frontend). **Date:** 6 November 2026.
**For:** Irfan (R18 offline QA), and anyone checking R12.
**What R12 promises:** the app installs on a phone, and a destination page opened while online reopens with no connection (Gantt R12 acceptance: "Selected page reopens on real phone in airplane mode").

## Before you start

| Needed | Why | Status |
|---|---|---|
| `abd` merged to `main` and deployed (DEP1) | The live site needs offline mode | **Done (7 Nov 2026)** |
| Live API sends `public, max-age=60` on destination routes | Otherwise nothing is saved for offline | **Confirmed (7 Nov 2026)** |
| R13 offline packs and R15 part 1 deployed (DEP2 in `Handoff-Backend.md`) | Needed for the pack tests (section H) | **Done (8 Nov 2026)**, PR #55 |
| Turnstile site key on Vercel (TS1) | Needed to send a guest review on the live site | **Key in the live bundle (8 Nov 2026)**; one live submission still to confirm |
| An Android phone with Chrome (Android 10+), and if possible an iPhone with Safari (iOS 16.4+) | PF 19.1 targets | |

**R12 (sections A to F) can be tested on `https://abhijatri.vercel.app` now. R13 packs and R15 drafts need DEP2 first; until then run them locally.** Sections A to F can also be run **locally** on a computer: `cd frontend && npm run preview:offline`, then open `http://localhost:4173`. The local backend must be running with a working database (see B6). Offline mode is **off** in `npm run dev` on purpose, so do not test offline there.

How to simulate, on a computer, in Chrome DevTools (F12):
- **No connection:** Network tab → throttling → *Offline*.
- **Slow phone network:** Network tab → add a custom profile: 400 kbps down, 400 kbps up, 400 ms latency (PF 19.4 "Abhijatri Slow 3G").
- **Server outage with internet on:** stop the backend (`Ctrl+C` in its terminal).
- **Start fresh:** Application tab → Storage → *Clear site data*.

For each test record: device and browser, pass or fail, a screenshot when it fails.

---

## A. Install

| # | Steps | Expected |
|---|---|---|
| A1 | Open the site in Chrome on Android. | Chrome offers "Install app" or "Add to Home screen". |
| A2 | Install it, open it from the home screen. | Opens full screen (no address bar), green theme colour, compass icon, name "অভিযাত্রী". |
| A3 | iPhone Safari: Share → Add to Home Screen. | Icon is the green compass; opens full screen. |

## B. Offline pages (the R12 acceptance test)

| # | Steps | Expected |
|---|---|---|
| B1 | Fresh start. Online, open **Destinations**, then open **Bandarban**. Wait until it has loaded. | Page shows. |
| B2 | Switch on **airplane mode**. Close the app completely, reopen it. | The app opens (no browser "no internet" page). |
| B3 | Go to Bandarban (sidebar → Destinations → Bandarban). | The full guide shows: advisories, restrictions, emergency contacts. A banner says you are offline and these are saved copies. |
| B4 | Open **Destinations** while still offline. | **Only Bandarban** is listed, with "You are offline. Showing the 1 destination(s) saved on this device". |
| B5 | Open **Overview** and the **landing page** offline. | Only Bandarban appears. Overview hides the site-wide count tiles. |
| B6 | Open a destination you never opened online (type its address, or from an old link). | "This destination is not saved on this device…" with a link to saved destinations. Never "Something went wrong". |
| B7 | Fresh start, go offline **before** opening any destination, open Destinations. | "No destinations saved on this device" and how saving works. |
| B8 | Turn airplane mode off. | Banner briefly says "Back online"; lists show all destinations again. |

## C. Server outage (internet on, server down)

| # | Steps | Expected |
|---|---|---|
| C1 | Open Bandarban online. Stop the backend. Open Destinations. | Only Bandarban, with "**The server cannot be reached**…" (not "You are offline"). |
| C2 | Open Bandarban. | The saved copy shows. |
| C3 | Open a destination never opened. | Title "The server cannot be reached", message that it is not saved. |
| C4 | If signed in as a member: open **My reviews** or **Notifications**. | "Account pages need a connection" with Try again, **not** "Sign in". The sidebar says the sign-in cannot be checked. |
| C5 | Start the backend again, wait up to 30 seconds. | Account pages recover by themselves. |

## D. Persistence

| # | Steps | Expected |
|---|---|---|
| D1 | Save Bandarban (open it online). Close the browser fully, reopen offline. | Bandarban still opens. |
| D2 | Keep the phone offline for several hours, reopen. | Still opens. |
| D3 | Open Bandarban again online after a day. | The saved copy is refreshed (new "saved" time). |
| D4 | After 7 days without opening it online. | It is no longer offered offline (PF 18.4: older copies are never shown as current). |
| D5 | Change language and theme, reload offline. | Both are kept. |
| D6 | Deploy a new version while the app is open. | A box says a new version is available with **Reload**; nothing changes until you press it; saved destinations are still there afterwards. |
| D7 | Phone nearly full (fill storage), then reopen offline. | Note whether saved pages survive. The browser may delete them; the app must not crash. (Persistent storage is requested but the browser decides.) |

## E. Data and images

| # | Steps | Expected |
|---|---|---|
| E1 | Offline, open the landing page and a destination with review photos. | No broken images. Panels show an icon on a dark background; review photos say they will show when back online. |
| E2 | Turn on Chrome **Lite mode / Data Saver** (or a 3G-class connection), open the landing page. | Only the small photo versions load (`*-480.webp`); review photos load only after tapping "Show … (uses data)". |
| E3 | Slow 3G profile, fresh start, open a destination. | Destination name and summary visible within 5 seconds (PF 19.4). |
| E4 | Low-end phone (under 4 GB memory or 4 cores) or Data Saver. | The green background is still, not animated. |

## F. Privacy (must pass)

| # | Steps | Expected |
|---|---|---|
| F1 | Sign in, use account pages, then DevTools → Application → Cache Storage. | No URLs containing `session`, `account`, `receipt`, `notification`, `report`, `guest` in any cache. |
| F2 | Same, check for review submission responses. | Not cached. |
| F3 | Offline, try to write a review. | Live site today: message that sending a review needs a connection. After DEP2: the form opens offline, saves the draft and keeps Send disabled with "Your draft is saved on this device" (guideline D1). |

## G. States that were fixed in the audit (quick re-check)

| # | Check | Expected |
|---|---|---|
| G1 | Bangla mode: rating filter on a destination's reviews. | "৫ তারকা … ১ তারকা" (Bangla digits). |
| G2 | Bangla mode, offline notice count. | "১টি", not "1টি". |
| G3 | Receipt page: press "অবস্থা দেখুন" with empty fields. | Format error shown and the cursor moves to the review ID field. |
| G4 | Destinations search for "zzzz". | "No destination matches…" with Clear search. |

---

## H. Offline packs (R13) and offline drafts (R15 part 1): manual tests

**Added 8 November 2026.** Run on `https://abhijatri.vercel.app` (DevTools → Network → *Offline*, or airplane mode on a phone) or locally with `npm run preview:offline`. The last column is the result of the Chrome run on 8 Nov 2026 against a local backend and database: **Pass**, **Fail** (see F1 to F3 in `Handoff-Backend.md`) or **Not run** (needs a real phone, a full disk or a staff screen).

**On a computer:** DevTools *Offline*, Wi-Fi off, or stopping the server all work since the F2 fix. With the server stopped, wait 60 seconds after the last online visit, because the browser may still answer from its own short HTTP cache.

### H1. Download and storage

| # | Steps | Expected | 8 Nov |
|---|---|---|---|
| H1.1 | Online, English, open Bandarban. | Box "Keep the guide… readable without internet" and **Save for offline use (… KB)**. | Pass (10 KB) |
| H1.2 | Press Save for offline use. | Becomes "Saved for offline use · Snapshot: date · size" with an **Offline packs** link. | Pass |
| H1.3 | Open **Offline packs** in the sidebar (no "Soon" mark). | Bandarban: snapshot date, size, review count, **Valid until** (7 days later), state **Ready**, Open / Update / Delete. "Storage on this device" shows whether the browser keeps data and the space used. | Pass |
| H1.4 | DevTools → Application → IndexedDB → `abhijatri-offline`. | Stores `packs`, `drafts`, `meta` only. `packs` has one row keyed by the destination id. | Pass |
| H1.5 | Save a second destination (Sylhet). | Both listed. | Pass |
| H1.6 | Private / Incognito window, save a pack. | Honest "saving unavailable" or a working save; the site keeps working, no crash. | Not run |
| H1.7 | Phone nearly full, save a pack. | "Storage is full"; old packs intact; no crash. | Not run |
| H1.8 | Start a download, switch to Offline before it finishes. | "Download failed" with Retry; an older pack of the same place stays. | Not run (unit-tested) |

### H2. Reading offline

| # | Steps | Expected | 8 Nov |
|---|---|---|---|
| H2.1 | Go offline. Open Destinations. | "You are offline. Showing the N destination(s) saved on this device"; the pack's Guest Feedback score and count show. | Pass |
| H2.2 | Open Bandarban. | Yellow "You are offline" banner, a second banner "You are reading the offline copy made on … Advisories verified on …". Guide, advisories, restrictions, emergency numbers all show, with no 4-second wait. | Pass |
| H2.3 | Scroll to Traveller reviews. | "Offline copy (date): the newest N published reviews." Reviews listed; no filters, no Load more; photos say they open when online. | Pass with real offline. Server down only: failed on first run (F2), **Pass after the fix** (allow 60 s after the last online visit: the browser's own `max-age=60` cache can still answer) |
| H2.4 | Offline, open a destination that was never saved. | "This destination is not saved on this device…", never "Something went wrong". | Pass (R12, unchanged) |
| H2.5 | Close the browser completely, reopen offline, open the pack. | Opens. | Not run |
| H2.6 | Phone: save, airplane mode, restart the phone, open from the home-screen app. | Opens full screen with the guide. | Not run (real phone) |

### H3. Expiry and advisories

| # | Steps | Expected | 8 Nov |
|---|---|---|---|
| H3.1 | Set the device date 8 days ahead (or wait), open Offline packs offline. | Red "Out of date: update when online"; Valid until is in the past. | Pass (expiry edited in IndexedDB) |
| H3.2 | Open that pack's guide. | Red "Out of date. This offline copy is from …" banner **and no advisory labelled Current**. | Fail on first run (F1); **Pass after the fix** ("Out of date offline copy: check when online"; Bangla "পুরনো অফলাইন কপি…") |
| H3.3 | An advisory whose `valid_until` is today: open offline, then set the date to tomorrow. | It disappears on the next Dhaka day, with no network. | Not run (unit-tested in `advisoryState.test.ts`) |
| H3.4 | Set the date back, go online. | State returns to Ready (or the pack updates). | Pass |

### H4. Updates after reconnect

| # | Steps | Expected | 8 Nov |
|---|---|---|---|
| H4.1 | Save a pack. Have a new review published by staff. Reload the app online. | Pack updates by itself: review count rises, snapshot changes. | Pass (0 to 3 reviews) |
| H4.2 | Staff hides one of those reviews. Go offline, then back online, wait 5 seconds. | The hidden review is gone from the pack before it shows as current. | Pass (3 to 2) |
| H4.3 | Staff archives the destination. Offline, then online. | Notice "Bandarban has been withdrawn, so its offline pack was removed"; the list is empty. | Pass |
| H4.4 | Online with the server down (or `503`), then reconnect. | Packs are kept; nothing deleted on a failed check. | Pass |
| H4.5 | Server comes back while the device stays online. | Packs are not checked until the next app start or offline-to-online change. | Known limit (F3) |

### H5. Delete

| # | Steps | Expected | 8 Nov |
|---|---|---|---|
| H5.1 | Offline packs → Delete on Sylhet. | Dialog "Delete the offline pack for Sylhet?" with Cancel and Delete. | Pass |
| H5.2 | Cancel. | Nothing removed. | Pass |
| H5.3 | Delete. | Sylhet gone from the page and from IndexedDB; Bandarban kept. | Pass |
| H5.4 | Sign out (as a member) with packs saved. | Packs remain; no account data left in IndexedDB or caches. | Not run |

### H6. Offline review drafts (R15 part 1)

| # | Steps | Expected | 8 Nov |
|---|---|---|---|
| H6.1 | Offline, open a pack, press **Write a review**. | The form opens; the destination list offers only saved destinations. | Pass |
| H6.2 | Offline with nothing saved, open Write a review. | Explains a guide must be saved first. | Not run |
| H6.3 | Type a name and pick 4 stars, wait 1 second, reload offline. | "Your saved draft was restored. Draft saved on this device (date), not encrypted." with **Delete draft**; the fields are back. | Pass |
| H6.4 | Delete draft. | Asks first; the draft is gone from IndexedDB `drafts`. | Not run |
| H6.5 | Online, submit the restored draft. | Receipt shown once; the draft and its stored receipt leave IndexedDB. | Pass |
| H6.6 | Queue a draft offline, reconnect. | Nothing sends by itself. After R15 part 2 is deployed, see H9. | Pass (nothing auto-sent) |

### H9. Sending saved drafts (R15 part 2): run after it is deployed

Built 9 Nov 2026 on `abd`, not on the live site yet. Use a **test** review and withdraw it afterwards with its receipt. For a lost response use the Console snippet of `Offline-Frontend-Guideline.md` 9.6.

| # | Steps | Expected |
|---|---|---|
| H9.1 (D5) | Write a draft offline, go to Overview, reconnect. | A green banner "You have 1 unsent review draft..." and a count on **Write a review**. Nothing is sent by itself (Network tab). |
| H9.2 (D6) | Review and send, Open, security check, Submit. | Receipt shown; the draft leaves the list. |
| H9.3 (D7) | Run the snippet, Submit, then Submit again. | First "Could not send. Your draft is safe...", then "This review was already submitted". **One** review. |
| H9.4 (D11) | Run the snippet, Submit, change the title, Submit. | Receipt screen says the first version was received and offers "Edit it with the receipt". |
| H9.5 (D9) | Submit and close the tab at once; reopen the Write page. | The draft is ready again (or the receipt is shown if it was received); a retry makes one review. |
| H9.6 (D10) | With a draft unsent, **Start as a new guest**, then send it. | It is published under the **old** guest tag; one review. |
| H9.7 | Close the receipt screen without pressing Done; reopen Write a review. | The receipt is shown again with "saving its receipt was not confirmed yet". After Done it is gone from IndexedDB `drafts`. |
| H9.8 (D16, D17) | Delete one draft; Clear all; Export with and without "include receipts". | Each delete asks first. The file has a receipt only when ticked; never the guest scope secret or a submitted review's receipt. |
| H9.9 (D20) | As a member with an unsent draft, Sign out. | Asked: keep or delete. Kept drafts show again only after signing in to the same account. |
| H9.10 (D22) | Queue four guest drafts offline, reconnect, send all. | Three send; the fourth stays, says when it can be sent, and Submit sends nothing before then. |
| H9.11 | Application, IndexedDB, `meta`. | `guest_scope_secret` equals Local Storage `abhijatri_guest_scope`. |

### H7. Retry without duplicates (R16, guideline group R)

Paste the snippet from `Offline-Frontend-Guideline.md` 9.6 in the Console before each case; it lets the request reach the server and then reports a network failure.

| # | Steps | Expected | 8 Nov |
|---|---|---|---|
| H7.1 (R1) | Submit a guest review, then press Submit again. | First "Could not reach the server"; then "This review was already submitted" with the receipt. **One** review in the database. | Pass |
| H7.2 (R2) | Receipt page → Edit → change the title → Save, then Save again. | "Saved"; the second answer has `Idempotent-Replayed: true`. | Pass |
| H7.3 (R3) | Receipt page → Withdraw → Yes, then Yes again. | "Withdrawn"; second answer `Idempotent-Replayed: true`. | Pass |
| H7.4 (R4) | Network tab on each write. | `Idempotency-Key` header; the same value on a retry. | Pass |
| H7.5 (R5) | After a failed save, change the text and save. | A **new** key; never `409 IDEMPOTENCY_KEY_REUSED`. Because the lost save was applied, the server answers `409 REVIEW_VERSION_CONFLICT` and the form says "This review changed while you were editing. Reload…", keeping your text. | Pass |
| H7.6 (R6) | Register or reset with `password123`. | "This password appears in a known data breach." | Not run |

### H8. Privacy (must pass)

| # | Steps | Expected | 8 Nov |
|---|---|---|---|
| H8.1 | After all of the above: Application → Cache Storage. | Only the precache, fonts and `abj-public-api-v1` (destination and review lists). No `session`, `account`, `receipt`, `notification`, `report`, `guest`, `auth` or pack URLs. | Pass |
| H8.2 | Application → IndexedDB. | `packs`, `drafts`, `meta` only; no tokens; no receipt of a submitted review. | Pass |
| H8.3 | Application → Local Storage. | Language, theme, visit dates and `abhijatri_guest_scope` only. | Pass |

---

## Known limits (not bugs)

- Installability cannot be checked on plain `http://localhost` with automated Chrome; use HTTPS (the deployed site).
- `navigator.storage.persisted()` may be `false`; the browser decides. R13 shows it on the Offline packs page ("Storage on this device").
- R13 packs and R15 part 1 drafts are live (PR #55). Section H covers them. R15 part 2 (sending saved drafts) is built on `abd` (9 Nov 2026) and not deployed; run H9 once it is live.
- First visit only: the service worker controls the tab after the next reload. A first-time visitor who goes offline in that same tab and opens a page not loaded yet gets a blank page (F4 in `Handoff-Backend.md`). Test offline after one reload.
- Pack freshness runs on app start and when the device goes from offline to online, not when only the server comes back (F3 in `Handoff-Backend.md`).

## Where to report

Add failures to `Frontend-Implemented.md` section 6 as a new row (next free ID), or tell Abdullah with the test number (for example "B4 fails on Samsung A12, Chrome 130") and a screenshot.
