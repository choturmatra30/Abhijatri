# Testing and implementation record: Verified Members and Tours (8 November 2026)

## 0. Read first: email delivery fix, and how to reach the Superadmin and Moderator dashboards (9 November 2026)

### 0.1 Why sign-up and "already have an account" emails stopped arriving

Railway's log for `abhijatri-api` shows `account email failed via gmail: gmail token 400` on every send since 8 November. Checked directly against Google: the refresh token in `backend/.env` answers **`invalid_grant: Token has been expired or revoked`**. The sign-up and "you already have an account" emails are built correctly; the Gmail API simply refuses to issue an access token, so nothing leaves the server. (The form still says "check your email" by design, so it looks like a silent failure.)

Most likely cause: the Google Cloud OAuth consent screen is in **Testing** status. Google expires refresh tokens of Testing apps after **7 days**. The earlier "spam folder fixed" commits (`4988fe2`, `28f6948`: no forged Message-ID or Reply-To, clean bilingual body, localhost links refused) are still in the code and unchanged; the sending side was fine until the token died.

**Code change made today:** a refused token now logs the Google reason and the remedy (`providers.py`), and `python -m app.jobs.gmail_authorize` reads `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` from `backend/.env`, so no arguments are needed. No change to the message format, so the inbox placement that worked before is unchanged.

### 0.2 Fix steps (owner of `choturmatra@gmail.com`, about 3 minutes)

