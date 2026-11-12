# Manual test cases: Phase 1 updates, moderation dashboard and user dashboard

**For:** Md. Irfan Iqbal (QA). **Prepared:** 12 November 2026. **Covers:** the five Phase 1 updates (`Handoff-Phase1-Updates.md`), the backend work of 12 November (P2, P4a to P4d, P5), every section of the staff (moderation) dashboard, and every section of the member (user) dashboard.

**How to use this file**
- Each row is one small check. Do the **Steps** and compare with **Expected**.
- Write **P** (pass), **F** (fail) or **B** (blocked) in **Result**. For F, add the bug ID or a short note in **Notes**.
- **Auto (12 Nov)** shows what the development run already checked. "API ✔" means the same rule passed over real HTTP on the local stack (section 11). "Unit ✔" means an automated backend or frontend test covers it. A blank cell means it has only been checked by hand, or not at all. Run it by hand anyway; automated checks do not replace this pass.
- Run each section **in English and once in Bangla** unless the row says otherwise. Where a Bangla text is given, check it exactly.

---

## 0. Setup

### 0.1 Where to test

| Target | Member app | Staff app | API |
|---|---|---|---|
| Local stack (recommended first) | `http://localhost:5180` | `http://localhost:5185` (or the API's own copy at `http://localhost:8100/staff/`) | `http://localhost:8100/api/v1` |
| Deployed (after merge and deploy) | `https://abhijatri.vercel.app` | `/staff` on the deployed API | `https://abhijatri-backend.up.railway.app/api/v1` |

The local stack is Docker Desktop with `supabase start` (database `abhijatri_local` on `127.0.0.1:54322`, Mailpit on `:54324`), the API started with `backend/.env.localstack`, and `npm run dev` in `frontend/` and `staff/` with `VITE_API_BASE_URL=http://localhost:8100`. **Never run the destructive cases (reports, hide, suspend, role changes) on production.**

### 0.2 Accounts you need

| Role | What it is for | How to get it |
|---|---|---|
| Guest (no account) | Guest review, Exit, guest "My reviews" | Open `/guest`, type a name |
| Member A ("Nila") | Writes reviews, My reviews, search, reported filter | Register, confirm the email (Mailpit locally) |
| Member B ("Rafi") | Reports Member A's review | Register a second account |
| Moderator | Moderation dashboard without superadmin screens | Must be a Verified Member first (rule P-02), then `make moderator EMAIL=...` |
| Superadmin | All ten dashboard sections | `make superadmin EMAIL=...` or the bootstrap command |

Staff sign-in always needs an authenticator app (TOTP). Use **two browser profiles** (or `user.localhost` and `mod.localhost`) so the member and staff cookies do not mix.

### 0.3 Test data

- At least one published destination (five are seeded: Bandarban, Cox's Bazar, Sajek Valley, Sundarbans, Sylhet).
- Keep a text file of every review ID and receipt you create, so you can withdraw them afterwards.

### 0.4 Devices and widths

Desktop Chrome (1280 px or wider), a narrow window (below 960 px), and a phone or 360 px emulation. Firefox or Safari once for section 5.

---

## 1. Update 1: destination types, search, sort and Google Maps

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| T1.1 | Open Destinations. Set the sort control to "Best rated first". | Destinations with a Community Rating come first (highest first), then those with Guest Feedback (highest average first, then by review count), then unrated ones in name order. A line under the control explains the order. | | | |
| T1.2 | Set the sort back to "By name". | The list is in English-name order, as before. | | | |
| T1.3 | With "Best rated first", type part of a name in the search box. | Only matching destinations show, still in best-rated order. | | | |
| T1.4 | Search for a name that does not exist. | An empty-result message appears, plus a way to clear the search. | | | |
| T1.5 | Clear the search. | All destinations return, still in the chosen order. | | | |
| T1.6 | Reload the page after choosing "Best rated first". | Note whether the choice is kept or reset. Either is acceptable; record what happens. | | | |
| T1.7 | Check that the list never shows one number that merges the Community Rating and Guest Feedback. | The two ratings are always shown separately. | | | |
| T1.8 | Open a destination. Find "Travel guide". | Type buttons appear: "All", then one button per guide type that has entries, each with a count. | | | |
| T1.9 | Press each type button in turn. | Only that type's entries show. The number on the button equals the number of entries shown. | | | |
| T1.10 | Press "All". | Every entry shows; the count on "All" equals the total. | | | |
| T1.11 | Check which button is marked as pressed. | Only one button looks pressed. A screen reader announces it as pressed (`aria-pressed`). | | | |
| T1.12 | Type an English word that appears in one entry. | Only entries containing that word (in the title or text) show. | | | |
| T1.13 | Type a Bangla word that appears in one entry. | The same behaviour as T1.12. | | | |
| T1.14 | Type the word in different letter case (e.g. "BEACH", "beach"). | The same results both times. | | | |
| T1.15 | Choose a type, then search for a word that only appears in another type. | "Nothing in the guide matches" appears with a "Show everything" button. | | | |
| T1.16 | Press "Show everything". | Both the type and the search are cleared; every entry is back. | | | |
| T1.17 | Press "Open in Google Maps" in the destination header. | Google Maps opens in a **new tab** at the destination's point (the URL has `google.com/maps/search/?api=1&query=lat,lng`). | | | |
| T1.18 | Same on a phone. | The Maps app or Maps website opens. | | | |
| T1.19 | Check that the page loads nothing from Google before the button is pressed (DevTools → Network, filter "google"). | No request to Google until the button is pressed. | | | |
| T1.20 | Contacts: open a destination with a contact that has a map point (seed one if none exists). | That contact has the same Google Maps link. | | | |
| T1.21 | Airplane mode: open a destination saved as an offline pack, then use the type buttons and the search. | Both work offline. The Maps link needs a connection; that is expected. | | | |
| T1.22 | Keyboard only: Tab to the type buttons and the search box. | Each can be reached; Enter or Space presses a button; the focus ring is visible. | | | |
| T1.23 | Phone at 360 px. | The search and sort controls stack; the type buttons wrap; nothing scrolls sideways. | | | |
| T1.24 | Dark mode. | Buttons, counts and the pressed state are readable. | | | |
| T1.25 | **Places (P1):** look for a list of restaurants or resorts inside a destination, each with its own rating. | **Not built yet** (needs a decision on rating places; `Decisions.md` 2026-11-12). Mark **B** and move on. | | | |

---

## 2. Update 2: the overall rating is calculated

### 2.1 Write a review (form)

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| T2.1 | Open Write a review. | Seven categories with five stars each: Cleanliness, Accessibility, Hospitality, Food, Transport, Feeling of safety, Value for money. No overall rating to choose. No "Not applicable". | Unit ✔ (parameters) | | |
| T2.2 | Rate nothing. Look under the list. | The line says no overall rating yet, and that it appears when all seven are rated. | | | |
| T2.3 | Rate three categories. | "3 of 7 rated; it appears when all are rated". | | | |
| T2.4 | Fill everything else and press Submit with ratings missing. | Not sent. "Rate each of the seven categories from 1 to 5 stars" shows under the list, and focus moves to the first unrated category. | | | |
| T2.5 | Rate 5,5,5,5,4,4,4. | "5 out of 5 (average 4.6)". | Unit ✔ | | |
| T2.6 | Change one 5 to 4 (5,5,5,4,4,4,4). | "4 out of 5 (average 4.4)". | Unit ✔ | | |
| T2.7 | Rate all 1. | "1 out of 5 (average 1.0)". | Unit ✔ | | |
| T2.8 | Rate 5,1,1,1,1,1,1. | "2 out of 5 (average 1.6)". | Unit ✔ | | |
| T2.9 | Rate 4,4,3,3,3,3,3. | "3 out of 5 (average 3.3)". | Unit ✔ | | |
| T2.10 | Rate all 3 and submit (as a guest). Check it with its receipt. | Accepted. Overall rating 3. | API ✔ (API-10, API-14 for 5) | | |
| T2.11 | Open the same review in the staff Queue. | Overall 3; all seven category ratings are listed. | API ✔ (API-32) | | |
| T2.12 | After it is published, look at the destination's Guest Feedback (or Community Rating for a Verified Member). | The average moves by the calculated overall rating. | | | |
| T2.13 | Press a star, then press the same star again. | Record the behaviour (it stays chosen, or clears). It must never leave the form showing a wrong overall. | | | |
| T2.14 | Keyboard only: reach every star and choose a rating. | Possible with Tab and the arrow keys or Space. | | | |
| T2.15 | Screen reader: change a rating. | The new calculated overall rating is announced. | | | |
| T2.16 | Phone at 360 px. | Stars are at least 44 px tall and easy to press; nothing scrolls sideways. | | | |
| T2.17 | Bangla. | Category names in Bangla (e.g. "পরিচ্ছন্নতা", "খাবার"); the numbers use the Bangla style the app uses elsewhere. | | | |

### 2.2 Edit a review

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| T2.18 | Member: My reviews → a pending review → Edit. Change only the title and save. | Saved. The ratings and the overall rating are unchanged. | API ✔ (API-29) | | |
| T2.19 | Same form: set all seven ratings to 3 and save. | Saved; the overall rating is now 3. | API ✔ (API-30) | | |
| T2.20 | Edit a review written before 11 Nov that has fewer than seven ratings; change one rating and save. | Not saved until all seven are rated; the message says so. | API ✔ (API-27) | | |
| T2.21 | Guest: edit with a receipt; touch one rating only. | The same rule as T2.20. | | | |
| T2.22 | Try to edit a **published** review. | No Edit button (only pending and changes-requested reviews can be edited). | | | |

### 2.3 Server rules (DevTools or Postman; local stack only)

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| T2.23 | `GET /review-parameters`. | Every category has `"required": true`; `rating_rules.overall_rating` starts "Calculated, not entered". | API ✔ (API-01, API-03) | | |
| T2.24 | `POST /reviews/guest` with six categories. | `422 VALIDATION_FAILED`. | API ✔ (API-04) | | |
| T2.25 | With `"category_ratings": {}`. | `422`. | API ✔ (API-05) | | |
| T2.26 | Without `category_ratings`. | `422`. | API ✔ (API-06) | | |
| T2.27 | Seven categories (5,5,5,5,4,4,4) and `"overall_rating": 2`. | `422`; the message names the calculated value 5. | API ✔ (API-07) | | |
| T2.28 | The same with `"overall_rating": 5`. | `201`. | API ✔ (API-11) | | |
| T2.29 | The same without `overall_rating`. | `201`; the stored overall is 5. | API ✔ (API-10, API-14) | | |
| T2.30 | A category rated 0, or 6, or 2.5. | `422`. | API ✔ (API-08), Unit ✔ | | |
| T2.31 | An unknown category key `"WIFI"`. | `422` with a field error under `category_ratings`. | API ✔ (API-09), Unit ✔ | | |
| T2.32 | `PATCH /reviews/{id}/pending` with `overall_rating` only. | `422` ("send all seven category_ratings instead"). | API ✔ (API-26) | | |
| T2.33 | `PATCH` with `"category_ratings": {}`. | `422`. | API ✔ (API-28) | | |
| T2.34 | `PATCH` with seven categories and a wrong `overall_rating`. | `422`. | Unit ✔ | | |
| T2.35 | Check an old review (written before this change) in the public feed. | It keeps its old overall rating; nothing recalculated it. | | | |

### 2.4 Offline drafts

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| T2.36 | Offline: write a review with all seven ratings, save it, go online, send it from Saved drafts. | Sent once, with the calculated overall rating. | | | |
| T2.37 | Open a draft saved **before** this update (fewer categories). | The form asks for the missing ratings; the old stored overall is ignored. | | | |

---

## 3. Update 3: "Exit" for a guest

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| T3.1 | Open `/guest`, enter a name, continue. Look at the sidebar card. | "Welcome, <name> · Guest <tag>" with the buttons "Sign in" and "Exit". No "Sign out". | | | |
| T3.2 | Open `/guest` again as that guest. | Links under the welcome: "Not <name>? Change name", "Exit", "Start as a new guest". | | | |
| T3.3 | Press "Exit" in the sidebar. | The landing page opens. The sidebar card shows "Guest <tag>" with the **same tag** as before, and only "Sign in". | | | |
| T3.4 | Repeat T3.3 from the `/guest` page. | The same result. | | | |
| T3.5 | After Exit, open Saved drafts. | Drafts saved before Exit are still there. | | | |
| T3.6 | After Exit, write a review again. | The guest tag on the new review equals the old tag (the guest scope did not change). | | | |
| T3.7 | Press "Start as a new guest". | A **new** tag is shown (this is the only way to change it). | | | |
| T3.8 | As a guest who never typed a name. | No "Exit" and no "Sign out"; only "Sign in". | | | |
| T3.9 | Sign in as a member. | The button reads "Sign out" and works as before, including the question about unsent drafts. | | | |
| T3.10 | Bangla, as a named guest. | The button reads "বের হোন". | | | |
| T3.11 | Check DevTools → Network while pressing Exit. | No request is sent to the server (a guest has no server session). | | | |

---

## 4. Update 4: finding your own reviews

### 4.1 Navigation

> **Changed on 12 Nov 2026:** guests now also get "My reviews" (P4a is built), so T4.1 and T4.5 of the 11 Nov handoff are replaced by the rows below.

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| T4.1 | As a guest, open the sidebar "Reviews" group. | "Write a review" and "My reviews". No "Check with receipt". | Build ✔ | | |
| T4.2 | Sign in as a member; open the "Reviews" group. | "Write a review" and "My reviews". | | | |
| T4.3 | Press "My reviews". | `/account/reviews` opens; the group stays open and "My reviews" is highlighted. | | | |
| T4.4 | Member: open Write a review and look under the form. | "Already reviewed? Find it in My reviews"; it opens My reviews. | | | |
| T4.5 | Guest: the same place. | The same link, "Already reviewed? Find it in My reviews". | | | |
| T4.6 | Type `/reviews/receipt` in the address bar (guest and member). | The receipt page still opens (it is still needed to edit, withdraw or appeal a guest review, and for older receipts). | | | |
| T4.7 | Sign out. | The group still shows "My reviews" (now the guest list). | | | |

### 4.2 Member "My reviews"

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| T4.8 | Member with no reviews opens My reviews. | "You have not written a review yet" and a link to browse destinations. | | | |
| T4.9 | Write three reviews (different months), then open My reviews. | Newest first; each shows destination, visit month, status chip, title, stars, created time. | | | |
| T4.10 | Status filter "Pending", then "Published", "Rejected", "Hidden", "Withdrawn". | Only reviews with that status each time. | API ✔ (API-41 for Hidden) | | |
| T4.11 | Destination filter. | Only that destination's reviews. | Unit ✔ | | |
| T4.12 | Type a word from a review **title** and press Search. | Only reviews with that word. | API ✔ (API-22) | | |
| T4.13 | Type a word from a review **text** (not the title). | That review is found. | Unit ✔ | | |
| T4.14 | Type the word in upper case. | The same result (case does not matter). | API ✔ (API-22) | | |
| T4.15 | Search for a Bangla word. | Matching Bangla reviews are found. | Unit ✔ | | |
| T4.16 | Search with spaces around the word. | The spaces are ignored. | Unit ✔ | | |
| T4.17 | Search for a word that matches nothing. | "No reviews match these filters" with "Clear filters". | API ✔ (API-23) | | |
| T4.18 | Search for `%` and then `_`. | Nothing matches (these are not wildcards). | Unit ✔ | | |
| T4.19 | Press Enter in the search box instead of the button. | It searches the same way. | | | |
| T4.20 | Try to type more than 100 characters. | The box stops at 100. (The API refuses 101: `422`.) | API ✔ (API-24) | | |
| T4.21 | Combine search with a status filter. | Only reviews that match both. | Unit ✔ | | |
| T4.22 | Search, then reload the page. | The search and filters stay (they are in the address, e.g. `?q=sunrise&status=PENDING`). | | | |
| T4.23 | Press "Clear filters". | The search box empties and every review returns. | | | |
| T4.24 | With more than 20 matching reviews, press "Show more reviews". | The next page loads with no repeats; then "That is all your reviews." | Unit ✔ (paging) | | |
| T4.25 | Member's search never shows another member's review (search for a word only in Member B's review). | Not listed. | Unit ✔ | | |
| T4.26 | Bottom of My reviews (member). | "Wrote a review as a guest, before you had an account? Check it with its receipt"; the link opens the receipt page. | | | |

### 4.3 "Reported" filter

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| T4.27 | Member A has a published review. Member B reports it. Member A ticks "Reported (a moderator decided)". | **Not listed yet:** an open report is not shown to the author. | API ✔ (API-35) | | |
| T4.28 | A moderator decides the report (hide or dismiss). Member A reloads with the box ticked. | The review is listed, with a "Was reported" badge. | API ✔ (API-38, API-39) | | |
| T4.29 | Look at the item and at DevTools → Network for that list. | Nowhere is the reporter's name, the reason (e.g. "spam") or the report text. | API ✔ (API-40) | | |
| T4.30 | Untick the box. | Every review is back; only the reported one has the badge. | | | |
| T4.31 | A report the moderator **dismissed** (no violation). | The review still shows "Was reported" (the decision exists). Record whether the team finds that acceptable. | Unit ✔ | | |
| T4.32 | Member B's own My reviews. | Member B sees nothing about Member A's review. | Unit ✔ | | |

### 4.4 Guest "My reviews" (new, P4a)

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| T4.33 | As a guest, write two reviews, then open My reviews. | Both are listed with their status, without typing a review ID or receipt. | API ✔ (API-13) | | |
| T4.34 | Each guest item. | A "Manage with receipt" button; no View, Edit, Withdraw or Appeal buttons. | | | |
| T4.35 | Bottom of the guest list. | "This list shows reviews written from this browser. Editing, withdrawing or appealing needs the receipt." | | | |
| T4.36 | Guest search and status filter. | They work as for a member. | API ✔ (API-17) | | |
| T4.37 | Open the same site in **another browser** (or a private window) as a guest. | The list is empty: it only shows this browser's reviews. | API ✔ (API-16) | | |
| T4.38 | Press "Start as a new guest", then open My reviews. | The old reviews are **not** shown (a new guest scope). Record this as expected. | | | |
| T4.39 | DevTools → Network: open My reviews as a guest. | `POST /api/v1/reviews/guest/mine`; the secret is in the **request body**, never in the URL; the response has `Cache-Control: no-store`. | API ✔ (API-15, API-19) | | |
| T4.40 | Exit (update 3), then open My reviews. | The reviews are still listed (Exit keeps the guest scope). | | | |
| T4.41 | Guest, Bangla. | Labels in Bangla; the "Manage with receipt" button reads "রিসিপ্ট দিয়ে পরিচালনা করুন". | | | |

### 4.5 No 20-character minimum

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| T4.42 | Write a review whose note is "Ok" (2 characters). | Accepted. | API ✔ (API-10, API-20) | | |
| T4.43 | A note of one character, e.g. "A". | Accepted. | Unit ✔ | | |
| T4.44 | An empty note, or only spaces. | Refused: a note is still required. | API ✔ (API-12) | | |
| T4.45 | The hint under the note box. | No "(at least 20)". | | | |
| T4.46 | Edit a pending review and shorten the note to "Ok". | Saved. | | | |
| T4.47 | Offline, with no cached parameters: write a review with a 2-character note. | The form accepts it (the offline fallback is now 1). | Build ✔ | | |
| T4.48 | `/guest` welcome text. | It does not ask for "at least 20 characters". | | | |
| T4.49 | Appeal statement with too few characters: (a) member, Appeals page; (b) guest, Check with receipt → Appeal. | (a) Member: the Appeal button stays disabled below **10** characters ("1 more character needed"). (b) Guest by receipt: refused below **20** characters (API.md 5.6). The note change did not touch either. | Browser ✔ (a) | | |
| T4.50 | A note of 6000 characters, then 6001. | 6000 accepted; 6001 refused. | | | |

---

## 5. Update 5: hamburger side menu in the moderation dashboard

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| T5.1 | Sign in as a superadmin on a laptop (960 px or wider). | A side menu on the left with ten sections; Queue is highlighted; the top bar reads "Moderation dashboard · Queue". No row of section buttons in the top bar. | Bundle ✔ (API-42) | | |
| T5.2 | Sign in as a moderator. | Eight sections: no "Staff" and no "Notifications". | | | |
| T5.3 | Choose each section in turn. | The screen changes, the section is highlighted, the top bar shows its name, and on a wide screen the menu stays open. | | | |
| T5.4 | Press the hamburger button. | The menu hides and the page uses the full width. Press again: it returns. | | | |
| T5.5 | Hover the hamburger button; use a screen reader. | It is announced as "Open menu" or "Close menu" and says whether it is expanded. | | | |
| T5.6 | Claim a task, open and close the menu, then decide the task. | The claim, the countdown and the decision are not affected. | | | |
| T5.7 | Narrow window (below 960 px) or a phone. | The menu is closed at first. The button opens it **over** the page with a dark backdrop. | | | |
| T5.8 | Narrow: choose a section. | The menu closes and the chosen section shows. | | | |
| T5.9 | Narrow: open the menu, press outside it (on the backdrop). | It closes. | | | |
| T5.10 | Narrow: open the menu, press Escape. | It closes; focus returns to the hamburger button. | | | |
| T5.11 | Narrow, keyboard only: open the menu and press Tab repeatedly. | Focus starts on the current section and stays inside the menu; the page behind cannot be reached. | | | |
| T5.12 | Resize from wide to narrow and back with the menu open. | No broken layout; the menu follows the rule for the new width. | | | |
| T5.13 | Bangla. | Bangla section names (e.g. "কাজের সারি" for Queue); the button label is Bangla for a screen reader ("মেনু খুলুন" / "মেনু বন্ধ করুন"). | | | |
| T5.14 | Both widths. | Nothing scrolls sideways. | | | |
| T5.15 | Firefox and Safari (or Edge). | The same behaviour (the menu uses the `inert` attribute). | | | |
| T5.16 | Reload while on a section other than Queue. | Record which section opens (Queue or the last one). | | | |
| T5.17 | `/staff` on the **deployed** API after the deploy. | The hamburger and the side menu are there (the bundle was rebuilt on 12 Nov). | Local ✔ | | |

---

## 6. Moderation dashboard: every section

Sign in on the staff app. Do 6.1 and 6.2 as superadmin and again as moderator.

### 6.1 Sign-in and access

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| S1 | Open the staff app signed out. | "Abhijatri staff dashboard" sign-in screen with Email and Password. | | | |
| S2 | Wrong password. | A clear refusal; no hint whether the email exists. | | | |
| S3 | Right password, no authenticator yet (first sign-in). | "Set up an authenticator app" with a QR code and a typed secret key. | | | |
| S4 | Enter a wrong 6-digit code. | Refused. | | | |
| S5 | Enter the right code. | The dashboard opens. | | | |
| S6 | Sign out, sign in again. | Password, then "Authenticator code"; no QR code this time. | | | |
| S7 | A plain member (no staff role) signs in on the staff app. | Refused; no dashboard. | | | |
| S8 | Moderator opens a superadmin-only screen by API (e.g. `GET /admin/staff`). | `403`. | | | |
| S9 | Leave the dashboard idle past the session timeout. | Asked to sign in again; nothing is lost silently. | | | |
| S10 | Language switch in the top bar. | Every label changes between Bangla and English. | | | |

### 6.2 Queue (কাজের সারি)

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| Q1 | Submit a new guest review, then open Queue. | The review appears with its title, text, overall rating, seven category ratings, "Guest" and the guest tag. | API ✔ (API-31, API-32) | | |
| Q2 | Type filter buttons (All, reviews, reports, appeals, media, ...). | Only that kind is listed. | | | |
| Q3 | Press "Claim this task". | You hold it; a lease countdown starts. | | | |
| Q4 | Second staff account tries to claim the same task. | "Another person holds it" / "Held by someone". | | | |
| Q5 | Let the lease run down to the end. | "ending soon" shows near the end; at expiry the task goes back to the shared queue. | | | |
| Q6 | Decide **Publish** with a reason. | The review is public on the destination page; the task leaves the queue. | API ✔ (API-33) | | |
| Q7 | Decide **Reject** with a reason. | The author sees Rejected, the reason and an appeal deadline. | | | |
| Q8 | Decide **Request changes**. | The author sees Changes requested and can edit. | | | |
| Q9 | Report task: "Hide pending decision", then decide. | The review leaves the public feed. | API ✔ (API-36, API-37) | | |
| Q10 | Report task: tick "Keep its rating in the totals while hidden". | Decided screen later says "Its rating still counts while it is hidden." | | | |
| Q11 | "Emergency takedown" / "Hide now" on a report (superadmin). | Hidden at once; audited. | | | |
| Q12 | "Escalate" a task as moderator. | It shows "Escalated" and only a superadmin can act on it. | | | |
| Q13 | Superadmin "Assign to" a moderator. | The task moves to that person. | | | |
| Q14 | Anonymous report vs. member report. | Labelled "Anonymous report" / "Member report"; the "Contact (staff only)" field shows only to staff. | | | |
| Q15 | Appeal task. | Shows the appeal statement and the original decision; "Overturn" and uphold work. | | | |
| Q16 | Decide twice quickly (double click). | Only one decision is recorded. | | | |
| Q17 | Open the hamburger menu while holding a task (narrow screen), then close it. | The claim and countdown are unchanged (= T5.6). | | | |
| Q18 | Empty queue. | A friendly empty message, no error. | | | |

### 6.3 Inbox (ইনবক্স)

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| I1 | Open Inbox after some events (new report, escalation). | Notifications are listed, newest first, unread ones marked "new". | | | |
| I2 | "Mark read" on one. | Its "new" mark goes. | | | |
| I3 | "Mark all read". | Every item is read. | | | |
| I4 | "Refresh". | New items appear without a full page reload. | | | |
| I5 | "Load more" with many items. | Older items load with no repeats. | | | |
| I6 | No notifications. | "No notifications." | | | |

### 6.4 Media (ছবি ও ভিডিও)

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| M1 | A member uploads a photo with a review. Open Media → Pending. | The item shows with "Show photo". | | | |
| M2 | "Approve". | "Approved: it now shows on the review." The photo appears on the public review. | | | |
| M3 | "Reject" another. | "Rejected: it is no longer shown." | | | |
| M4 | Video item. | "Show video" plays it. | | | |
| M5 | Tabs Pending / Approved / Rejected. | Each lists the right items. | | | |
| M6 | Nothing pending. | "Nothing here." | | | |

### 6.5 Rejected & hidden (বাতিল ও লুকানো)

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| D1 | Open after rejecting one review and hiding another. | Both listed, with "Rejected" / "Hidden", Guest or Member, and the reason. | | | |
| D2 | A hidden review whose rating was kept. | "Its rating still counts while it is hidden." | | | |
| D3 | "Reopen", then "Confirm reopen". | "The review is back in the queue." It appears in Queue. | | | |
| D4 | "Reopen" then "Cancel". | Nothing changes. | | | |
| D5 | A decision older than the reopen window. | "The reopen window has closed." | | | |
| D6 | A review whose text was removed. | "[text removed]" and "it can no longer be reopened". | | | |
| D7 | "More" with many items. | The next page loads. | | | |

### 6.6 Enforcement (এনফোর্সমেন্ট)

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| E1 | Search an account by part of an email (3+ characters). | Matches are listed. | | | |
| E2 | Open a "Posting restriction" for some days with a reason code. | "Case opened."; the member cannot post a review (they get a clear message) but can still read. | | | |
| E3 | "Lift" the restriction. | "Restriction lifted."; the member can post again. | | | |
| E4 | Remove a published review by its ID; choose "counts in ratings" or "not counted". | The review leaves the public feed; the rating follows the choice. | | | |
| E5 | "Restore" it. | It is public again. | | | |
| E6 | "Emergency" on a case (superadmin). | Marked emergency; listed in Monitoring's "Overdue emergency takedowns" when overdue. | | | |
| E7 | Cases list. | Shows open and closed cases; "No cases." when empty. | | | |

### 6.7 Tour Operations (ট্যুর অপারেশনস)

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| TO1 | Search a tour by ID, code, title or organiser. | Found. | | | |
| TO2 | Filters "All states", "All flags". | The list narrows correctly. | | | |
| TO3 | Open a tour: Members, Dates, Key changes, Reports. | Each shows; "No reports." when empty. | | | |
| TO4 | "Remove member" with an internal note. | "Member removed."; the member is told. | | | |
| TO5 | "Suspend the tour (note required)" with no note. | Refused until a note is written. | | | |
| TO6 | Suspend with a note. | Members see a banner; chat is read-only. | | | |
| TO7 | "Restore". | Chat works again. | | | |
| TO8 | "Cancel this tour (members are told)". | Cancelled; members are notified. | | | |
| TO9 | "Break-glass" chat view with a justification under 10 characters. | Refused. With 10+ characters: allowed and audited. | | | |
| TO10 | Report decision on a chat message: "Hide the message". | Members see "[removed]"; "This message is already hidden." if repeated. | | | |
| TO11 | "Dismiss (no violation)". | The report closes; nothing else changes. | | | |

### 6.8 Audit (অডিট)

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| A1 | Open Audit after the actions above. | Each action is listed with Time, Actor, Actor role, Action, Target type, Target id, Reason, Request id. | | | |
| A2 | Filter by action and by date (From, To). | Only matching events. | | | |
| A3 | "Clear". | Filters reset. | | | |
| A4 | Pick an event. | Its details show. | | | |
| A5 | "Export CSV". | A CSV downloads; no cell starts with `=`, `+`, `-` or `@` (formula-safe). | | | |
| A6 | "Older". | The next page of events. | | | |
| A7 | Search the export and the screen for secrets (passwords, receipts, scope secrets, full ID numbers). | None appear. | | | |

### 6.9 Monitoring (পর্যবেক্ষণ)

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| MO1 | Open Monitoring. | Tiles: Open tasks, Oldest open task, Open reports, Open appeals, Escalated, Expired claims, Active restrictions, Denied attempts 24 h, Open verification requests, Outbox pending, Oldest pending event, Failed outbox events, Failed or unclear emails, Overdue emergency takedowns; an "Updated" time. | | | |
| MO2 | Create a report, then refresh Monitoring. | "Open reports" goes up by one. | | | |
| MO3 | Decide it. | The count goes back down. | | | |
| MO4 | Numbers are never negative and the page has no error. | | | | |

### 6.10 Staff (স্টাফ), superadmin only

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| ST1 | "Active staff" list. | Name, Email, Role of every staff member. | | | |
| ST2 | Search by email with fewer than 3 characters. | Asked for 3+ characters. | | | |
| ST3 | Grant `moderator` to a member who is **not** a Verified Member. | Refused: verification required. | | | |
| ST4 | Grant `moderator` to a Verified Member with a reason of fewer than 3 characters. | "Write a reason (at least 3 characters)." | | | |
| ST5 | Grant with a reason; re-enter your password when asked. | "Role updated."; audit row `staff.role_granted`. | | | |
| ST6 | The new moderator signs in. | Must set up TOTP; then sees eight sections. | | | |
| ST7 | "Revoke" the role. | The person loses access on their next request. | | | |
| ST8 | Try to remove the last superadmin. | Refused (`LAST_SUPERADMIN`). | | | |

### 6.11 Notifications (বিজ্ঞপ্তি ব্যবস্থা), superadmin only

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| N1 | Open the section. | Event types, channels (Email, digest), templates, deliveries and suppressions are shown. | | | |
| N2 | Disable an event, then Enable it. | The state changes and is audited. | | | |
| N3 | Add a new template version using only the listed variables, then "Activate". | "Activated." | | | |
| N4 | A template with an unknown variable. | Refused. | | | |
| N5 | Deliveries list. | Shows recent sends with status and error, no full email body with personal data. | | | |
| N6 | Suppressions: "No active suppressions." when none; add one by email address. | Listed; that address gets no email. | | | |

---

## 7. User (member) dashboard: every section

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| U1 | Landing page `/` signed out. | Hero, links to Destinations and to start as a guest or sign in. | | | |
| U2 | Register with a weak password ("short1"). | Refused with a password rule message. | | | |
| U3 | Register properly. | "Check your email". The email arrives (Mailpit locally). | | | |
| U4 | Sign in before confirming. | Refused: email not verified. | | | |
| U5 | Confirm through the link, sign in. | Signed in; sidebar card shows the name and "Sign out". | | | |
| U6 | Forgot password → reset link → new password. | Can sign in with the new password only. | | | |
| U7 | Overview (`/overview`). | Loads without errors; the cards link to their sections. | | | |
| U8 | Destinations (`/destinations`). | Five destinations with ratings; see section 1. | | | |
| U9 | A destination page. | Header, map link, travel guide, advisories, contacts, Guest Feedback and Community Rating (separate), reviews feed. | | | |
| U10 | Reviews feed on a destination: "Show more". | More reviews load, no repeats. | | | |
| U11 | Report a public review (as Member B). | Reason list; sent; a second open report on the same review is refused. | API ✔ (API-34) | | |
| U12 | Cost planner (`/planner`). | Marked "Soon" in the sidebar; the page says it is not available yet. | | | |
| U13 | Offline packs (`/offline-packs`). | "Save for offline use (… KB)" on a destination; the pack is listed here with its date. | | | |
| U14 | Saved trips (`/trips`). | Marked "Soon"; a placeholder page. | | | |
| U15 | Tours & TourMates (`/tours`) as a non-verified member. | Only the landing information; no Tours actions. | | | |
| U16 | Tours as a Verified Member: Find, New, Requests, Invitations, Preferences. | Each page opens; creating a draft and publishing works. | | | |
| U17 | Reviews → Write a review. | Section 2. | | | |
| U18 | Reviews → My reviews. | Section 4. | | | |
| U19 | My reviews → View a review (`/account/reviews/:id`). | Full text, seven ratings, status history, photos. | | | |
| U20 | My reviews → Withdraw → "Yes, withdraw". | "Review withdrawn."; status Withdrawn; it leaves the public feed. | | | |
| U21 | Withdraw → "Cancel". | Nothing changes. | | | |
| U22 | Appeals (`/account/appeals`) for a rejected review. | An appeal can be written (20+ characters); its state is shown. | | | |
| U23 | My reports (`/account/reports`). | Reports you made, with their state; never the author's private data. | | | |
| U24 | Notifications (`/account/notifications`). | Events about your reviews and reports; mark read works. | | | |
| U25 | Verification (`/account/verification`). | Application form; after submit, a review-status screen that refreshes itself. | | | |
| U26 | Account page (`/account`). | Name and email; sign-out. | | | |
| U27 | Check with receipt (`/reviews/receipt`) with a valid review ID and receipt. | Status, and Edit / Withdraw / Appeal where allowed. | | | |
| U28 | Check with receipt with a wrong receipt, five times. | Refused each time; then slowed down (rate limit) with a clear message. | | | |
| U29 | Privacy page (`/privacy`). | Opens and is readable in both languages. | | | |
| U30 | An unknown address (`/no-such-page`). | A "not found" page with a way home. | | | |
| U31 | Sign out with an unsent draft. | Asked what to do with the draft before signing out. | | | |
| U32 | Health page (`/health`). | Shows API status. | | | |

---

## 8. Cross-cutting checks (run once per release)

| ID | Steps | Expected | Auto (12 Nov) | Result | Notes |
|---|---|---|---|---|---|
| X1 | Switch language on every page above. | No English left on a Bangla page except names; no broken layout. | | | |
| X2 | Dark mode on every page above. | Readable contrast everywhere. | | | |
| X3 | 360 px width on every page above. | No sideways scrolling; buttons at least 44 px. | | | |
| X4 | Keyboard only through each form. | Every control reachable; visible focus; logical order. | | | |
| X5 | Screen reader (NVDA or TalkBack) on Write a review and My reviews. | Labels and status changes are read out. | | | |
| X6 | DevTools console on each page. | No red errors. | | | |
| X7 | Network: any request that carries a receipt or guest scope secret. | Always in the body, never in the URL. | API ✔ (API-19) | | |
| X8 | Airplane mode on a page opened before. | The offline shell shows; no blank page (known issue F4 on a very first visit). | | | |

---

## 9. Known limits (not bugs)

- **Places inside a destination (P1)** are not built: no restaurant or resort list with its own ratings (T1.25).
- **Guest "My reviews"** works only on the browser that wrote the review; on a new device the guest still needs the receipt or an account.
- **"Reported"** shows only after a moderator decided the report, by design.
- **Older reviews** keep the overall rating their author typed.
- F3 and F4 in `Handoff-Backend.md` are still open.

## 10. Bug report template

```
ID: QA-P1-###          Found by: Irfan     Date:
Case ID: (e.g. T4.28)  Build / commit:     Where: local | deployed
Account role:          Language: EN | BN   Device and width:
Steps:
1.
2.
Expected:
Actual:
Screenshot / request_id (from the error box or DevTools):
Severity: Blocker | High | Medium | Low
```

## 11. Development run, 12 November 2026 (evidence for the "Auto" column)

**Backend suite:** 940 tests passed, 0 failed (PostgreSQL integration included), before the guest list route was added. New tests added after that run: keyword search, the reported filter, the server-side overall rating and the guest list; all pass, and the contract and docs tests pass. `ruff` and `mypy` are clean. The `openapi-v1.json` file was regenerated.
**Member app:** type check clean; 241 unit tests pass. **Staff bundle:** rebuilt into `backend/app/staff_site`.

**End-to-end over HTTP on the local stack** (API `:8100`, local Supabase Auth and Mailpit, fresh QA accounts with real TOTP): **42 of 42 passed.**

| Check | Result | Check | Result |
|---|---|---|---|
| API-01 every category required | Pass | API-22 member search ignores case | Pass |
| API-02 note minimum 1 | Pass | API-23 search with no match is empty | Pass |
| API-03 rating rule text | Pass | API-24 101-character search refused | Pass |
| API-04 six categories refused | Pass | API-25 item has `reported: false` | Pass |
| API-05 empty categories refused | Pass | API-26 edit: overall alone refused | Pass |
| API-06 missing categories refused | Pass | API-27 edit: partial categories refused | Pass |
| API-07 wrong overall refused | Pass | API-28 edit: empty categories refused | Pass |
| API-08 rating 0 refused | Pass | API-29 edit title only: overall kept | Pass |
| API-09 unknown category refused | Pass | API-30 edit all 3: overall becomes 3 | Pass |
| API-10 2-character note, no overall: accepted | Pass | API-31 review reaches the staff queue | Pass |
| API-11 correct overall accepted | Pass | API-32 queue shows overall 3 | Pass |
| API-12 empty note refused | Pass | API-33 moderator publishes | Pass |
| API-13 guest list shows this browser's reviews | Pass | API-34 second member reports | Pass |
| API-14 stored overall is the calculated 5 | Pass | API-35 open report hidden from the author | Pass |
| API-15 guest list is `no-store` | Pass | API-36 hide under the report lease | Pass |
| API-16 another secret sees nothing | Pass | API-37 report resolved | Pass |
| API-17 guest search | Pass | API-38 `reported=true` lists it | Pass |
| API-18 short secret refused | Pass | API-39 badge data and status Hidden | Pass |
| API-19 guest list not reachable by GET | Pass | API-40 no reporter or reason exposed | Pass |
| API-20 member review with 2-character note | Pass | API-41 status Hidden filter | Pass |
| API-21 member overall 5 from mean 4.57 | Pass | API-42 `/staff` bundle has the side menu | Pass |

**Browser (Claude in Chrome):** run on 12 Nov 2026; see section 12.

## 12. Browser run with Claude in Chrome, 12 November 2026

**Setup:** local stack. Member app `http://localhost:5180` (guest "QA Irfan", then member "Nila QA"). Staff app `http://127.0.0.1:5185` (superadmin "Shahana QA", then moderator "Mahin QA", both with real TOTP). The staff app is on a different host on purpose; see finding B3. Desktop window 1487 px wide; the staff narrow tests ran at 767 px.

### 12.1 Results

| Case | Result | What was seen |
|---|---|---|
| T1.1 | Pass | With Bandarban (4.0, 3 reviews) and Sajek (3.0, 1 review) rated: Bandarban, Sajek, then Cox's Bazar, Sundarbans, Sylhet. The explanation line shows. |
| T1.3 | Pass | "sy" with "Best rated first": only Sylhet. |
| T1.4 | Pass | `No destination matches "syzzz"` with "Clear search". |
| T1.5 | Pass | "Clear search" brings back all five; the sort stays "Best rated first". |
| T1.6 | Recorded | After a reload the sort is back to "By name". |
| T1.7 | Pass | "Seeded Destination Selection" and "Guest Feedback" are separate on every card; no merged number. |
| T1.9, T1.10, T1.11 | Pass | Bandarban: All 4, Attractions 3, Getting there 1; the counts match the entries; one button pressed at a time. |
| T1.12, T1.14 | Pass | "BOGA" finds "Boga Lake and Keokradong". |
| T1.13 | Pass | "বগা" (Bangla page) finds "বগা লেক ও কেওক্রাডং". |
| T1.15, T1.16 | Pass | Getting there + "BOGA": "Nothing in the guide matches"; "Show everything" clears both (All 4, empty box). |
| T1.17 | Pass | A new tab opens at `google.com/maps/search/?api=1&query=22.1953,92.2184`. |
| T1.19 | Pass | Nothing loads from Google Maps before the press (only the Google Fonts stylesheet, which is expected). |
| T2.1, T2.2 | Pass | Seven categories, no overall input; "0 of 7 rated; it appears when all are rated." |
| T2.3 | Pass | "3 of 7 rated; it appears when all are rated." |
| T2.4 | Pass | Not sent; "Rate each of the seven categories from 1 to 5 stars."; focus on "Food: 1 star" (first unrated). |
| T2.5 | Pass | 5,5,5,5,4,4,4 → "5 out of 5 (average 4.6)". |
| T2.6 | Pass | 4,5,5,5,4,4,4 → "4 out of 5 (average 4.4)". |
| T2.8 | Pass | 5,1,1,1,1,1,1 → "2 out of 5 (average 1.6)". |
| T2.9 | Pass | 4,4,3,3,3,3,3 → "3 out of 5 (average 3.3)". |
| T2.10 | Pass | All 3 → "3 out of 5 (average 3.0)"; submitted; the guest list shows ★★★. |
| T2.11 | Pass after fix | The queue showed only ★★★ and no category ratings (finding B1). After the fix all seven are listed, e.g. "Cleanliness: ★★ 2". |
| T2.12 | Pass | After publishing, Sajek has Guest Feedback 3.0 (1) and moved up under "Best rated first". |
| T2.13 | Pass | Pressing a chosen star again keeps it chosen; the overall stays right. |
| T2.18 | Pass | Edit, title only → "Saved as version 2"; the seven ratings and ★★★★ unchanged. |
| T2.19 | Pass | Edit, all seven to 2 → "2 out of 5 (average 2.0)" → "Saved as version 3", ★★ and each category 2/5. |
| T3.1 | Pass | Card: "Welcome, QA Irfan · Guest Z6YV3-1TBMX", "Sign in", "Exit". No "Sign out". |
| T3.2, T3.10 | Pass (Bangla) | `/guest`: "QA Irfan নন? নাম পরিবর্তন করুন", "বের হোন", "নতুন অতিথি হিসেবে শুরু করুন". |
| T3.3, T3.8 | Pass | Exit opens `/`; the card shows "Guest Z6YV3-1TBMX" (same tag) and only "Sign in". |
| T3.9 | Pass | Member Nila: "Sign out". |
| T4.1 | Pass | Guest "Reviews" group: "Write a review", "My reviews". |
| T4.2, T4.3 | Pass | Member: "My reviews" opens `/account/reviews` and is highlighted. |
| T4.4, T4.5 | Pass | Both read "Already reviewed? Find it in My reviews". |
| T4.10 | Pass | Status Published: none; Hidden: the hidden review; Rejected: the rejected review. |
| T4.11 | Pass | Destination Bandarban: none (correct). |
| T4.12, T4.14 | Pass | "LANTERN" finds "Member lantern beach walk". |
| T4.17 | Pass | "volcano": "No reviews match these filters" with "Clear filters". |
| T4.19 | Pass | Enter in the box searches. |
| T4.22 | Pass | `?q=LANTERN` in the address fills the box and filters. |
| T4.23 | Pass after fix | The lower "Clear filters" emptied the list but left "volcano" in the box (finding B2). Fixed; re-tested. |
| T4.26 | Pass | Member footer line with "Check it with its receipt". |
| T4.27, T4.28, T4.30 | Pass | The ticked box shows only the decided, reported review with a "Was reported" badge next to "Hidden"; unticking brings all back. |
| T4.33 to T4.35 | Pass | Guest list without ID or receipt; "Manage with receipt" only; the browser-only notice at the bottom. |
| T4.36 | Pass | Guest search "SUNRISE" finds it; "volcano" finds nothing. |
| T4.39 | Pass | `POST /api/v1/reviews/guest/mine`, 200; nothing secret in the URL. |
| T4.40 | Pass | After Exit the guest list still shows the review. |
| T4.42 | Pass | Guest note "Ok" accepted. |
| T4.43 | Pass | Member note "A" accepted. |
| T4.45, T4.48 | Pass | "0 / 6000 (at least 1)"; `/guest` says "কমপক্ষে ১ অক্ষরে". |
| T4.49 (a) | Pass | Member appeal: disabled at 9 characters ("1 more character needed"); sent at 10+. |
| T5.1 | Pass | Superadmin: ten sections, Queue highlighted, "Moderation dashboard · Queue". |
| T5.2 | Pass | Moderator: eight sections (no Staff, no Notifications). |
| T5.3 | Pass | All ten sections: the title follows, the item is highlighted, the menu stays open, no error on any screen. |
| T5.4 | Pass | The hamburger hides the menu (full width) and shows it again. |
| T5.6 | Pass | Holding a task: menu hidden and shown; the lease kept counting (4:44 → 4:37); "Done: PUBLISHED". |
| T5.7 | Pass | At 767 px the menu starts closed. |
| T5.8 | Pass | Narrow: choosing Audit closes the menu and shows Audit. |
| T5.9 | Pass | Narrow: pressing the backdrop closes it. |
| T5.10 | Pass | Narrow: Escape closes it; focus returns to the "Open menu" button. |
| T5.11 | Pass | Narrow: focus starts on Queue; 12 × Tab and 3 × Shift+Tab stay inside the menu; the page behind is `inert`. |
| T5.12 | Pass | 767 → 1507 px: the menu sits open beside the page; 1507 → 767 px: it closes. |
| T5.13 | Pass | Bangla: "কাজের সারি" … "বিজ্ঞপ্তি ব্যবস্থা"; button label "মেনু খুলুন" / "মেনু বন্ধ করুন". |
| T5.14 | Pass | No sideways scrolling at 767 or 1507 px. |
| S1, S2 | Pass | Sign-in screen; a wrong password gives "The email, password or code is not correct." |
| S4, S5, S6 | Pass | Wrong code refused; right code opens the dashboard; no QR code once an authenticator is set up. |
| S8 | Pass | Moderator `GET /admin/staff` → 403, logged as `denied.role`. |
| Q1 | Pass after fix | Title, overall, author and note; the seven ratings and the guest tag after fix B1. |
| Q3 | Pass | "You hold this task. A 5-minute lease is running." |
| Q6 | Pass | "Done: PUBLISHED"; the task left the queue; public on Sajek. |
| Q7 | Pass | Moderator rejects ("Off topic"): "Done: REJECTED"; the member sees "Rejected" and "Appeal deadline: 12 Dec 2026". |
| Q15 | Pass | The appeal task tells the deciding moderator "You made the original decision…", and Claim is disabled. |
| D1 | Pass | "REJECTED · Member · off-topic · … 29 days 23 hours left to reopen". |
| A1 | Pass | Each action of the run is logged: `task.claimed`, `review.publish`, `review.reject`, `appeal.received`, `denied.role`. |
| MO1, MO2 | Pass | All tiles show; "Open appeals 1" after the appeal; "Denied attempts, 24 h 1". |
| U1 | Pass | Landing page after signing out. |
| U19 | Pass | Review view: text, seven ratings, version history. |
| U22 | Pass | "Appeal submitted."; the appeal shows "#… · Received". |

**Not run in the browser (do them by hand):** phone width (T1.23, T2.16, X3), because Chrome in this setup would not shrink the page below 767 px. Also not run: screen reader (T1.22, T2.15, X5), dark mode (X2), offline (T1.21, T2.36, T2.37, X8), Firefox and Safari (T5.15), the second-browser guest check (T4.37), "Start as a new guest" (T3.7, T4.38), and the rest of sections 6 and 7 (media, enforcement, tours, staff roles, notifications, registration).

### 12.2 Findings

| ID | Severity | Where | Problem | Status |
|---|---|---|---|---|
| B1 | Medium | Staff Queue, review task | The moderator saw only the overall stars: `GET /admin/queue` did not send the category ratings or the guest tag, so the seven ratings behind the calculated overall were invisible. | **Fixed:** `app/admin/routes.py` sends `category_ratings` and `guest_tag`; `staff/src/screens/Queue.tsx` lists them in Bangla and English; test added in `test_admin.py`; bundle rebuilt. Re-tested in Chrome. |
| B2 | Low | Member My reviews | "Clear filters" in the empty-result box cleared the list but left the old word in the search box. | **Fixed** in `MyReviewsPage.tsx` (the box follows the address). Re-tested in Chrome. |
| B3 | Info (test setup) | Local testing | The staff app and member app on `localhost` share the API cookie, so signing in on one signs in the other. | Not a product bug (production uses different hosts). Test with different hosts, e.g. staff on `127.0.0.1` (section 0.2). |
| B4 | Low | Write a review, signed-in member | The text still says "No account needed… you get a receipt", and a member is shown a receipt to save that they do not need. | Open (copy and UX); for Abdullah. |
| B5 | Info | This document | T4.49 assumed a 20-character appeal minimum; the member appeal page uses 10. | Corrected above. |
