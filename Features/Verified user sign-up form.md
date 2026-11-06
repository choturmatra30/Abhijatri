# Verified User Sign-Up Form

**Companions:** `Features/Verified Users Interface.md` (what a Verified Member can do) and `Features/Verified Users Interface Architechture.md` (how it is built).
**Depends on:** account registration and email verification (Platform-Foundation.md, R04, Supabase Auth proxied by the API); the **implemented verification case** in the moderation dashboard (`Docs/Moderation-Dashboard-Specification.md` 5.2 Queue, 10 permissions, 11.1 state machine, 11.2 appeals, 12.4 endpoints, 16 tables, 18 retention); the `verifications` record (Review.md 2.3); notifications and audit.
**Builds on, does not replace:** this form fills the existing `verification_cases` and `verification_evidence` tables and goes through the existing staff queue, leases, appeals and retention job. Section 8 lists only the columns and routes it adds.
**Supersedes:** Review.md amendment A3 and Decisions.md "Not adopted: NID", and the Security.md deploy gate on ID images, as decided by the owner on 6 Nov 2026 (section 16).

---

## 1. Purpose

Email verification proves a person controls an inbox. It does not prove who they are. Being a **Verified Member** means a moderator has checked that a real adult with a real identity stands behind the account.

The sign-up form collects **exactly what moderators need to make that decision**, plus the few verified facts that later features depend on:

| Verified fact | Used by |
|---|---|
| Real person, one account per person | Everything: reviews, communities, tours |
| Age 18 or over (birth year) | Tour access (spec Q5), age bands in Find People |
| Gender as on the identity document | Women-only and Men-only tours |
| Student status and its end date | Students-only tours |
| Verified phone number | Account recovery, safety contact during tours, one-account rule |
| Home district | Division shown in Find People; regional matching |

It collects nothing else. In particular it never asks for payment details, and it keeps identity images only as long as the review and a possible appeal need them (section 9).

---

## 2. The Whole Journey

```
 Guest ──Stage A: create account──▶ Member (email unverified)
       ──verify email (link)──────▶ Member
       ──Stage B: verification application (7 steps, saved as you go)──▶ Submitted
       ──moderator review──▶ Approved = Verified Member  (badge, tours, image reviews)
                         └─▶ Needs clarification ──user fixes the named step──▶ Submitted
                         └─▶ Rejected (reason, cooldown)
```

Stage A is short so that people start using the guide at once. Stage B is offered when the person tries something that needs it (writing a rated review, joining a community, opening Tours) and from the profile page.

---

## 3. Stage A: Create Account (Member)

This is the existing registration form. It is listed here so the whole sign-up is in one place.

| # | Field | Rules |
|---|---|---|
| A1 | Email | Valid format, lowercased; disposable-email domains refused; unique |
| A2 | Password | 10 to 128 characters; checked against breached-password lists (k-anonymity range check); no composition rules |
| A3 | Display name | 2 to 40 characters; the existing reserved-name and confusable checks (Review.md 3.3) |
| A4 | Preferred language | Bangla or English |
| A5 | "I am 18 or older" | Required tick. Proof comes later in Stage B. |
| A6 | Terms and Privacy | Required tick, with version recorded |
| A7 | Turnstile | Invisible challenge |

After submit, the person can browse as a Member and gets a verification email (link valid 24 hours). Google sign-in through Supabase Auth may replace A1 and A2; the email is then already verified.

---

## 4. Stage B: Verified Member Application

A seven-step wizard on one route, `/verify`. Every step saves a draft on the server when the person presses Next, so a dropped connection loses nothing. A progress bar shows "Step 3 of 7". Each step explains in one line **why** the information is needed.

Before Step 1 the screen lists what the person will need: their identity document, their phone, about 5 minutes, and good light for a selfie.

### Step 1. Eligibility and consent

