# Verified Users Interface: Architecture

**Companion to:** `Features/Verified Users Interface.md` (the feature specification) and `Features/Verified user sign-up form.md` (how a Member becomes verified). Section numbers in the form "spec 7.4" point there.
**Builds on:** `Docs/Architecture.md` and `Docs/Decisions.md`. Nothing here replaces an existing decision. Where a new tool is added, section 3 says why and what it costs.
**Goal:** a secure, production-grade design that a small team can run on a small budget at launch, and that scales to hundreds of thousands of users without a rewrite.

---

## 1. Design Principles

1. **One system of record.** Supabase Postgres holds every tour, membership, message and expense. Redis and the CDN only speed things up; losing them loses no data.
2. **Invariants live in the database.** Capacity, one active membership per person, one pending request, and the single confirmation are enforced by constraints and locked transactions, not only by application code.
3. **Deny by default.** Every endpoint goes through `can(actor, action, resource)`. A non-member gets `404`, never `403`, so private tours are not revealed.
4. **Events, not side effects.** State changes write an `outbox_events` row in the same transaction. Notifications, chat activation, emails and search indexing are driven from the outbox, so they happen exactly when the change commits.
5. **Modular monolith first.** New modules live in the existing FastAPI service with clear boundaries. Chat is the only part designed to split into its own process when load requires it.
6. **Privacy by design.** Collect the minimum, encrypt the sensitive, delete on schedule, and log every privileged read.
7. **Offline-tolerant clients.** The PWA treats the network as unreliable: idempotent writes, client IDs, and resumable uploads.

---

## 2. System Overview

```
             ┌──────────── Vercel (CDN, edge) ───────────┐
 Phone/PWA ─▶│ frontend/ (React+TS+Vite PWA, Workbox SW) │
 Staff ─────▶│ staff/   (admin.<domain>)                 │
             └───────────────┬───────────────────────────┘
                             │ HTTPS (REST + WebSocket), __Host- cookies, CSRF
                             ▼
             ┌──────────── API (Docker, Railway/Render) ─────────────┐
             │ FastAPI modular monolith                              │
             │  tours · membership · matching · invitations          │
             │  workspace (itinerary, budget, safety) · tour-ops     │
             │  chat gateway (WebSocket) · notifications (SSE)       │
             │ Workers: outbox relay · scheduler · media processor   │
             └───┬───────────────┬────────────────┬──────────────────┘
                 │               │                │
                 ▼               ▼                ▼
       Supabase Postgres   Upstash Redis     Object storage
       (RLS, PgBouncer)    (pub/sub, rate    (Supabase Storage now;
       system of record     limits, presence)  R2 option for chat media)
                 │
                 ▼
       Sentry · OpenTelemetry → Grafana Cloud · ops/ dashboard panels
```

Process types, all from the same Docker image:

| Process | Command | Scales by |
|---|---|---|
| `web` | Uvicorn/Gunicorn, REST + SSE | CPU, request rate |
| `realtime` | Uvicorn, WebSocket chat gateway | Open connections |
| `worker` | Outbox relay and job runner | Queue depth |
| `scheduler` | One instance, triggers time-based transitions every minute | Fixed at 1 (leader lock) |

At launch, `web` and `realtime` can be one process. They are separated by configuration, not code, when connections grow.

---

## 3. Technology Choices

