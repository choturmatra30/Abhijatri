# Bilingual Information Architecture and UI Component Plan

**Gantt task:** F03, "Create bilingual information architecture and UI component plan".
**Acceptance:** "Bangla-default flows and component map approved". Risk note: "Use system font fallback".
**Status:** Draft for approval, 20 October 2026. Approver: Shahriar Islam (scope owner). Author: Abdullah Bin Sorwar Choudhury (frontend owner).
**Authority:** Below `Features/Review.md`, `Docs/Security.md` and `Docs/Platform-Foundation.md`; it describes how the public PWA applies them. Visual tokens stay in `Docs/Design.md`; implementation status in `Docs/Frontend-Implemented.md`.

---

## 1. Language model

The rules every screen follows. Section 7 lists where the current build does not yet meet them.

| # | Rule | Source |
|---|---|---|
| L1 | **Bangla is the default.** A first visit renders in Bangla whatever the browser language is. English is one tap away on every screen, including public pages. | Execution.md rule 8; Proposal O1 |
| L2 | **The choice persists and is global.** Stored as `abhijatri_lang` in `localStorage` (PF 18.1 allows the language preference on the device), applied to `<html lang>` and sent as `Accept-Language` on every API call so server messages match. | PF 12.3, 18.1 |
| L3 | **Switching never loses context.** The same route, scroll position and form input stay; no refetch, because destination content carries both languages in one payload. | Gantt R03 note "English switch preserves context" |
| L4 | **Interface text is always paired.** Every visible string, `aria-label`, `placeholder`, `title` and `alt` has a Bangla and an English form. No English-only labels. | PF 20, 23 |
| L5 | **Maintained content is shown in the interface language with fallback.** `pick(language, bn, en)` shows the other language only when one is missing, and that text is tagged with its own `lang`. | API.md 5.12, 5.13 |
| L6 | **User content is never translated.** Reviews, names and notes appear exactly as written; their declared language comes from the text, not the interface (D12). They are tagged with their own `lang`, not the page's. | Gantt R09 "Reviews remain in submitted language"; Review.md 3.1 |
| L7 | **Numbers and dates follow the interface language.** Bangla uses `bn-BD` (Bangla digits), English `en-GB`. Dates are shown in Asia/Dhaka. Machine values stay Latin: review IDs, receipts, phone numbers in `tel:` links, coordinates, codes. | PF 11.2 |
| L8 | **Server errors are shown as sent.** The API already localises `message` by `Accept-Language`; the client branches on `code` only and never rewrites the message. Network failures, which have no server message, use a paired local string. | API.md 2 |
| L9 | **No sentence assembly across languages.** Build each full sentence in both languages (`t('… ৩টি রিভিউ', '3 reviews')`) instead of concatenating fragments, because word order and plural forms differ. | Bangla grammar |

## 2. Information architecture

### 2.1 Sitemap

```text
Public shell (PublicLayout: brand, language and theme switches, footer with 999)
├── /                 Landing: Continue as guest | Sign in; quick links to destinations
└── /login            Sign in (disabled until R04)

App shell (AppLayout: sidebar, top bar, session card)
├── /overview                     Overview: counts, destinations with advisories
├── /destinations                 Destination list with bilingual filter
│   └── /destinations/:id         Profile: advisories first, seasonality, guide, restrictions, contacts, reviews
├── /reviews[?destination=:id]    Guest review form, receipt shown once, receipt status and withdrawal
├── /planner                      Prototype (E08)
├── /offline-packs                Prototype (R13)
├── /trips                        Prototype (E09)
└── /health                       System status (diagnostic)

Staff build (separate, admin.<owned-domain>; not in this app; Gate A item)
```

Planned public routes, added when their backend exists: `/register`, `/verify-email`, `/reset-password` (R04, R05); `/account` with "My reviews" and verification request (R05, R07). They join the public or app shell as listed in section 3.

### 2.2 Navigation

| Place | Contents | Bilingual notes |
|---|---|---|
| Sidebar (desktop fixed, mobile drawer) | Overview, Destinations, Cost planner, Offline packs, Saved trips, Reviews, System status; brand links to `/`; session card | Labels in the title font; drawer button needs a paired `aria-label` (section 7) |
| Top bar | Destination search (planned), API status pill, language switch, theme switch | The language button is written in the *target* language ("English" / "বাংলা") and carries that `lang` |
| Public top bar | Brand, language switch, theme switch | Same switch component (`PreferenceToggles`) |

### 2.3 Primary flows

Each flow is complete in either language and survives a language switch at any step.