| Field | Type | Rules |
|---|---|---|
| Email verified | System check | Must be true, otherwise the person is sent to verify first |
| Age confirmation | Tick | "I am 18 or older" |
| Consent to identity check | Tick | Plain-language text: what is collected, that moderators see it, that document and selfie images are deleted 24 hours after approval, or 30 days after rejection (so an appeal can be checked), that only the last 4 digits of the document number are kept |
| Not restricted | System check | Accounts with an active verification ban (section 10.3) cannot start |

### Step 2. Personal details

All fields must match the identity document. The form says so above the fields.

| Field | Type | Rules | Stored as |
|---|---|---|---|
| Full legal name (English) | Text | 2 to 100 characters, letters, spaces, dots and hyphens | Encrypted; shown only to staff |
| Full legal name (Bangla) | Text, optional | Bangla script | Encrypted |
| Date of birth | Date picker (day, month, year) | Age 18 or over on the day of submission; not over 100 | Encrypted full date; **birth year** kept in plain form for age bands |
| Gender | Choice: Female, Male, Third gender | As printed on the document | Attribute set by the moderator on approval |
| Home district | List of the 64 districts | Required | District; division derived |
| Current city or area | Text, optional | Up to 60 characters | Plain; never shown publicly |
| Occupation | Choice: Student, Employed, Self-employed, Not working, Other | Required; "Student" opens Step 5 | Plain |

The display name from Stage A stays the public name. The legal name is never shown to other users. Tour members see the first word of the display name.

### Step 3. Phone number

| Field | Rules |
|---|---|
| Mobile number | Bangladeshi mobile in the form `+8801XXXXXXXXX` (operator prefixes 013 to 019). Normalised to E.164. |
| One-time code | 6 digits by SMS, valid 5 minutes, 3 wrong attempts per code, at most 3 codes per number per hour and 5 per account per day. Resend after 60 seconds. |

- A phone number can belong to only **one** Verified Member. The server keeps a keyed hash of the number to enforce this, and the number itself encrypted.
- A number already used by another Verified Member shows: "This number is already linked to a verified account. Contact support if this is your number." It never says which account.
- Bangladeshi SIMs are registered to a national ID, which makes this a useful fraud signal at low cost.

### Step 4. Identity document

| Field | Rules |
|---|---|
| Document type | Choice: National ID card (smart or laminated), Passport, Driving licence |
| Document number | Required. NID: 10 or 17 digits (old 13-digit numbers accepted). Passport: letter plus digits. Licence: as printed. |
| Expiry date | Required for passport and driving licence; must be in the future |
| Front photo | Taken with the camera or chosen from the gallery; JPEG, PNG or HEIC, up to 10 MB |
| Back photo | Required for NID cards and driving licences |

Guidance shown with the camera: all four corners visible, no glare, no fingers over the text, no screenshots or photocopies. The app checks in the browser that the image is sharp and large enough before upload, and suggests a retake if not.

**What is stored:** the document type, the **last 4 digits** of the number, a keyed hash (HMAC-SHA-256 with a server secret) of the normalised number for duplicate detection, and the expiry date. The full number is shown to the moderator only while the case is under review, and is deleted with the images (section 9).

A birth registration certificate is **not** accepted because it has no photo. A person without any of the three documents can contact support; staff can approve a manual alternative and record why.

### Step 5. Student details (only if Occupation is Student)

| Field | Rules |
|---|---|
| Institution | Search list of Bangladeshi universities, colleges and madrasas (UGC and board lists); "Other" with text |
| Student ID card photo | Front, same rules as Step 4 |
| Institutional email, optional | An address on an allowed academic domain (`*.ac.bd`, `*.edu.bd` and a staff-maintained list). Verified by a 6-digit email code. A verified institutional email speeds up review. |
| Expected end of study | Month and year, at most 6 years ahead |

On approval the moderator sets `is_student = true` and `student_until` (the end date shown on the card, or the expected end of study, whichever is earlier, and at most 1 year from now). Student status then needs a quick renewal (new card photo) every year. A person can add student details later without redoing the whole application.

### Step 6. Live selfie