| Concern | Choice | Why | Alternative considered |
|---|---|---|---|
| Frontend | React + TypeScript + Vite PWA (existing) | Already the stack; installable, offline-capable | Next.js: rejected in Decisions.md |
| Client data | TanStack Query + IndexedDB (Dexie) for chat cache and outbox queue | Mature cache and retry; IndexedDB survives restarts | Redux: more boilerplate |
| Offline | Workbox service worker, Background Sync where supported, foreground retry elsewhere | iOS lacks Background Sync, so a foreground retry loop is required anyway | |
| Forms and validation | React Hook Form + Zod; schemas generated from OpenAPI | One source of truth for field rules | |
| API | FastAPI, SQLAlchemy 2, Psycopg 3, Pydantic v2 (existing) | Existing | |
| Migrations | Alembic only (existing) | Existing rule | |
| Database | Supabase Postgres 15+ with RLS (existing) | System of record | |
| Connection pooling | Supavisor/PgBouncer transaction mode for `web`; a small direct pool for `worker` and `LISTEN` | Advisory locks and `LISTEN` need session connections | |
| Realtime chat | FastAPI WebSocket gateway + Redis pub/sub fan-out | Keeps auth, RLS and audit in one place; cheap | Ably or Pusher when connections exceed one region's capacity (section 8.6) |
| Notification stream | Existing SSE, changed from 2 s DB polling to Redis pub/sub | Fixes the known polling gap | Postgres `LISTEN/NOTIFY` (fine for one instance) |
| Cache, rate limits, presence | Upstash Redis (existing) | Already used for counters | |
| Jobs and scheduling | Postgres job table with `FOR UPDATE SKIP LOCKED` + one scheduler loop; existing outbox relay | No new infrastructure; transactional with business data | Celery/RQ: extra broker |
| Search | Postgres full text + `pg_trgm` + B-tree/GiST indexes; SQL scoring | Enough for tens of thousands of tours | Meilisearch or Typesense at large scale |
| Object storage | Supabase Storage private buckets (existing) for covers and receipts; S3-compatible multipart for chat media | Signed URLs, no public buckets | Cloudflare R2 (no egress fees) for chat media at scale |
| Resumable upload | S3 multipart with presigned part URLs (Uppy on the client) | Resumes after signal loss | tus protocol |
| Media processing | libvips (pyvips) for images, ffmpeg for video, ClamAV scan | Fast, strips EXIF location | |
| Encryption of sensitive fields | Envelope encryption: per-row data key, AES-256-GCM, key encrypted by a master key in a KMS or Supabase Vault | Database dump alone reveals nothing | pgcrypto with a static key: key sits next to data |
| Email | Existing Resend/Brevo/Gmail API through the notifications registry | Existing | |
| Web push (P2) | Web Push with VAPID keys | Works on Android and installed iOS PWAs | |
| Bot defence | Cloudflare Turnstile (existing) on publish, request and invite | Existing | |
| Feature flags | A `feature_flags` table cached in Redis, checked server and client side | Turn on P1 modules per environment | Unleash/GrowthBook later |
| Errors and tracing | Sentry (front and back) + OpenTelemetry → Grafana Cloud free tier | Traces across REST, WebSocket and workers | |
| Testing | pytest + pytest-asyncio + Testcontainers Postgres; Hypothesis for state machines; Playwright E2E; k6 load tests | Real Postgres needed for lock and constraint tests | |
| CI/CD | GitHub Actions: lint, type check, tests, migration check, OpenAPI diff, image build, deploy | | |

---

## 4. Module Boundaries

Each module owns its tables and exposes a service interface. Other modules call the service, never the tables.

| Module | Owns | Publishes events |
|---|---|---|
| `tours` | `tours`, `tour_destinations`, `tour_rules`, `tour_changes` | `tour.published`, `tour.confirmed`, `tour.at_risk`, `tour.cancelled`, `tour.started`, `tour.completed`, `tour.key_details_changed` |
| `membership` | `tour_members`, `tour_join_requests`, `tour_companions` | `request.created`, `request.decided`, `member.joined`, `member.left`, `member.removed` |
| `invitations` | `tour_invitations`, `invitation_optouts` | `invitation.sent`, `invitation.answered` |
| `matching` | `travel_preferences`, `discovery_settings` | none |
| `workspace` | `itinerary_items`, `itinerary_suggestions`, `expenses`, `expense_shares`, `settlements` | `expense.added` |
| `safety` | `emergency_contacts`, `medical_notes`, `meeting_points`, `checkins`, `sos_events` | `checkin.requested`, `sos.raised` |
| `chat` | `chat_channels`, `chat_messages`, `chat_reads`, `chat_attachments` | `message.created` (internal) |
| `tour_ops` | `breakglass_grants`; extends the staff dashboard's `moderation_tasks` (new task types), `enforcement_cases` (tour, member and message subjects), `sanctions` (`tourmate_restriction`), `reports`, `appeals` and `audit_events` (moderation spec 16) | `tour.suspended`, `tour.restored` |

---

## 5. Data Model

All tables have `id uuid primary key default gen_random_uuid()`, `created_at`, `updated_at`, and RLS enabled with no `anon` or `authenticated` grants (the API connects as a service role and enforces `can()`; RLS is the second line).

### 5.1 Tours

```sql
create type tour_lifecycle as enum
  ('DRAFT','RECRUITING','CONFIRMED','ONGOING','COMPLETED','CANCELLED','ARCHIVED');
create type tour_recruitment as enum ('OPEN','PAUSED','FULL','CLOSED','EXPIRED');
create type tour_policy as enum
  ('OPEN','STUDENTS','FAMILY','WOMEN','MEN','INVITE_ONLY');

create table tours (
  id               uuid primary key default gen_random_uuid(),
  public_id        text not null unique,          -- T-2026-7Q3MK
  code             text unique,                   -- ABH-7K92PX, null when retired
  code_version     int  not null default 1,
  creator_id       uuid not null references users(id),
  title            text not null check (char_length(title) between 8 and 80),
  description      text not null default '' check (char_length(description) <= 1000),
  lifecycle        tour_lifecycle   not null default 'DRAFT',
  recruitment      tour_recruitment not null default 'OPEN',
  is_at_risk       boolean not null default false,
  suspended_at     timestamptz,                   -- flag; null = not suspended
  policy           tour_policy not null,
  start_date       date not null,
  end_date         date not null,
  recruit_deadline timestamptz not null,
  min_members      smallint not null check (min_members between 2 and 30),
  max_members      smallint not null check (max_members between 2 and 30),
  seats_taken      smallint not null default 1,   -- counter, includes creator and companions
  budget_min_bdt   int, budget_max_bdt int,
  style            text, pace text, transport text,
  activities       text[] not null default '{}',
  confirmed_at     timestamptz,                   -- set once
  cancelled_reason text,
  search_tsv       tsvector,
  version          int not null default 1,        -- optimistic concurrency for edits
  check (end_date >= start_date and end_date - start_date <= 30),
  check (max_members >= min_members),
  check (seats_taken between 0 and max_members),
  check (recruit_deadline < (start_date::timestamp at time zone 'Asia/Dhaka') - interval '24 hours'),
  check (budget_min_bdt is null or budget_max_bdt >= budget_min_bdt)
);
create index on tours (lifecycle, recruitment, start_date) where suspended_at is null;
create index on tours using gin (search_tsv);
create index on tours using gin (activities);
```

