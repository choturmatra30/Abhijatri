# Testing and implementation record: Verified Members and Tours (8 November 2026)

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
