# Guest identity, visit counting and monitoring dashboard: draft review

**Checked:** the pasted "Production-Grade System Architecture & Documentation" draft and the team chat (7 screenshots) against `Features/Platform-Foundation.md` (PF), `Features/Community.md`, `Features/Review.md`, `Docs/Security.md`, `Docs/Architecture.md`, `Docs/Schema.md`, `Docs/Decisions.md`, `Docs/api/API.md` (current contract) and the frontend code (`src/api/guests.ts`, `src/api/reviews.ts`). **Date:** 21 October 2026. Final design: `Docs/Guest-Identity-and-Visits.md` (G) and `Docs/System-Monitoring-Dashboard.md` (D); section numbers below point into those. Nothing in the repo was committed.

## Verdict

**Not production-ready as written.** The goals are right (stable guest identity, new vs returning, an admin dashboard), but the draft was written for a different stack (Next.js + Supabase Auth), it stores guest profiles and visit logs in Supabase against the team's own count-only rule and the chat's "DB te store kora lagbe na", the A − B formula mixes people and visits, and the "private" dashboard has no working protection because staff authentication does not exist yet.

## What the chat settled (requirements)

| # | Requirement | Source |
|---|---|---|
| C1 | Replace "guest 1, 2 …" (sequential, from UTC time) with a random unique string per guest. | Screenshot 1 |
| C2 | Metrics: Guest, Verified, New Guest, New Verified, Total visits, Old visits = A − B. | Screenshot 1 |
| C3 | Guest identity must survive sign-in / sign-out on the device (today it is lost). | Screenshot 2 |
| C4 | A **System Monitoring Dashboard** on a **private URL** that shows the whole system, not only guest ids. | Screenshots 3, 4, 5 |
| C5 | Upstash Redis for this; guests are not stored in the database. Hosting on Vercel, not a Railway database. | Screenshots 3, 4 |
| C6 | The unique string lives on the device (local storage) and is shown as a frontend badge. | Screenshot 6 |
| C7 | Guest notes on destinations show an "anonymous guest" heading with the unique id. | Screenshots 5, 6, 7 |

## Blocking issues

| # | Issue in the draft | Why it matters | Evidence | Fix in final design |
|---|---|---|---|---|
| 1 | Built on **Next.js middleware** and Vercel functions. | The frontend is a **Vite React SPA** on Vercel and the backend is **FastAPI** (Railway now, Render in the plan). There is no Next.js middleware to put this in, and the browser must talk only to FastAPI. | `Docs/Architecture.md` 1, 5; PF 4; `frontend/vercel.json` | G2 |
| 2 | **Supabase Anonymous Sign-ins / Supabase Auth** for guests. | Forbidden: PF 8.1 says Supabase Auth is not used; the browser holds no Supabase key. Each anonymous sign-in also creates an `auth.users` row, which is a stored guest. | PF 4, 8.1; Decisions 15 Oct "System flow" | G1 (D6), G2 |
| 3 | **Guest profiles in a Supabase `users` table** (`user_type = 'guest'`). | Breaks the scope owner's ruling of 20 Oct ("Guest footprint is a count only") and the chat (C5). It also collides with the existing `users` table, which is for Members only, and would grow by one row per browser forever. | Decisions 20 Oct; Schema `users`, `guest_visits`; Community.md 1 | G3, G4.5 |
| 4 | **`visit_logs` with `user_agent` and `ip_hash` on every visit**, no retention. | Per-visit device fingerprints are personal data. An unkeyed IP hash is reversible by brute force (the IPv4 space is small). PF 26 bans raw IPs in logs; Security 3.3 forbids IP as identity. No retention rule exists for it. | PF 14.2, 26; Security 3.3, 3.7 | G4.5, G6 (no per-visit rows) |
| 5 | **A − B formula is wrong**: `Total visits − (New Guests + New Verified)` subtracts *people* from *visits*, and `is_new_user = true` is never cleared, so "new" means "ever". | The number is only meaningful if "visit" and "new" are defined over the same period and unit. Over 30 days a new guest who comes 5 times adds 5 visits but 1 "new". | Draft section 4 | G4.1, G5 |
| 6 | **"Private URL" dashboard with "RBAC"**, but no staff login exists. | Staff auth (R04/R11) is not built; staff routes return 501 in production. A hidden URL is not access control (Security 4.1: knowing `/admin` grants no authority). The dev added the page **inside the public frontend**, but PF 5.1 says staff pages are a separate build, never in the public bundle. | PF 5.1, 25; Security 4.1; screenshot 3 | D1, D3 |
| 7 | **HttpOnly cookie for the guest UUID.** | Not allowed: only member session, staff session and language cookies are permitted (Security 3.4, PF 5.3). Also `*.vercel.app` → `*.railway.app` is cross-site, so Safari and Chrome block it as a third-party cookie. And an HttpOnly cookie cannot drive the local badge the chat asked for (C6). | PF 5.2, 5.3; Security 3.4; Architecture 5 | G3.2 (local storage, JSON bodies only) |
| 8 | **Guest → verified "conversion"** reuses the guest id on the account. | Links anonymous browsing and reviews to a named account, which the count-only rule and Review.md 1.1 (a Guest has no account) avoid. Member accounts (R04) are also on hold. | Decisions 20 Oct; Review.md 1.1 | G3.4 (no linking) |