1. Google Cloud Console, <https://console.cloud.google.com/auth/audience> (select the project that owns the OAuth client first), **Audience**: press **Publish app** so the status is **In production**. Without this the new token dies again in 7 days. (`gmail.send` is a sensitive scope; an unverified app in production still works for the owner's own account, with a one-time "unverified app" warning.)
2. In a terminal, from `backend/`: `.venv\Scripts\python -m app.jobs.gmail_authorize`. Sign in as `choturmatra@gmail.com`, allow, and copy the printed `GMAIL_REFRESH_TOKEN=...` line.
3. Put it in `backend/.env` and in **Railway, service `abhijatri-api`, Variables** (`GMAIL_REFRESH_TOKEN`). Railway redeploys on a variable change. Production must have `EMAIL_PROVIDER=gmail`, `EMAIL_FROM=Abhijatri <choturmatra@gmail.com>` (the same address that authorised), `AUTH_EMAIL_DELIVERY=app`, and `FRONTEND_BASE_URL=https://abhijatri.vercel.app` (a `localhost` or `http://` link is refused on purpose).
4. Test: `.venv\Scripts\python -m app.jobs.send_test_email --to mdirfan-2023315978@cs.du.ac.bd` (with `EMAIL_PROVIDER=gmail` in `.env`), then on the live site register or press "resend" for `mdirfan-2023315978@cs.du.ac.bd`.
5. Expected: the message arrives in **Inbox** (the format is the one that passed on 8 November; the recipient is a university address, so inbox placement depends on that domain's filter and must be checked by hand). If it ever lands in Spam, open it once and press **Not spam**; that trains the filter for this sender.
6. Check Railway logs: no new `gmail token 400` line. If the address already has a confirmed account (`email_exists` in the log), sign-up sends the "You already have an Abhijatri account" email, which is correct; use **Forgot password** on the live site to get a link email instead.

### 0.3 Reaching the staff dashboards (Moderator and Superadmin)

The staff app is separate from the member app: locally `http://localhost:5175` (run `npm run dev` in `staff/`), online its own Vercel project (the staff project in the `choturmatra30` team). It uses the **same account** as the member app plus a mandatory authenticator app (TOTP). Members never see it.

**Superadmin (first one)**
1. Register on the member app and confirm the email (needs 0.2 working).
2. From `backend/`, with `DATABASE_URL` pointing at the target database (for production: `railway run`, which injects the service's own variables): `python -m app.jobs.bootstrap_admin --email mdirfan-2023315978@cs.du.ac.bd`, then type the email to confirm. It refuses if a superadmin already exists or the email is unverified.
3. Open the staff app and sign in with the same email and password. First sign-in shows a QR code: scan it with Google Authenticator, Authy or Microsoft Authenticator, and enter the 6-digit code. From then on sign-in is password then code.
4. Lost phone: `python -m app.jobs.reset_mfa --email <email>` (server side only, audited), then enrol again.

**Moderator**
1. The person registers and confirms their email, and must be a **Verified Member** first (rule P-02; granting the role otherwise fails with `VERIFICATION_REQUIRED`). Quick way: submit the verification application on the member app at `/account/verification`, and approve it as superadmin in the staff app (Verifications queue).
2. Superadmin, staff app, **Staff roles** tab: find the user, choose `moderator`, re-enter your password (the dialog asks), confirm. One active role per person; it is audited.
3. The moderator signs in on the staff app and enrols their own TOTP the same way. They see the review queue, reports, media and cases; they do not see superadmin-only screens (Staff roles, Notifications, escalated cases, evidence).

**Test checklist (do both, in two browser profiles or two `*.localhost` hosts so cookies do not collide)**
| Step | Expect |
|---|---|
| Superadmin signs in without TOTP code | refused, `MFA_REQUIRED` |
| Superadmin enrols TOTP, signs in | Staff dashboard with Staff roles, Notifications, Audit |
| Grant `moderator` to an unverified user | refused: verification required |
| Grant `moderator` to a verified user | success; audit row `staff.role_granted` |
| Moderator signs in and enrols TOTP | queue, reports, media; no Staff roles tab |
| Moderator opens a superadmin URL or API | 403 / hidden |
| Revoke the role | moderator loses access on next request |


**For:** Md. Irfan Iqbal (testing owner in `Abhijatri Project Gantt — CSE 3102.xlsx`).
**Gantt rows covered:** TM04 (Tourmates: privacy, capacity, reporting, safety), CM04 (permissions, reporting, blocking), MD04 (evidence file safety and lifecycle), H07 (automated regression), T03/T04 (functional and security flows), F07 (privacy checklist).
**Environment:** fully local stack, nothing touched production. API on `:8100`, Postgres `abhijatri_local`, local Supabase Auth and Storage, Mailpit on `:54324` (email and the development SMS provider).

## 1. How the run was done

Three Chrome tabs were signed in **at the same time**, one per role, each on its own `*.localhost` host so cookies do not collide:

| Role | URL | Account |
|---|---|---|
| Member (Nila Traveller) | `http://user.localhost:5180` | `user@abhijatri.test` |
| Moderator (Mahin Moderator) | `http://mod.localhost:5185` | `moderator@abhijatri.test`, TOTP |
| Superadmin (Shahana Superadmin) | `http://admin.localhost:5186` | `superadmin@abhijatri.test`, TOTP |

A second member (Rafi Traveller, `user2@abhijatri.test`) was driven by a script for the "other person" steps. Passwords and TOTP secrets are in the local, untracked `localstack-accounts.json`; they are not repeated here.

## 2. Test cases and results

| ID | Gantt | Case | Result |
|---|---|---|---|
| T-01 | TM04 | Unverified member calls Tours APIs (AC-01) | Pass: 404, landing page only |
| T-02 | F07 | Applicant under 18 | Pass: refused with the field message |
| T-03 | F07 | Reused phone number or document number | Pass: refused without naming the other account |
| T-04 | MD04 | Evidence upload; selfie needs a server-issued liveness code | Pass |
| T-05 | TM04 | Submit raises a risk flag; case escalates to superadmin; moderator cannot claim it | Pass |
| T-06 | MD04 | Superadmin opens evidence: inline watermarked image, audited, no new browser tab | Pass (after fix, see 3.1) |
| T-07 | F07 | Approve with 8-point checklist plus gender, birth year; member becomes Verified and sees Tours | Pass |
| T-08 | TM04 | Create draft, publish, private code issued | Pass |
| T-09 | TM04 | Second member joins by code; organiser approves; tour auto-confirms at minimum size | Pass: CONFIRMED, 2/4 |
| T-10 | TM04 | Chat both ways, appears without reload (5 s poll) | Pass |
| T-11 | TM04 | Budget: 2400 BDT split two ways | Pass: "Rafi owes Nila 1200.00" |
| T-12 | TM04 | Safety: save emergency contact, request check-in, answer it | Pass (after fix, see 3.2) |
| T-13 | CM04 | Member reports a chat message (reason `spam`) and the tour (default reason) | Pass (after fix, see 3.3) |
| T-14 | CM04 | Moderator sees the report with the conversation as it was, claims it, hides the message | Pass (after fix, see 3.4); the message shows "[removed]" to members |
| T-15 | CM04 | Moderator dismisses the tour report | Pass |
| T-16 | TM04 | Superadmin suspends the tour: members see a banner, chat is read-only (409) | Pass (after fix, see 3.5) |
| T-17 | TM04 | Superadmin restores the tour: chat works again | Pass |
| T-18 | F07 | Break-glass chat view needs a reason of 10+ characters | Pass; granted and viewed events audited |
| T-19 | MD04 | Audit log lists every action of this run | Pass |

## 3. Defects found and fixed during the run

1. **Evidence link opened at the staff origin** (relative URL, then a 404). The review screen now fetches the image with the session, shows it inline with a watermark, no download, no context menu.
2. **Safety tab did nothing visible.** Errors were swallowed, an empty form always sent a contact, and saved details were not loaded back. Rewritten with messages, prefill, and an inline two-step SOS confirmation instead of a browser dialog.
3. **Reports failed with the default reason.** The API expects lower-case codes (`other`); the client sent `OTHER`. Server and client now agree.
4. **Report tasks showed "The content of this task is gone."** The queue had no summary for `tour_report`, `chat_report` or `tour_safety`, and nothing could close them. Added a summary (reporter, reported member, tour, conversation snapshot) and `POST /api/v1/admin/tours/reports/{id}/resolve` with actions dismiss, hide message, restrict member, suspend tour, all under the task lease and audited (`tour.report_resolved`).
5. **Suspended tours looked normal to members.** Added a banner, and the workspace now refreshes every 15 s and on focus. Chat refusals show "Not sent: ..." instead of silently queueing.
6. **Staff Tour Operations used browser `prompt()` dialogs.** Replaced with an inline panel (reason list, note, days, break-glass justification).
7. **Liveness gesture was blank in staff details**; it now reads from the challenge table.
8. **Verification page:** pending cases now show a review-status screen (auto-refresh every 30 s) instead of "Start application"; the review step shows the entered data with Edit links.

## 4. Automated evidence

- New regression test `test_chat_and_tour_reports_reach_the_staff_queue_and_resolve_under_lease` covers defects 3 and 4 and the lease rule.
- It also surfaced two registry omissions, both fixed: the new audit action, and the audit-trail declaration for the new route.
- `tests/test_tours.py` plus `tests/test_verification_application.py`: 22 passed.
- Staff app: type-check clean, 46 tests pass, build clean. Member app: 192 tests pass, build clean.
- Backend `ruff` and `mypy` clean. The full backend suite was started last; see section 6.

## 5. Known limitations (not defects of this run)

- Chat is polled every 5 s; there is no WebSocket client in the frontend yet.
- Real SMS gateway, KMS/Vault, malware scanning and the national ID partner check are not built; development equivalents were used.
- Production feature flags stay off until this record is accepted.

## 6. Full-suite result

890 backend tests: 888 passed first run; the 2 failures were API-contract documentation for the new route, fixed and re-run green (`Backend-Implemented.md` section 9).