1. The camera opens in the app. Choosing a gallery photo is not allowed for this step.
2. The screen shows a **random 4-digit code** and one random instruction, for example "Hold up three fingers" or "Turn your head to the left".
3. The person takes the photo while showing the code written on paper or on their hand, or while following the instruction. The capture records the code and instruction that were shown.
4. The moderator compares the face with the document photo and checks the code or gesture. This proves the person is present, not just holding someone else's ID.

The selfie is deleted with the document images (section 9). It is never used as a profile photo.

### Step 7. Default emergency contact, review and submit

| Field | Rules |
|---|---|
| Emergency contact name and relationship | Optional now, required before a person's first tour starts |
| Emergency contact phone | Bangladeshi or international number; cannot be the person's own number |
| Review screen | All entered data, thumbnails of images, with an Edit link per step |
| Declaration | "The information is true and the document is mine. I understand that false information leads to rejection and a ban." |
| Submit | Turnstile check; creates the application in state **Submitted** |

The emergency contact is stored encrypted on the profile and copied into a tour's Safety module when the person joins (spec 13.4). It is optional here because it serves tours, not identity.

After submitting, the person sees: "Thanks. A moderator usually reviews applications within 48 hours. We'll email you and tell you in the app." They can keep using Abhijatri as a Member meanwhile.

---

## 5. Application States

These are the states of the existing verification case (moderation spec 11.1), plus `draft` and `expired`, which this form adds.

| State | Meaning | The person can |
|---|---|---|
| `draft` (new) | Started, not submitted; steps saved on the server | Continue, discard |
| `submitted` | Waiting in the staff queue | Withdraw |
| `in_review` | A moderator has claimed the queue task (5-minute lease, renewed by heartbeat) | Wait |
| `needs_clarification` | The moderator asked for a fix to named steps, with a note | Fix those steps and respond (`/respond`), within 7 days |
| `escalated` | Sent to a superadmin, who must decide | Wait |
| `approved` | A `verifications` record is active; the person is a Verified Member | Use all verified features |
| `rejected` | Not approved, with a reason | Appeal within 30 days (moderation spec 11.2), or apply again after the cooldown (section 10.3) |
| `withdrawn` | The person cancelled | Start again |
| `expired` (new) | A draft not submitted within 14 days, or no response within 7 days of `needs_clarification` | Start again |

After approval, the **verification** (not the application) can become:

| Verification state | When | Effect |
|---|---|---|
| Active | Approved | Badge and access |
| Renewal due | 30 days before the document expires, or 2 years after approval, whichever is first | Reminder to upload a current document and a new selfie (Steps 4 and 6 only) |
| Lapsed | Renewal not done by the due date | Badge hidden; tours and communities keep membership as Inactive until renewed. Earlier rated reviews keep counting (Review.md: eligibility frozen at publication). |
| Revoked | Fraud or serious abuse: a superadmin opens an account enforcement case (moderation spec 11.1) that revokes the verification | As Lapsed, plus the abuse-revocation rating recomputation (Review.md) and a ban. Appealable like any enforcement case. |

The application's state rules are enforced by the server. Any other move returns `422 TRANSITION_NOT_ALLOWED`.

---

## 6. Moderator Review

Verification cases arrive in the existing staff dashboard **Queue** tab as `task_type = verification` (moderation spec 5.2), and follow its rules (5.3): claim before deciding, heartbeat, release, `expected_version`, `Idempotency-Key`, and no deciding one's own case (`403 SELF_MODERATION_FORBIDDEN`). Only Verified Members can be granted the moderator role (moderation spec P-02), so every reviewer has passed this same check.

### 6.1 Review screen