`confirmed_at` is protected by a trigger that refuses any update that changes a non-null value. `tour_destinations (tour_id, destination_id, position)` links to the existing published destinations.

### 5.2 Membership and requests

```sql
create type member_role as enum ('CREATOR','CO_ORGANIZER','TOURMATE');
create type member_state as enum ('ACTIVE','LEFT','REMOVED','INACTIVE');

create table tour_members (
  id uuid primary key default gen_random_uuid(),
  tour_id uuid not null references tours(id),
  user_id uuid not null references users(id),
  role member_role not null,
  state member_state not null default 'ACTIVE',
  seats smallint not null default 1 check (seats between 1 and 5),  -- 1 + companions
  joined_via text not null check (joined_via in ('CREATED','REQUEST','INVITATION')),
  approved_by uuid references users(id),
  left_reason text, ended_at timestamptz
);
create unique index one_active_membership on tour_members (tour_id, user_id) where state = 'ACTIVE';
create unique index one_creator on tour_members (tour_id) where role = 'CREATOR' and state = 'ACTIVE';

create type request_state as enum ('PENDING','APPROVED','DECLINED','WITHDRAWN','EXPIRED','CLOSED');
create table tour_join_requests (
  id uuid primary key default gen_random_uuid(),
  tour_id uuid not null references tours(id),
  user_id uuid not null references users(id),
  state request_state not null default 'PENDING',
  answer text, message text check (char_length(message) <= 300),
  seats smallint not null default 1,
  decided_by uuid references users(id), decided_at timestamptz, decline_code text,
  via_code boolean not null default false
);
create unique index one_pending_request on tour_join_requests (tour_id, user_id) where state = 'PENDING';
```

Date overlap between a user's active tours is checked in the approval transaction with a query on `tours` joined to `tour_members` (an exclusion constraint cannot span two tables). `tour_companions (request_id, member_id, first_name, age_band, relationship)` is encrypted at the field level (section 10.4).

### 5.3 Invitations, preferences, discovery

- `tour_invitations (tour_id, invitee_id, inviter_id, state, expires_at)` with a partial unique index on pending `(tour_id, invitee_id)`, and a unique index on `(tour_id, invitee_id)` for declined rows to prevent re-inviting.
- `travel_preferences (user_id pk, date_ranges daterange[], budget int4range, destinations uuid[], regions uuid[], style, pace, activities text[], smoking, must_no_smoking bool)`.
- `discovery_settings (user_id pk, discoverable bool default false, audience text check in ('ALL','WOMEN','MEN'), updated_at)`.
- Verified attributes: `verification_attributes (user_id, gender, is_student, student_until date, birth_year, set_by, set_at)`. Written only by the moderator's approval transaction in the verification application (sign-up form, section 8). Gender values are FEMALE, MALE and THIRD; student eligibility also requires `student_until >= start_date`.

### 5.4 Chat

```sql
create table chat_messages (
  tour_id     uuid not null,
  seq         bigint not null,                 -- per-tour, gap-free order
  id          uuid not null default gen_random_uuid(),
  sender_id   uuid,                            -- null for system messages
  client_msg_id uuid,                          -- idempotency from the device
  kind        text not null check (kind in ('TEXT','SYSTEM','ANNOUNCEMENT','MEDIA','POLL')),
  body        text check (char_length(body) <= 2000),
  reply_to    bigint,
  edited_at   timestamptz, deleted_at timestamptz, hidden_by_staff_at timestamptz,
  created_at  timestamptz not null default now(),
  primary key (tour_id, seq)
) partition by range (created_at);
create unique index on chat_messages (tour_id, sender_id, client_msg_id, created_at);
```

