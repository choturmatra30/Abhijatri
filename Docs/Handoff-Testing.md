# Testing handoff: R12 offline and installable app

**From:** Abdullah (frontend). **Date:** 6 November 2026.
**For:** Irfan (R18 offline QA), and anyone checking R12.
**What R12 promises:** the app installs on a phone, and a destination page opened while online reopens with no connection (Gantt R12 acceptance: "Selected page reopens on real phone in airplane mode").

## Before you start

| Needed | Why | Status |
|---|---|---|
| `abd` merged to `main` and deployed (DEP1) | The live site needs offline mode | **Done (7 Nov 2026)** |
| Live API sends `public, max-age=60` on destination routes | Otherwise nothing is saved for offline | **Confirmed (7 Nov 2026)** |
| R13 offline packs and R15 part 1 deployed (DEP2 in `Handoff-Backend.md`) | Needed for the pack tests (guideline group P) and the draft tests below | **Not yet (7 Nov 2026)**: R12 tests only on the live site for now |
| Turnstile site key on Vercel (TS1) | Needed to send a guest review on the live site | **Not yet (7 Nov 2026)** |
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

## Known limits (not bugs)

- Installability cannot be checked on plain `http://localhost` with automated Chrome; use HTTPS (the deployed site).
- `navigator.storage.persisted()` may be `false`; the browser decides. R13 shows it on the Offline packs page ("Storage on this device").
- R13 packs and R15 part 1 drafts are built but not deployed yet (DEP2). Their test cases are `Offline-Frontend-Guideline.md` 9.4 (group P) and 9.5 (D1 to D4, D16 and D2 now; the rest after R15 part 2).
- Sending queued drafts on reconnect (R15 part 2) waits for question Q1.

## Where to report

Add failures to `Frontend-Implemented.md` section 6 as a new row (next free ID), or tell Abdullah with the test number (for example "B4 fails on Samsung A12, Chrome 130") and a screenshot.
