# UI-Architecture.md (F03) review

**Checked:** the uploaded `UI-Architecture.md` (identical to `Docs/UI-Architecture.md` on `main` at `8720cca`) against `Features/Platform-Foundation.md`, `Features/Review.md`, `Features/Execution.md`, `Docs/Security.md`, `Docs/Design.md`, `Docs/Frontend-Implemented.md`, `Docs/Decisions.md`, `Docs/api/API.md`, the Gantt, and the frontend code. **Date:** 21 October 2026. Fixed version: `specs/UI-Architecture.md` (revision 2). Nothing in the repo was changed.

## Verdict

The language model and component map are well grounded and most of the audit is accurate. It is **not ready to approve as written**: the sitemap misses a built route, two spec requirements (prerendering and the font budget) are not handled or are misread, and the audit misses several gaps that are in the same files it scanned, one of which can blank the app.

## Fix before implementing

| # | Issue | Evidence | Fixed in rev 2 |
|---|---|---|---|
| 1 | `/guest` (GuestEntryPage) is missing from the sitemap, flows and component map, so flow F1 is wrong: "Continue as guest" goes to `/guest`, not `/overview`. | `App.tsx`; `LandingPage.tsx` links `/guest`; Decisions.md 20 Oct "Guest entry"; API 5.14 | 2.1, F1, section 3 |
| 2 | No rule for the language of prerendered destination pages. PF 19.2 prerenders them and PF 16.3 forbids inline script, so a stored English preference cannot apply before paint. | PF 16.3, 19.2 | 2.3, decision Q1 |
| 3 | Font budget misread: PF 19.3 is at most 40 KiB **per weight** and **at most 2 weights**; the plan says "one subset". Today two Bangla families × 4 weights load. Self-hosting is pushed to R12, but Google Fonts breaks `style-src 'self'` and is not in the processor register, so it must land before the CSP. | PF 16.3, 19.3, 23.5; `index.html`, `global.css` | 4.3, decision Q2 |
| 4 | Blocked storage blanks the app: `LanguageContext` and `ThemeContext` call `localStorage` with no guard (unlike `api/guests.ts`). | `LanguageContext.tsx:15`, `ThemeContext.tsx:14` | L2, U12 |
| 5 | Bangla and English legal pages (privacy, terms, takedown) are absent from the IA, though they must exist in both languages with equal prominence. | Security.md 3.4, 10.2 | 2.1 planned routes, `LegalPage` |
| 6 | The "one local map per enum" rule conflicts with API 5.15, which says the client renders review labels from `GET /review-parameters` and never hard-codes them. | API 5.15; `GuestReviewForm.tsx` uses local `TRAVELLER_TYPES`, `COMFORT_TIERS` | 3.1, U15 |

## Missed by the audit (section 7)

| # | Gap | Where |
|---|---|---|
| 7 | API pill "API Live / API Offline / Checking" is English-only. | `Navbar.tsx` |
| 8 | Search input is unwired, unlabelled, and its two placeholders promise different things. Sidebar "সিস্টেম স্ট্যাটাস" vs "API Health". | `Navbar.tsx`, `Sidebar.tsx` |
| 9 | Language switch: Bangla `aria-label` overrides the visible "English" (WCAG 2.5.3) and is tagged `lang="en"`; switch 36 px, theme button ~32 px vs the 44 px in Design.md. | `PreferenceToggles.tsx` |
| 10 | `RatingSummary` joins "{n} verified" from fragments (breaks L9, which the plan says it meets) and uses "Editorial seeded selection" instead of Review.md's "Seeded Destination Selection". | `RatingSummary.tsx:45,57` |
| 11 | `tracking-*` and `uppercase` on Bangla headings and taglines, against the plan's own section 5. | Landing, Overview, Destinations, DestinationDetail, Reviews pages |
| 12 | Star `aria-label` uses a Latin digit in Bangla. | `ReviewFeedSection.tsx:109` |
| 13 | First requests can send `Accept-Language: bn` for a stored English choice (the `<html lang>` effect runs after child fetch effects). | `LanguageContext.tsx`, `client.ts:64` |
| 14 | `TurnstileWidget` is listed as Planned but is built; `CategoryAverages` is not listed. | `components/reviews/TurnstileWidget.tsx`, `components/destination/CategoryAverages.tsx` |

## Rule gaps

- L3 overstates "never loses context": a language switch re-renders Turnstile (needs a new token), and a server error already on screen stays in its original language.
- L5 says fallback text is tagged with its own `lang`, but `pick()` returns only a string, so callers cannot know which language was used.
- L6 gives no `lang` for `MIXED` reviews or Banglish in Latin letters.
- L7 is ambiguous for phone numbers: the footer shows ৯৯৯ while contact cards show Latin digits.
- Fixed product terms (Guest Feedback vs Community Rating, Verified Member vs Verified Visit) are not pinned, though Review.md requires they never be confused. Rev 2 adds a short term table.
- Missing planned flows: report a review (API 5.7, R11) and appeal from receipt status (API 5.6).
- The plan changes Design.md's typography (fonts from Google, Inter tracking on `[lang="en"]`, "বাং / EN" toggle) without amending it.

## Citation fixes

- L4 cites "PF 20, 23": PF section 23 is Backup and Restore; the intended reference is requirement **PF-23** (section 28).
- L2 cites PF 18.1 for `localStorage`; 18.1 names **IndexedDB** for the language preference. Keeping `localStorage` is reasonable but should be recorded in Decisions.md (decision Q3).
- "D12" is a defect in `Frontend-Implemented.md`, not a Decisions.md entry.
- "API.md" is `Docs/api/API.md`. The project-files copy `specs/API.md` (18 Oct) is stale: it has no sections 5.12 to 5.15, which this plan cites.
- `Docs/Platform-Foundation.md` is PF's declared location, but the file is at `Features/Platform-Foundation.md` in the repo today.