- Monthly partitions are created by `pg_partman` (or a scheduled job), so old months are dropped cheaply at archive time.
- `seq` comes from `chat_channels.last_seq`, incremented with `update ... returning` in the insert transaction. This gives each tour a strict order that clients use to fetch "everything after seq N".
- `chat_reads (tour_id, user_id, last_read_seq)` gives unread counts and "Seen by N".

### 5.5 Workspace and safety

- `itinerary_items (tour_id, day, position, kind, title, place_id, starts_at, notes)`.
- `expenses (tour_id, author_id, paid_by, amount_paisa bigint check > 0, category, description, receipt_object, settled bool)`, `expense_shares (expense_id, user_id, share_paisa)` with a deferred constraint trigger that the shares sum to the amount. Money is stored in integer paisa, never floats.
- `emergency_contacts (member_id pk, ciphertext bytea, wrapped_key bytea, key_id text, nonce bytea)`; the same layout for `medical_notes`.
- `meeting_points`, `checkins (tour_id, requested_by, created_at)`, `checkin_answers`, `sos_events`.

### 5.6 Operations

- TourMate restrictions are rows in the existing `sanctions` table with kind `tourmate_restriction` (end date required, lazy expiry as in moderation spec P-01).
- `enforcement_cases` gains nullable `tour_id`, `tour_member_id` and `chat_message_id` subjects; the existing "exactly one subject" check covers them.
- `breakglass_grants (staff_id, tour_id, reason, granted_at, expires_at, scope text[])`.
- Reuses `reports`, `audit_events` (append only), `outbox_events`, `notifications`.

---

## 6. The Critical Transactions

### 6.1 Approve a request (and confirm automatically)

All steps in **one transaction**, `READ COMMITTED` with explicit row locks:

```
BEGIN;
SELECT * FROM tours WHERE id = :tour FOR UPDATE;              -- serialises all approvals for this tour
-- guards (each failure → ROLLBACK with a specific error code)
assert lifecycle in (RECRUITING, CONFIRMED) and suspended_at is null
assert recruitment in (OPEN, PAUSED)                         -- PAUSED: approve pending ones allowed
assert now() < recruit_deadline
assert can(actor, 'tour.approve', tour)                      -- creator or active co-organizer
SELECT * FROM tour_join_requests WHERE id = :req AND state = 'PENDING' FOR UPDATE;
assert requester eligible (verified, 18+, policy, not restricted, no block, no overlap)
assert seats_taken + req.seats <= max_members
INSERT INTO tour_members (...);                             -- unique index stops duplicates
UPDATE tour_join_requests SET state='APPROVED', decided_by=:actor, decided_at=now();
UPDATE tours SET seats_taken = seats_taken + req.seats, version = version + 1;
IF seats_taken >= min_members AND lifecycle = 'RECRUITING' THEN
   UPDATE tours SET lifecycle='CONFIRMED', confirmed_at=now(), is_at_risk=false;
   INSERT INTO chat_channels (tour_id, last_seq) VALUES (:tour, 0);
   INSERT INTO outbox_events ('tour.confirmed', ...);
ELSIF lifecycle='CONFIRMED' AND is_at_risk AND seats_taken >= min_members THEN
   UPDATE tours SET is_at_risk=false;  INSERT INTO outbox_events ('tour.risk_cleared', ...);
END IF;
IF seats_taken = max_members THEN
   UPDATE tours SET recruitment='FULL';
   UPDATE tour_join_requests SET state='CLOSED' WHERE tour_id=:tour AND state='PENDING';
END IF;
INSERT INTO outbox_events ('request.decided', ...);
INSERT INTO audit_events (...);
COMMIT;
```

Why this is safe: the `FOR UPDATE` on the tour row makes concurrent approvals for one tour run one after another; the `CHECK (seats_taken <= max_members)` is a final guard if a bug skips the check; the partial unique index stops a double membership; `confirmed_at` can be set only once. Acceptance AC-07 is proved by a test that fires 20 approvals in parallel threads against a real Postgres.

The same pattern is used for: accepting an invitation, leaving, removal, lowering the minimum, and the scheduler's transitions. Every one locks the tour row first, so there is a single lock order and no deadlocks.

### 6.2 Leaving and At Risk

Leave or remove: lock tour → set member `LEFT/REMOVED` → `seats_taken -= seats` → if `CONFIRMED` and `seats_taken < min_members`, set `is_at_risk = true` and write `tour.at_risk` → if recruitment was `FULL` and the deadline has not passed, set it back to `OPEN` → revoke chat access (section 8.4).

### 6.3 Idempotent APIs

Every state-changing endpoint accepts an `Idempotency-Key` header. The key and the response are stored in Redis for 24 hours (and in `idempotency_keys` for money-like operations such as expenses). A retried request from a flaky connection returns the first response instead of acting twice.

### 6.4 Edits with optimistic concurrency

Tour edits send `If-Match: <version>`. A stale version returns `409 STALE_VERSION` with the current data, so two organisers editing at once never overwrite each other silently.

---