| Flow | Steps | Bangla-default behaviour |
|---|---|---|
| F1 First visit | `/` → Continue as guest → `/overview` | Renders in Bangla; nothing to accept or sign |
| F2 Shared link | `/destinations/:id` opened directly | No landing gate; Bangla unless the visitor chose English before |
| F3 Plan a visit | Overview or Destinations → profile → advisories → contacts (`tel:`) | Advisories before attractions; dates in Dhaka time; Bangla digits |
| F4 Guest review | Profile → Write a review (destination preselected) → form → receipt shown once → done | Language of the review detected from the text; note sent verbatim; receipt is Latin and copyable |
| F5 Check or withdraw | `/reviews` → receipt panel → status → withdraw (confirm) | Status labels paired; server messages already localised |
| F6 Member sign-in | `/login` (disabled) → Continue as guest | Honest notice in both languages until R04 |
| F7 Verified Member review | As F4 plus photos with alt text | Alt text written by the member in their language, tagged with that `lang` |

## 3. Component map

Each component owns its bilingual behaviour; pages compose them. Status: **Built**, **Partial**, **Planned**.

| Layer | Component | Purpose | Bilingual responsibility | Status |
|---|---|---|---|---|
| Context | `LanguageContext` | Current language, `t(bn, en)`, persistence, `<html lang>` | L1, L2 | Built |
| Context | `ThemeContext` | Light and dark themes | none | Built |
| Context | `SessionContext` | Guest, Member or Verified Member (guest only until R04) | Session labels | Partial |
| Layout | `PublicLayout` | Shell for `/` and `/login` | Footer emergency line paired | Built |
| Layout | `AppLayout`, `Sidebar`, `Navbar` | App shell and navigation | Labels paired; English-only `aria-label` remains (section 7) | Partial |
| Layout | `PreferenceToggles` | Language and theme switches | Target-language label with its own `lang` | Built |
| Common | `LoadingState`, `ErrorState`, `EmptyState`, `describeError` | Shared states | L8; request reference shown in Latin | Built |
| Destination | `RatingSummary` | Community Rating and Guest Feedback with counts | L7 digits; L9 sentences | Built |
| Destination | `AdvisoryCard` | Severity, state, validity, source | Paired severity and state labels; dates per L7 | Built |
| Destination | `ProvenanceNote` | Source, publisher, verification date | Publisher name stays as published | Built |
| Reviews | `GuestReviewForm` | Structured review, client checks, retry-safe identity | Language detection (L6); paired field errors; focus to first error | Built |
| Reviews | `CategoryRatings` | Seven categories with prompts | Paired names and prompts | Built |
| Reviews | `ReviewPhotos` | Locked for guests; picker for Verified Members | Paired limits and notices; member-written alt text | Partial (upload waits for R07) |
| Reviews | `ReceiptPanel`, `ReceiptStatusPanel` | Receipt shown once; status and withdrawal | Receipt and IDs Latin (L7) | Built |
| Reviews | `ReviewFeedSection` | Published reviews with paging | L6: each review needs its own `lang` (section 7) | Partial |
| Pages | Landing, SignIn, Overview, Destinations, DestinationDetail, Reviews | Route screens | Compose the above | Built |
| Pages | HealthCheck | Diagnostics | Mostly English (section 7) | Partial |
| Pages | Planner, OfflinePacks, SavedTrips | Prototypes | English fragments and unlocalised numbers (section 7) | Prototype |
| Planned | `AccountForms` (register, verify email, reset) | R05 | Paired validation; paste allowed in password fields (PF 20) | Planned |
| Planned | `OfflineStatus`, `PackCard` | R12, R13 | Freshness and storage-refusal messages | Planned |
| Planned | `TurnstileWidget` | R09 follow-up | Widget language set from the interface language | Planned |
| Utilities | `utils/format.ts` (`pick`, `formatNumber`, `formatCalendarDate`, `formatTimestamp`, `currentDisplayMonth`) | Locale-aware formatting | L5, L7 | Built |
| Utilities | `components/reviews/reviewLabels.ts`, label maps in `AdvisoryCard`, `DestinationDetailPage` | Paired labels for API enums | One map per enum, never inline per use | Built |

### 3.1 How strings are written

- Inline pairs: `t('বাংলা', 'English')` at the point of use. With two languages this keeps both forms together and reviewable; a separate catalogue adds indirection without benefit.
- Enum labels (statuses, categories, severities, traveller types) live in one map per enum as `[bn, en]` pairs and are spread into `t(...)`.
- Bangla copy is written as Bangla, not translated word for word; English is the second form.
- A string that contains a number is written as a whole sentence in each language (L9) and formats the number with `formatNumber` (L7).

## 4. Typography and fonts

| Role | Bangla stack | English stack |
|---|---|---|
| Titles | Hind Siliguri, then system Bangla fonts, then `sans-serif` | Inter, then `system-ui`, then `sans-serif` |
| Body | Noto Serif Bengali, then system Bangla fonts, then `serif` | Inter, then `system-ui`, then `sans-serif` |