Left side: the document images and selfie (shown through 60-second signed links, with the moderator's ID as a faint watermark, no download button). Right side: the entered details and a checklist.

| # | Check | Pass when |
|---|---|---|
| 1 | Document looks genuine | Correct layout for its type, no visible editing, not a screen photo or photocopy |
| 2 | Name matches | Entered legal name equals the document |
| 3 | Date of birth matches | And the person is 18 or over |
| 4 | Gender matches | As printed |
| 5 | Number matches | The entered number equals the one on the image |
| 6 | Not expired | Passport and licence expiry in the future |
| 7 | Face matches | Selfie and document photo show the same person |
| 8 | Liveness | The code or gesture in the selfie matches what was shown |
| 9 | Student card (if any) | Name matches; institution and end date readable |
| 10 | System signals | No duplicate document or phone; no risk flags (section 10) |

### 6.2 Decisions

| Decision | Requires | Result |
|---|---|---|
| Approve | All checks ticked; moderator sets gender, birth year, and student status with end date | `verifications` record Active; `verification_attributes` written; badge appears; email and in-app notice |
| Needs clarification | Choose which steps to redo and a reason from the reason-code list (blurry photo, glare, missing back side, selfie code not visible, other) plus a note | Person is told exactly what to fix |
| Reject | Reason from a list (document not genuine, details do not match, face does not match, under 18, duplicate account, other) plus an internal note | Person sees the listed reason, never the internal note; cooldown starts |
| Escalate | Any doubt, or a high-risk flag | State `escalated`; only a superadmin can decide (moderation spec 10) |

**Conflict of interest.** A moderator must not review someone they know; they release the item with "Conflict" and it returns to the queue.

**Second approval.** Applications with a risk flag (section 10.2) are escalated automatically, so a superadmin decides them.

**Appeals.** A rejected person can appeal once within 30 days (Asia/Dhaka). An independent reviewer decides; overturning grants the verification (moderation spec 11.2). A superadmin can also reopen a rejected case within 30 days (P-05).

**Reason codes.** Rejection and clarification reasons come from the server's reason-code list (`GET /admin/reason-codes`, P-06), extended with the codes in this section.

**Service target.** 90% decided within 48 hours, all within 7 days. The ops dashboard shows queue length and turnaround (Review.md metrics).

Every view of evidence and every decision is written to `audit_events` with the moderator, time and reason.

---

## 7. What Each Party Sees

| Data | The person | Other users | Moderators | Superadmins |
|---|---|---|---|---|
| Display name, badge | Yes | Yes | Yes | Yes |
| Legal name, full date of birth | Yes | No | During review, and in the user's record | Yes |
| Birth year, age band | Yes | Age band only (Find People, opt-in) | Yes | Yes |
| Gender | Yes | Only as eligibility (they see a Women-only tour; never a label on the person) | Yes | Yes |
| Phone | Yes | Never (tours use the native chat) | Last 4 digits | Full, with reason, audited |
| Document number | Last 4 digits | No | Full during review only; then last 4 | Last 4 |
| Document images and selfie | Until deleted | No | During review only | During review or escalation only |
| Home district | Yes | Division only (opt-in) | Yes | Yes |
| Emergency contact | Yes | Tour organisers during an Ongoing tour or SOS | Break-glass only | Break-glass only |

---

## 8. Data Model

New and changed tables (all with RLS on and no anon grants, Alembic migrations only).

```sql
-- Existing table (moderation spec 16). Its state check gains 'draft' and 'expired',
-- and its "one open case per applicant" index now also covers 'draft'.
-- Existing columns (id, user_id, state, version, purge_after, ...) are unchanged.
-- Leases stay on moderation_tasks, as today.
alter table verification_cases
  add column legal_name_enc    bytea,     -- envelope encrypted
  add column legal_name_bn_enc bytea,
  add column dob_enc           bytea,
  add column birth_year        smallint check (birth_year between 1900 and 2100),
  add column gender_claimed    text check (gender_claimed in ('FEMALE','MALE','THIRD')),
  add column home_district     text,
  add column current_area      text,
  add column occupation        text,
  add column phone_id          uuid references phone_numbers(id),
  add column doc_type          text check (doc_type in ('NID','PASSPORT','DRIVING_LICENCE')),
  add column doc_number_enc    bytea,     -- deleted with the evidence
  add column doc_last4         text,
  add column doc_hash          bytea,     -- HMAC of the normalised number
  add column doc_expiry        date,
  add column is_student_claim  boolean not null default false,
  add column institution_id    uuid,
  add column institution_email_verified boolean not null default false,
  add column study_end_month   date,
  add column liveness_code     text,
  add column liveness_gesture  text,
  add column clarification_steps text[],
  add column risk_flags        text[] not null default '{}',
  add column submitted_at      timestamptz,
  add column draft_expires_at  timestamptz;

-- Existing table verification_evidence (files stay in the verification-evidence bucket):
alter table verification_evidence
  add column kind   text not null check (kind in ('DOC_FRONT','DOC_BACK','SELFIE','STUDENT_CARD')),
  add column sha256 bytea,
  add column phash  bytea;               -- perceptual hash for reuse detection

create table phone_numbers (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id),
  phone_hash bytea not null,       -- HMAC of E.164 number
  phone_enc bytea not null, last4 text not null,
  verified_at timestamptz
);
create unique index one_verified_phone on phone_numbers (phone_hash) where verified_at is not null;

create unique index one_document_per_person
  on verification_cases (doc_hash) where state = 'approved';
```

- `verifications` (existing) gets one row per approval: type `IDENTITY`, method `DOCUMENT_SELFIE_REVIEW`, approver, decision date, expiry (renewal due date), revocation.
- `verification_attributes (user_id pk, gender, birth_year, is_student, student_until, set_by, set_at)` is written only by the approval transaction and staff routes. Tours read eligibility from here (architecture 5.3).
- `emergency_contacts_default (user_id pk, ciphertext, wrapped_key, key_id, nonce)`.
- `verification_bans (user_id, reason, until, created_by)` and `doc_hash` and `phone_hash` checks for banned identities.

The approval runs in the existing decision pipeline (moderation spec 9), in one transaction: check the task lease and `expected_version`, write `verifications` and `verification_attributes`, set state Approved, delete `doc_number_enc`, write the outbox event `verification.approved` (which notifies the person and schedules evidence deletion) and the audit event.

---

## 9. Evidence Storage and Deletion

1. **Upload:** the API returns presigned upload URLs to a private `verification-quarantine` bucket, valid 10 minutes, one per image, with size and type fixed in the signature.
2. **Processing:** a worker checks the file's real type, scans it (ClamAV), strips all metadata including GPS, re-encodes to JPEG at a maximum of 2,000 px, records the SHA-256 and moves it to the private `verification-evidence` bucket. Originals are deleted.
3. **Encryption:** the bucket uses server-side encryption, and each object is also encrypted by the API with a per-application data key (envelope encryption, key in KMS or Supabase Vault). A leaked bucket is unreadable.
4. **Viewing:** only through the staff review screen, with 60-second signed links, watermarking, and an audit event per view (Review.md rule for evidence).
5. **Deletion** (the existing retention job, moderation spec 18): evidence and the full document number are deleted, and their data keys destroyed, **24 hours after approval**, and **30 days after rejection or withdrawal** so an appeal can still be checked. An open appeal blocks deletion until it is decided. Drafts and their images are deleted after 14 days. Cases pending for 7 days raise the existing queue-overdue alert. Evidence under a fraud investigation is kept by a superadmin hold with a reason, for at most 90 days.
6. **Never** in backups beyond the deletion window: the evidence bucket is excluded from long-term backups; database rows hold only keys and hashes.

---

## 10. Fraud and Abuse Prevention

### 10.1 Automatic checks before review

| Signal | Action |
|---|---|
| Document hash matches an approved or banned person | Block submission: "This document is already linked to an account." Flag to staff. |
| Phone hash matches another Verified Member or a banned person | Block at Step 3 |
| Same document image hash (or near-identical perceptual hash) used before | Risk flag |
| Image has editing-software metadata, or is a screenshot | Risk flag |
| Many applications from one device or network in a day | Risk flag; Turnstile hardened |
| Disposable or newly created email with immediate application | Risk flag |
| Date of birth makes the person under 18 | Refuse at Step 2 with a polite message |

### 10.2 Risk flags

Any flag puts the application in a separate queue view and requires a second staff approval (section 6.2).

### 10.3 Cooldowns and bans

| Situation | Rule |
|---|---|
| First rejection | Can apply again after 7 days |
| Second rejection | 30 days |
| Third rejection, or any rejection for a fake document | 90-day ban, superadmin can lift; document and phone hashes added to the ban list |
| Revocation for fraud | Permanent ban by superadmin decision |

### 10.4 Rate limits

Draft creation: 3 per account per day. Image uploads: 20 per application. OTP limits as in Step 3. Submissions: 1 per account per day.

---

## 11. API

Existing routes (moderation spec 12.4) are kept. New routes are marked **new**.

| Method and path | Purpose | |
|---|---|---|
| `GET /api/v1/verifications/mine` | Own case, its state, and which steps are complete | existing, extended |
| `POST /api/v1/verifications` | Open a case (now starts in `draft`) | existing, extended |
| `PATCH /api/v1/verifications/{case_id}/steps/{step}` | Save one step; per-field validation errors | **new** |
| `POST /api/v1/verifications/{case_id}/phone/send-code`, `/phone/verify` | Phone OTP | **new** |
| `POST /api/v1/verifications/{case_id}/student-email/send-code`, `/student-email/verify` | Institutional email code | **new** |
| `POST /api/v1/verifications/{case_id}/liveness-challenge` | Server issues the random code and gesture | **new** |
| `POST /api/v1/verifications/{case_id}/evidence` | One-time upload URL, now with `kind` | existing, extended |
| `POST /api/v1/verifications/{case_id}/evidence/{evidence_id}/complete` | Confirm the upload | existing |
| `POST /api/v1/verifications/{case_id}/submit` | `draft → submitted`; Turnstile; creates the queue task | **new** |
| `POST /api/v1/verifications/{case_id}/respond` | Answer clarification; back to the queue | existing |
| `POST /api/v1/verifications/{case_id}/withdraw` | Withdraw | existing |
| `POST /api/v1/admin/verification-cases/{case_id}/transition` | `in_review`, `needs_clarification`, `approved` (now requires gender, birth year, student fields), `rejected`, `escalated` | existing, extended |
| `POST /api/v1/admin/verification-cases/{case_id}/evidence/{evidence_id}/url` | 60-second signed URL; audited `evidence.viewed` | existing |
| `POST /api/v1/admin/verification-cases/{case_id}/reopen` | Superadmin reopens a rejection within 30 days | planned P-05 |
| `POST /api/v1/appeals` | Appeal a verification decision | existing |

All writes need the CSRF token and an `Idempotency-Key`. The liveness code is generated by the server, never by the client. Error codes follow the existing convention.

## 12. Tools and Services

| Need | Choice | Notes |
|---|---|---|
| SMS one-time codes | A Bangladeshi SMS gateway (SSL Wireless or BulkSMSBD) for local cost and delivery, behind an `SmsProvider` interface; Twilio Verify as fallback | Masking sender ID "Abhijatri" needs registration with the operator |
| Camera capture | Browser `getUserMedia` with a capture screen; no gallery for the selfie | Works in the PWA on Android and iOS |
| Image checks in the browser | A small sharpness and size check before upload | Saves data on bad photos |
| Upload | Presigned PUT to Supabase Storage private buckets | Same pipeline as review images |
| Processing | libvips (pyvips), ClamAV | Strips GPS |
| Encryption | Envelope encryption with AES-256-GCM; master key in a cloud KMS or Supabase Vault | Shared with the Safety module |
| Bot defence | Cloudflare Turnstile | Existing |
| Breached passwords | k-anonymity range API (Have I Been Pwned) | Only a hash prefix leaves the server |
| Later: government check | Bangladesh Election Commission NID verification through an authorised partner (for example Porichoy) | Section 15 |
| Later: assisted review | Document text reading (OCR) and face similarity scoring to pre-fill and rank, never to decide alone | Section 15 |

---

## 13. Screens and Experience

1. **Entry points:** a "Get verified" card on the profile, and a prompt whenever a Member taps a verified-only feature ("Verified members can join tours. It takes about 5 minutes.").
2. **Wizard:** one step per screen on a 360 px phone, large touch targets, Bangla and English, errors shown under each field in plain words.
3. **Camera screens:** an outline guide for the card and the face, live hints ("Too dark", "Move closer"), retake before upload.
4. **Low data:** images are compressed on the phone to under 1 MB before upload; uploads resume if the connection drops.
5. **Status page** `/verify/status`: the current state, what happens next, and for Needs clarification the exact steps to fix with one button each.
6. **Notifications:** submitted, needs more info, approved, rejected, renewal due (30 and 7 days), lapsed. Email and in-app.
7. **Accessibility:** WCAG 2.2 AA; every camera step has text instructions; the selfie step offers a gesture alternative for people who cannot write a code.

---

## 14. Acceptance Criteria

- VF-01 A Member with an unverified email cannot start an application.
- VF-02 A person under 18 by date of birth cannot submit, and no images are uploaded.
- VF-03 A phone number or document already linked to a Verified Member or a banned person is refused without revealing the other account.
- VF-04 The selfie step cannot use a gallery image, and the server rejects a selfie submitted without a liveness challenge issued for that application.
- VF-05 A moderator cannot approve without setting gender and birth year; an approval writes one `verifications` row and one `verification_attributes` row in one transaction.
- VF-06 Two moderators cannot decide the same application (lease); a stale decision returns 409.
- VF-07 Evidence images and the full document number are gone 24 hours after approval and 30 days after rejection (later only while an appeal is open), and their keys are destroyed.
- VF-08 Every evidence view and decision appears in the audit log.
- VF-09 A rejected person cannot reapply before the cooldown ends.
- VF-10 Students-only and gender-restricted tours read eligibility only from `verification_attributes`.
- VF-11 A renewal reminder is sent 30 days before document expiry, and the badge is hidden if renewal is not done.
- VF-12 The whole wizard can be completed on a 3G connection with a mid-range Android phone, resuming after a dropped connection.

---

## 15. Later Improvements

1. **Election Commission NID check** through an authorised partner. The person enters NID number and date of birth; the partner confirms a match (and optionally returns the photo for comparison). This turns the moderator's check 1 into a hard yes or no and reduces review time. It needs a contract and a data processing agreement, so it is added after launch.
2. **Assisted review:** read the document text to pre-fill fields and compare automatically; score face similarity and show it to the moderator. The moderator still decides.
3. **Verified organiser** level for people who complete several tours with good feedback.
4. **Re-verification on risk:** a reported or suspicious Verified Member can be asked to redo the selfie step.

---

## 16. Decisions and Documents to Update

| Decision (6 Nov 2026) | Replaces |
|---|---|
| Verified Member = identity approved by moderators from a document, a live selfie and a verified phone | Review.md A3 "no NID"; Decisions.md "Not adopted: NID"; Security.md deploy gate on ID images |
| Only the last 4 digits and a keyed hash of the document number are kept; images deleted 24 h after approval, 30 days after rejection | Review.md 2.3 "erase within 24 hours after approval or rejection"; the moderation spec's 30-day rule for rejected cases wins so appeals work |
| Gender and student status come from the verified documents | New |
| 18+ only | Security.md deploy gate on minimum age |
| The full TourMate system, including chat, is in scope; P0 to P3 is build order | Proposal and Review.md 12.4 exclusions of chat and group tours |

These documents should be updated to match: `Features/Review.md` (2.3, A3, 12.4), `Docs/Decisions.md`, `Docs/Security.md` (deploy gate), `Features/Platform-Foundation.md` (line on deferred phone and NID verification), the Proposal scope section, and `Features/Execution.md` (step 12 points to the three new documents).

**Identity proof (decided by the owner, 6 Nov 2026):** an ID document photo plus a live selfie, reviewed by moderators, with an Election Commission NID check added later (section 15).