## 7. Time-Based Transitions (Scheduler)

One `scheduler` process holds a Postgres advisory lock (`pg_try_advisory_lock`) so only one instance acts. Every minute it selects due tours with `FOR UPDATE SKIP LOCKED` in batches of 100 and runs the same guarded transitions as the API.

| Job | Condition (Asia/Dhaka) | Action |
|---|---|---|
| Recruitment deadline | `RECRUITING` and `now() >= recruit_deadline` | `CANCELLED` "Not enough tourmates"; pending requests `EXPIRED`; invitations closed |
| Recruitment expiry on confirmed | `CONFIRMED` and `now() >= recruit_deadline` | `recruitment = EXPIRED`; pending requests `EXPIRED` |
| At Risk warnings | `is_at_risk` and 48 h / 24 h before start | Notifications (once each, keyed by job and tour) |
| At Risk cancel | `is_at_risk` and `now() >= start - 24 h` | `CANCELLED` "Not enough tourmates before start" |
| Start | `CONFIRMED` and the start date begins | `ONGOING`; safety reveal windows open |
| End | `ONGOING` and the end date has passed | `COMPLETED`; chat read only |
| Archive | `COMPLETED/CANCELLED` and 90 days passed | `ARCHIVED`; drop chat rows (keep those linked to open reports) |
| Safety purge | 30 days after end | Delete emergency contacts, medical notes, companions' details; destroy their data keys |
| Invitations | `expires_at` passed | `EXPIRED` |
| Change window | 72 h after a key change | Close no-penalty leave window |
| Restrictions | `ends_at` passed | Handled by the existing sanction expiry (moderation spec P-01: lazy check on each request plus the daily retention job) |

Each job writes its own outbox events, so notifications are sent exactly once per transition. A job that fails is retried with backoff and alerts Sentry after three failures.

---

## 8. Real-Time Chat

### 8.1 Connection

1. The PWA opens `wss://api.<domain>/v1/realtime`. The browser sends the existing `__Host-` session cookie; the `Origin` header must be the app's origin (stops cross-site WebSocket hijacking).
2. The gateway authenticates once, then the client sends `subscribe {tour_id, after_seq}`. The gateway checks `can(user, 'chat.read', tour)` and replies with the missing messages since `after_seq` (up to 200, then the client pages through REST).
3. Heartbeat every 25 seconds; the client reconnects with jittered exponential backoff (1 s to 30 s).
4. One WebSocket carries all of a user's tours and also replaces SSE for users who have chat open. SSE stays for everything else.

### 8.2 Sending

```
client → {type:"send", tour_id, client_msg_id, body, reply_to}
gateway: rate limit (Redis token bucket 30/min) → can('chat.post') → validate
  BEGIN; UPDATE chat_channels SET last_seq = last_seq + 1 RETURNING last_seq;
         INSERT chat_messages ... ON CONFLICT (tour_id, sender_id, client_msg_id) DO NOTHING;
  COMMIT;
gateway → PUBLISH redis "tour:{id}" {seq, message}
every gateway instance → pushes to its connected members of that tour
gateway → client {type:"ack", client_msg_id, seq}
```

A duplicate send (same `client_msg_id`) returns the original `seq`, so the offline queue can retry safely. Messages go to Postgres **before** fan-out, so a Redis outage delays delivery but never loses a message; clients catch up by `after_seq` on reconnect.

### 8.3 Offline queue on the device

- Outgoing messages are stored in IndexedDB (`outbox` store) with `client_msg_id`, then sent in order when online. A message is removed from the queue only after its `ack`.
- The last 500 messages per tour are cached in IndexedDB, encrypted at rest with a key held in memory for the session (Web Crypto, non-extractable), and cleared on sign-out.
- After 24 hours unsent, or on a `403/404` (access lost), queued messages move to "Not sent".

### 8.4 Access revocation

When a member leaves, is removed, is restricted, loses verification, or the tour is suspended, the transaction writes an outbox event; the relay publishes `revoke {user_id, tour_id}` on Redis; every gateway drops that subscription immediately and the client deletes its local cache for the tour. Every send also re-checks membership against a short-lived cache (5 s), so even a missed revocation message expires in 5 seconds (AC-14).

### 8.5 Moderation hooks

Messages pass a fast filter (blocked words, phone and link detection) before insert. Reports snapshot the message and its neighbours into the report record, so evidence survives deletion or archive.

### 8.6 Scaling path

| Stage | Load | Setup |
|---|---|---|
| Launch | Under 1,000 concurrent connections | One process for `web` + `realtime`, Upstash Redis pub/sub |
| Growth | Up to ~20,000 connections | Separate `realtime` service, 2 to 4 instances behind sticky load balancing, dedicated Redis (Upstash fixed plan or Redis Cloud) |
| Large | Beyond that, or multiple regions | Move fan-out to Ably (or a NATS cluster); the API keeps persistence and authorisation, and issues Ably tokens scoped to the user's tours |