**System font fallback (Gantt F03 risk).** Each stack ends in fonts already on the target devices, so text is readable before or without the web font: `"Noto Sans Bengali"` (Android), `"Nirmala UI"` and `"Vrinda"` (Windows), `"Bangla Sangam MN"` and `"Kohinoor Bangla"` (Apple). Web fonts use `font-display: swap`.

**Font and spacing follow the text's language, not the page's.** The current rule `[lang="en"] { font-family: Inter !important; letter-spacing: -0.06em !important }` matches `<html lang="en">`. Measured in Edge on 21 Oct 2026 (section 7, U1): the font does not reach the text, because `body` sets its own `font-family`, so English-mode body text uses Noto Serif Bengali's Latin letters instead of Inter; but `letter-spacing` is inherited, so every element, Bangla included, is tightened by 0.06em (−0.93 px at 15.5 px). Bangla in English mode is visibly cramped; conjuncts still form. Planned change: apply Inter and any tracking only to English text (`:lang(en)` on content, Bangla content tagged `lang="bn"`), and never tighten Bengali.

**Budget.** PF 19.3 allows one critical Bangla subset of at most 40 KiB. Today three families and four weights load from Google Fonts twice (`index.html` and an `@import` in `global.css`), which also conflicts with the CSP rule `style-src 'self'` (PF 16.3). Planned with R12: self-host one subset Bangla weight, load the rest after first content, remove the `@import`.

## 5. Bilingual layout rules

- Bangla text runs longer and taller (conjuncts, matras). Buttons and pills size to content with `min-h-[44px]`; no fixed widths on text containers; line height at least 1.5 for Bangla body text.
- Never truncate Bangla mid-cluster; use `line-clamp` on whole lines only.
- Uppercase and letter-spacing utilities (`uppercase`, `tracking-*`) apply only to English labels; Bangla has no case.
- Icons sit beside text, never replace it; every icon-only button has a paired `aria-label`.
- Text enlarges to 200 % without loss (PF 20): layouts wrap rather than clip.

## 6. Accessibility in two languages

- `<html lang>` follows the interface language; any element whose text is in the other language carries its own `lang` (switch button, fallback content, user reviews) so screen readers pronounce it correctly.
- Validation messages, live regions (`role="status"`, `role="alert"`) and focus movement are language-independent; the message text is paired.
- TalkBack in Bangla is part of the screen-reader pass required by PF 20.

## 7. Current gaps (audit, 20 October 2026)

Found by scanning every `.tsx` file for unpaired text and attributes, and by measuring computed styles in Edge (21 Oct 2026).

| # | Gap | Where | Rule | Fix and task |
|---|---|---|---|---|
| U1 | English mode tightens every element by `-0.06em` letter-spacing, Bangla included (measured −0.93 px; visibly cramped), while English body text does not actually get Inter | `global.css` `[lang="en"]` on `<html>` | Section 4 | Scope font and tracking by text language; no negative tracking on Bengali (F03 follow-up) |
| U2 | Fonts load twice from Google Fonts; no system fallback stacks | `index.html`, `global.css`, `tailwind.config.js` | Section 4 | System stacks now (F03 follow-up); self-hosted subset with R12 |
| U3 | Published reviews and fallback content carry the page's `lang`, not their own | `ReviewFeedSection`, `pick()` callers | L5, L6 | Tag each review and each fallback (F03 follow-up; the feed does not return `language`, so tag by detected script until the API adds it) |
| U4 | English-only `aria-label="Toggle Navigation"` | `Navbar.tsx` | L4 | Pair it (F03 follow-up) |
| U5 | English-only brand subtitle "Abhijatri Companion" | `Sidebar.tsx` | L4 | Pair or drop (F03 follow-up) |
| U6 | System status page mostly English (labels, presets, endpoint list) and `toLocaleTimeString()` with the browser locale | `HealthCheckPage.tsx` | L4, L7 | Pair labels; endpoint paths stay Latin (F03 follow-up) |
| U7 | Prototype screens: English fragments ("Airplane Mode Ready", "Saved:", "/ person"), `toLocaleString()` and `toFixed()` without locale, "BDT" prefix only | `OfflinePacksPage`, `SavedTripsPage`, `PlannerPage` | L4, L7, L9 | Fix when each screen is rebuilt (R13, E09, E08); not worth polishing prototype data |
| U8 | Coordinates use `toFixed(4)` | `DestinationDetailPage` | L7 | Correct as is: coordinates are machine values and stay Latin |

## 8. Approval

| Role | Name | Decision | Date |
|---|---|---|---|
| Scope owner | Shahriar Islam | Pending | |
| Frontend owner | Abdullah Bin Sorwar Choudhury | Submitted | 20 Oct 2026 |

On approval, F03 is complete. The follow-ups U1 to U6 are implementation items under F03 and Gate A "Bangla and English infrastructure working".