## Other issues

| # | Issue | Fix |
|---|---|---|
| 9 | Redis is an explicit deferral (PF 32, PF 14.5, Decisions "Scope control"). Adopting Upstash needs a dated decision and a processor-register entry (Security 3.8 deploy gate). The draft has neither. | 10, 11 (G10) |
| 10 | "`active_guests_count` incremented via HyperLogLog": HLL counts distinct items, it is not incremented, and "active" is undefined. With no server-side guest id there is nothing to count distinctly. | Dropped; daily counters instead (5) (G4.4) |
| 11 | "Counter reset at 00:00 UTC". The platform's day is **Asia/Dhaka** (Decisions 14 Oct; API 5.14). A UTC day splits Bangladesh evenings. | Dhaka-date keys with TTL (5) (G4.4) |
| 12 | "Fire-and-forget" telemetry. On serverless an unawaited call is often killed; on FastAPI it hides failures. No behaviour is defined for Redis being down. | One awaited pipeline, fail-open with a dropped-count metric (5.4) (G4.6) |
| 13 | No durability: Redis is a cache in the draft, but it would be the only copy of history. | Nightly roll-up of *aggregate* numbers into Postgres (5.3) (G4.5) |
| 14 | No abuse control: anyone can inflate counts with a script. | Keep the existing burst + per-network limits (5.5) (G4.6) |
| 15 | Badge "from a server-validated JWT payload". There are no JWTs (opaque server sessions, PF 8.2) and guests have no session. | Badge from local state (3.2) (G3.3) |
| 16 | Sequential ids "collide": they don't; the real problems are that they are guessable, reveal traffic volume and are lost on a new device. | Random tag (3.1) (G3.1) |
| 17 | The public tag on reviews must not be client-supplied, or anyone can post under someone else's tag. | Server derives the tag from the guest scope secret (3.3) (G3.1) |
| 18 | "Verified" is ambiguous: UI-Architecture 1.1 reserves "Verified Member" for the verification badge. | Dashboard says "Verified (signed-in members)"; defined in 6 (G4.1) |
| 19 | Railway database question (screenshot 4). | No. Supabase stays the only database; Upstash holds counters only (2) (G1 D6) |
| 20 | Existing docs say the opposite of the new design in places (API 5.14 "Guest #N", Schema `guest_visits`, UI-Architecture "Guest #N"). | Companion changes listed in 12 (G10) |

## What the draft got right

- A random identifier instead of `guest 1, 2 …` (C1).
- Admin data served by an authenticated API route, not by reading client state.
- Redis for fast counters and Postgres as the system of record.
- Rendering status from server-checked data rather than trusting the client for authority.