---

## 9. Media Pipeline for Chat (P2)

1. Client asks `POST /v1/tours/{id}/chat/uploads` with type and size. Server checks membership, quotas (per user per day, per tour total) and allowed types (JPEG, PNG, WebP, HEIC, MP4, MOV).
2. Server creates an S3 multipart upload in a **quarantine** bucket and returns presigned part URLs (5 MB parts, 15-minute expiry). Uppy uploads parts and resumes failed ones after reconnect.
3. On completion, the `media` worker: checks magic bytes, scans with ClamAV, strips EXIF (including GPS), makes resized WebP images (320, 1080 px) with libvips, transcodes video to H.264 720p with ffmpeg and makes a poster frame, then moves outputs to the private `chat-media` bucket.
4. The message is created as `MEDIA` with a placeholder; when processing finishes, a `media.ready` event updates it for all members.
5. Media is viewed through signed URLs valid 10 minutes, served through the CDN with the signature in the cache key. Low-data mode loads only the 320 px version until tapped.
6. Media is deleted with the chat at archive time.

---

## 10. Security

### 10.1 Authentication and sessions

Existing Supabase Auth proxied by the API, `__Host-` HttpOnly Secure SameSite=Lax cookies, CSRF synchronizer token on every REST write, TOTP for staff. WebSocket uses the same cookie plus an Origin check. No tokens are stored in `localStorage`.

### 10.2 Authorisation

- `can(actor, action, resource)` is the only gate, with a policy table in code, for example `tour.approve → actor is ACTIVE CREATOR or CO_ORGANIZER and not restricted`.
- Gate order on every tour route: verified and 18+ → not restricted → member or eligible viewer → role → resource state. Any failure before "member or eligible viewer" returns `404`.
- Eligibility for policies uses `verification_attributes`, never values sent by the client.
- Unit tests generate the full matrix of roles × actions × states from the spec permissions table (spec 13.2) and assert every cell.

### 10.3 Abuse and rate limits (Redis sliding windows)

| Action | Limit |
|---|---|
| Tour code lookup (failed) | 10 per user per hour; 50 per IP per hour |
| Join requests | 20 per user per day; 10 pending total |
| Invitations | 10 per organiser per day; 2 × seats left pending per tour |
| Person cards viewed | 100 per user per day |
| Chat messages | 30 per minute per user |
| Tour publish | 3 per user per day, plus Turnstile |

Breaches write `abuse_signals` rows shown in Tour Operations. Tour codes and public IDs use `secrets.choice` over the unambiguous alphabet; uniqueness is enforced by the unique index with retry.

### 10.4 Data protection

- **Field encryption** for emergency contacts, medical notes and companion details: AES-256-GCM with a random data key per row; the data key is wrapped by a master key stored outside the database (cloud KMS, or Supabase Vault at launch). The API decrypts only inside the routes allowed to show the data, and every decryption writes an audit event.
- **Crypto-shredding:** the safety purge destroys the wrapped keys, so backups that still hold ciphertext become unreadable.
- **Minimisation:** Find People reads from a `discoverable_profiles` view that exposes only coarse fields (age band from `birth_year`, division from home district). Exact birth date, phone and email are never in that view.
- **Logs** never contain message bodies, contacts or tokens; Sentry scrubbing rules are tested.
- **Retention** summary: chat 90 days after end; safety data 30 days after end; declined and expired requests 180 days; audit events 2 years.

### 10.5 Content and link safety

Bodies are stored as plain text and rendered escaped (React default); no HTML or Markdown rendering in chat. A strict Content Security Policy (`default-src 'self'`, no inline scripts) is applied to the PWA. Links are shown with a warning interstitial for domains outside an allowlist.

### 10.6 Staff access

Staff routes stay under `/api/v1/admin/*` with the existing role checks and the staff dashboard's decision pipeline (moderation spec 9). Break-glass is a grant row with a 60-minute expiry checked on every staff read of private content; each read is audited with the grant id. Cancelling a Confirmed tour needs a second staff approval (two-person rule).

### 10.7 Threat model summary

| Threat | Control |
|---|---|
| Stranger enumerates private tours | Random IDs and codes, 404 for non-members, code rate limits |
| Over-booking through concurrent approvals | Row lock, counter CHECK, unique indexes |
| Removed member keeps reading chat | Revocation event plus 5-second membership cache |
| Harassment through invitations or requests | Opt-in discovery, blocks both ways, daily limits, "don't invite me again" |
| Gender-restricted tour infiltrated | Staff-verified attribute, server-side check on every action |
| Database leak exposes contacts | Envelope encryption, keys outside the database |
| Malicious media | Quarantine bucket, type checks, ClamAV, re-encoding |
| Insider misuse | Break-glass with reason and expiry, audit, organisers informed |
| Replay or double submit | Idempotency keys, CSRF tokens |

---

## 11. API Design

REST under `/api/v1`, documented by FastAPI's OpenAPI. Error bodies use the existing `{code, message, details}` form.

| Method and path | Purpose | Notes |
|---|---|---|
| `GET /me/tours` | Dashboard data | One call returns all dashboard modules |
| `PUT /me/travel-preferences` | Save preferences | |
| `PUT /me/discovery` | Opt in or out of Find People | |
| `POST /tours` | Create a draft | |
| `PATCH /tours/{publicId}` | Edit | `If-Match` version |
| `POST /tours/{publicId}/publish` | Publish | Turnstile |
| `POST /tours/{publicId}/cancel` | Cancel | Reason |
| `POST /tours/{publicId}/recruitment` | Pause, close, reopen | |
| `POST /tours/{publicId}/code/regenerate` | New code | |
| `GET /tours/search` | Find Tours | Filters as query params, cursor paging, score with reasons |
| `GET /tours/by-code/{code}` | Summary from a code | Rate limited |
| `POST /tours/{publicId}/requests` | Request to join | Idempotency key |
| `POST /tours/{publicId}/requests/{id}/approve` | Approve | Transaction 6.1 |
| `POST /tours/{publicId}/requests/{id}/decline` | Decline | Reason code |
| `DELETE /me/requests/{id}` | Withdraw | |
| `GET /people/search` | Find People | Opt-in profiles only |
| `POST /tours/{publicId}/invitations` | Invite | |
| `POST /me/invitations/{id}/accept` / `decline` | Answer | |
| `POST /tours/{publicId}/leave`, `POST /tours/{publicId}/members/{id}/remove` | Membership | |
| `GET/PUT /tours/{publicId}/itinerary` | Itinerary | |
| `GET/POST /tours/{publicId}/expenses`, `GET /tours/{publicId}/balances` | Budget | Integer paisa |
| `PUT /tours/{publicId}/safety/me` | Own emergency contact and notes | Encrypted |
| `POST /tours/{publicId}/checkins`, `POST /tours/{publicId}/sos` | Safety | |
| `GET /tours/{publicId}/messages?after_seq=` | Chat history | REST fallback |
| `WS /realtime` | Chat and live events | Section 8 |
| `/admin/tours/*` | Tour Operations | Staff only |

**Search query.** Find Tours is one SQL query: hard filters in `WHERE` (eligibility, status, dates, blocks via `NOT EXISTS`), then the score computed in SQL from the user's preferences (date overlap with `daterange` operators, budget overlap with `int4range`, array overlap for destinations and activities), ordered by score, with keyset pagination. The reasons are computed from the same columns, so the explanation always matches the score. A covering index on `(lifecycle, recruitment, start_date)` keeps it under 100 ms for 50,000 open tours.

---

## 12. Client Architecture

- **Routes** under `/tours/*` are lazy-loaded chunks so the main guide stays small.
- **State:** TanStack Query for server data; live events from the WebSocket/SSE update the query cache directly.
- **Offline:** the service worker caches the app shell and the dashboard response; writes made offline (chat, expenses, check-in answers) go to an IndexedDB outbox with idempotency keys and replay on reconnect.
- **Forms:** the creation wizard saves a draft to the server at each step and to IndexedDB on every change.
- **Internationalisation:** i18next with Bangla and English; numbers and dates shown in the chosen language, stored in UTC and Asia/Dhaka dates.
- **Accessibility:** WCAG 2.2 AA; chat is a live region with proper focus handling; colour is never the only status signal (badges have text).
- **Performance budget:** under 170 KB of JavaScript (gzip) for the first TourMate screen on a mid-range Android phone over 3G; Lighthouse PWA and performance checks in CI.

---

## 13. Notifications

Every user-facing event in spec 15 is a registry entry in the existing notifications module (template, channels, digest rule, mute category). The outbox relay turns events into notification rows; delivery to open apps uses Redis pub/sub (replacing the 2-second DB poll); email uses the existing provider with daily digests for request activity. SOS uses every channel and bypasses mutes.

---

## 14. Observability and Operations

| Signal | Tool | Alerts |
|---|---|---|
| Errors | Sentry | New error types; error rate over 1% |
| Traces | OpenTelemetry → Grafana Cloud | p95 API over 500 ms; search over 300 ms |
| Business metrics | Prometheus metrics endpoint, ops dashboard panels | Tours published, confirmations, cancellations by reason, request approval time, At Risk count |
| Realtime | Gateway metrics | Connections, messages per second, fan-out lag over 2 s, reconnect storms |
| Jobs | Scheduler metrics | Job lag over 5 minutes; repeated failures |
| Safety | Ops panel | Any SOS raised (page the on-call moderator) |
| Abuse | Ops panel | Code-guessing and mass-request signals |

New panels plug into the existing `ops/` dashboard registry. Backups: Supabase daily backups plus point-in-time recovery when on a paid plan; a restore drill every 6 months.

---

## 15. Testing Strategy

| Layer | Tools | What it proves |
|---|---|---|
| Unit | pytest | Score formula, settlement algorithm (sum to zero), eligibility, permission matrix |
| State machine | Hypothesis stateful tests | No sequence of actions reaches a state not allowed in spec 7 |
| Database | pytest + Testcontainers Postgres | Constraints, partial unique indexes, `confirmed_at` trigger, RLS denies |
| Concurrency | Threaded tests on real Postgres | AC-07: 20 parallel approvals, 5 seats, one confirmation |
| API contract | Schemathesis on OpenAPI | Every endpoint handles bad input without 500s |
| End to end | Playwright (mobile viewport) | Each acceptance criterion AC-01 to AC-19, including offline chat with network emulation |
| Load | k6 | 1,000 chat connections, 50 messages per second, search at 50 requests per second with p95 under 300 ms |
| Security | OWASP ZAP baseline, Bandit, pip-audit, npm audit, gitleaks | No high findings before release |

CI runs unit, database and API tests on every push; E2E and load tests on the release branch.

---

## 16. Deployment and Rollout

1. **Migrations** with Alembic, written to be backward compatible (expand, then contract), so the API can roll forward and back.
2. **Feature flags:** `tours_core` (P0), `tours_chat`, `tours_people`, `tours_safety`, `tours_budget` (P1), `tours_media` (P2). They control rollout only: each is turned on in staging first, then for staff test accounts, then for everyone.
3. **Environments:** local (Docker Compose with Postgres, Redis, Mailpit, MinIO for S3), staging (separate Supabase project), production.
4. **Release checklist:** migration dry run on a staging copy; acceptance suite green; Sentry release created; rollback tested.

---

## 17. Scaling Plan

| Area | Launch | 10× | 100× |
|---|---|---|---|
| API | 1 container | 2 to 4 `web` containers | Autoscaled; read replica for search |
| Realtime | Same process | Separate `realtime` service | Ably or NATS fan-out |
| Database | Supabase free/pro | Pro, PgBouncer, tuned indexes | Larger instance, read replicas, chat partitions moved to cheaper storage after archive |
| Search | Postgres SQL | Materialised "open tours" view refreshed on events | Meilisearch/Typesense fed from the outbox |
| Media | Supabase Storage | R2 for chat media | R2 + image CDN |
| Jobs | One scheduler, one worker | Several workers (SKIP LOCKED) | Same, partitioned by tour id |

None of these steps change the data model or the API.

---

## 18. Cost (Launch Estimate)

| Service | Plan | Monthly |
|---|---|---|
| Vercel | Hobby/Pro | 0 to 20 USD |
| Railway/Render API | Starter container | 5 to 10 USD |
| Supabase | Free, or Pro for backups | 0 to 25 USD |
| Upstash Redis | Pay as you go | Under 5 USD |
| Sentry, Grafana Cloud | Free tiers | 0 |
| Cloudflare R2 (P2 media) | Pay as you go | Under 5 USD |

---

## 19. Consistency With Existing Decisions

| Existing decision | How this design respects it |
|---|---|
| Postgres is the only system of record | All data in Postgres; Redis only for pub/sub, limits and cache |
| API proxies Supabase Auth; browser never calls Supabase | Same for REST and WebSocket; storage via signed URLs from the API |
| RLS on, no anon grants | All new tables, with deny tests |
| Alembic only | All schema here ships as Alembic migrations |
| Append-only `audit_events`, shared outbox | Used for every state change and privileged read |
| 404 for non-staff, 403 for lower role, 409 stale, 422 `TRANSITION_NOT_ALLOWED` | Same codes, extended to tour membership |
| SRS C3 (no payments), C8 (no payment data) | Budget is tracking only; no payment fields. The no-NID part of C8 and Review.md A3 are superseded by the 6 Nov decision: identity documents are reviewed, then only the last 4 digits and a keyed hash are kept (sign-up form, section 16) |
| Community.md has no real-time chat | Chat exists only inside confirmed tours, as Community.md assigns group tours to XFR-03 |
| Proposal excludes chat and group tours | Superseded by the owner's 6 Nov decision (spec Q6): the full system is in scope |

---

## 20. Decisions Applied

The owner answered spec section 18 on 6 Nov 2026. Effects on this design:

- **Q1, Q3:** eligibility reads only `verification_attributes`, set by the moderator's approval in the verification application. Phone and document hashes give one account per person.
- **Q2:** every join goes through the approval transaction in 6.1, or through an accepted direct invitation. No auto-approval path is built.
- **Q4, Q5:** the scheduler jobs in section 7 and the 18+ gate in 10.2.
- **Q6:** the whole design is built. P0 to P3 sets the order, and feature flags (section 16) only control rollout, not scope.
