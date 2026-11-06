# Verified Users Interface: Tours and TourMates

**Execution:** Step 12 of `Features/Execution.md` (XFR-03, "Tourmate groups and join-request management"). This document is the feature specification for that step and replaces the planned `Features/Tourmates.md`.
**Companion:** `Features/Verified Users Interface Architechture.md` describes how every feature here is built, secured and scaled.
**Verification:** `Features/Verified user sign-up form.md` defines how a Member becomes a Verified Member.
**Depends on:** R04 accounts and sessions (Supabase Auth, proxied by the API); Verified Member verification (Review.md 2.3); moderation and the staff app (Moderation-Dashboard-Specification.md); notifications and the outbox (Notification-Documentation.md); the shared media pipeline (Review.md 8); `can(actor, action, resource)` (Review.md 2.2); blocking and reporting (Community.md).
**Source:** the owner's "Final Product Specification: Verified User & TourMate System" (6 Nov 2026). Where this document differs from that draft, section 17 says what changed and why.

---

## 1. Purpose and Product Identity

Abhijatri helps people in Bangladesh plan trips with verified information. The TourMate system adds the missing piece: **finding trustworthy people to travel with, and organising the trip together in one place.**

The promise to the user, in one line: *"Find verified travel companions, agree on a plan, and travel together safely."*

Three rules shape every feature below.

1. **Only verified people.** Every person who creates, joins or is shown in a tour is a Verified Member, so a traveller always knows the others passed an identity check by staff.
2. **A tour is real only when enough people commit.** A tour is confirmed automatically the moment it reaches its minimum number of approved members. Nobody has to press a button, and nobody is left guessing.
3. **Private until confirmed.** People talk inside the tour only after it is confirmed. Before that, the only contact is the join request and the organiser's answer. This keeps strangers from using recruitment as a messaging channel.

### 1.1 What Abhijatri serves (summary)

| # | Service | What the verified user gets | Priority |
|---|---|---|---|
| S1 | Verified dashboard | One home page for their tours, requests, invitations and alerts | P0 |
| S2 | Create a tour | A guided form that publishes a recruiting tour with rules | P0 |
| S3 | Access policies | Control over who may request to join | P0 |
| S4 | Automatic confirmation | The tour confirms itself at the minimum member count | P0 |
| S5 | Join requests and approval | A fair, auditable request flow approved by the organisers | P0 |
| S6 | Find Tours | Search and filter of recruiting tours, with a compatibility score | P0 |
| S7 | Tour ID, tour code and private link | A shareable code and link for invite-only tours | P0 |
| S8 | Tour workspace | Overview, Tourmates, Itinerary, Discussion, Budget and Safety in one place | P0 (Overview, Tourmates) / P1 (rest) |
| S9 | Native tour chat | Group chat for confirmed tours, with an offline queue | P1 |
| S10 | Find People and direct invitations | Opt-in discovery of compatible travellers, and invitations | P1 |
| S11 | Budget tracking | Shared expense list and fair split (no money moves) | P1 |
| S12 | Safety module | Emergency contacts, meeting points, check-ins and SOS info | P1 |
| S13 | Tour Operations (staff) | Moderation of tours, requests, chat reports and safety cases | P0 (reports) / P1 (full) |
| S14 | Media in chat | Photos and short videos, with resumable upload | P2 |
| S15 | Post-tour | Completion, reviews of the trip, and tourmate feedback | P2 |
| S16 | Advanced matching | Learned weights, saved searches, smart suggestions | P3 |

Priorities are defined in section 19.

---

## 2. Who Can Do What

### 2.1 Account levels

| Level | Meaning | TourMate access |
|---|---|---|
| Guest | Not signed in | Sees a marketing page only: "Verified members can find tourmates." No tour data. |
| Member | Email verified | Sees an explanation and a "Get verified" button. No tour data. |
| Verified Member | Identity approved by a moderator through the verification application (`Verified user sign-up form.md`) and aged 18 or over | Full access to everything in this document |
| Restricted Verified Member | A Verified Member with a TourMate restriction from staff | Can see their existing tours; cannot create, request, invite or post until the restriction ends |

A Verified Member whose verification is revoked loses TourMate access at once. Their memberships are kept as **Inactive** so organisers can see a seat opened, and the tour recalculates its confirmation state (section 7.4).

### 2.2 Roles inside a tour

| Role | How someone gets it | Number per tour |
|---|---|---|
| Creator (owner) | Created the tour | Exactly 1. Can be transferred to a co-organizer. |
| Co-organizer | Appointed by the creator from approved tourmates | 0 to 3 |
| Tourmate | Request approved, or invitation accepted | Up to capacity |
| Former tourmate | Left, removed, or inactive | Not counted |

### 2.3 Staff roles

Moderators and superadmins use the existing staff dashboard (Tour Operations, section 16). Staff have **no** standing access to private tour content. They see it only through a report, or through time-limited break-glass access with a stated reason (section 13.4).

---

## 3. The Verified User Dashboard (S1)

The dashboard is the verified user's home page in the TourMate area (`/tours`). It is one screen with these modules, in this order on a phone.

| # | Module | Shows | Actions |
|---|---|---|---|
| D1 | Alerts strip | At Risk tours, tours starting within 48 hours, unanswered requests to the user's tours, safety check-ins due | Open the item |
| D2 | My tours | Tours the user created or joined, grouped as Recruiting, Confirmed (including "Upcoming" and "Starts in N days"), Ongoing, Completed. Each card shows the status badge, dates, members `approved / minimum / maximum` and unread chat count. | Open workspace |
| D3 | Requests | Two tabs: **Sent** (the user's requests and their state) and **To review** (pending requests to tours the user organises) | Withdraw, approve, decline |
| D4 | Invitations | Invitations received, with expiry | Accept, decline, view tour summary |
| D5 | Find Tours (shortcut) | Three best compatible recruiting tours | Open Find Tours |
| D6 | Find People (shortcut) | Shown only if the user opted in to discovery (section 10.1) | Open Find People |
| D7 | Create tour | Primary button | Start the creation form |
| D8 | My travel preferences | Completion meter for the preference profile used by matching | Edit preferences |
| D9 | Drafts | Unpublished tours | Continue, delete |

**Empty states.** A new verified user with no tours sees D7, D8 and D5 first, with the text "Tell us how you like to travel, and we'll show tours that fit."

**Counters.** All counts (unread, pending requests) come from the server and update live through the notification stream. They never depend on the browser's clock.

---

## 4. Travel Preference Profile

Matching (section 9) needs a small, structured profile. It is separate from the public profile and only the user can see it in full.

| Field | Type | Values | Used for |
|---|---|---|---|
| Usual travel dates | Optional date ranges or "flexible" | Up to 3 ranges | Date overlap |
| Budget per person per day | Range in BDT | Min and max | Budget fit |
| Preferred destinations | Up to 10 | Published destinations and regions | Destination overlap |
| Travel style | Choice | Budget, Standard, Comfort | Style match |
| Pace | Choice | Relaxed, Balanced, Packed | Style match |
| Activities | Multi-select | Hiking, Beach, Heritage, Food, Photography, Wildlife, Boating, Camping, Religious sites, City | Activity overlap |
| Languages | Multi-select | Bangla, English, others | Shown, not scored |
| Smoking | Choice | No, Outdoors only, Yes | Hard filter if the tour says "No smoking" |
| Discoverable in Find People | Switch | Off by default | Section 10 |

The profile is optional for Find Tours (the score then uses only what is known, and says so) and required before a user can turn on Find People discovery.

---

## 5. Creating a Tour (S2)

### 5.1 Step-by-step flow

The form is a five-step wizard. Each step saves a draft, so a user who loses connection loses nothing.

**Step 1. Basics**
1. Title (8 to 80 characters).
2. Destinations: one or more published destinations, in visiting order. Free-text places are allowed as itinerary stops later, not as the main destination, so discovery and safety advisories always link to a real destination.
3. Short description (up to 1,000 characters).
4. Cover image (optional, from the shared media pipeline).

**Step 2. Dates and meeting**
1. Start date and end date (Asia/Dhaka). The start must be at least 3 days after publishing, so there is time to recruit. The tour may last at most 30 days.
2. **Recruitment deadline** (required). It must be before the start date, and at least 24 hours before it. Default: 3 days before the start.
3. Departure city and an approximate meeting area. The exact meeting point is entered later in the Safety module and shown only to confirmed tourmates.

**Step 3. Group size**
1. Minimum members, counting the creator. Allowed range 2 to 30. Default 3.
2. Maximum members, counting the creator. Allowed range: the minimum to 30. Default 8.
3. The form explains: "Your tour is confirmed automatically when it has N approved members, including you."

**Step 4. Who can join**
1. Access policy (section 6). One choice.
2. Manual approval is always on: every request is reviewed by the creator or a co-organizer (decision Q2).
3. Optional join question shown to requesters, such as "What's your hiking experience?" (up to 200 characters).
4. Tour rules: No smoking, No alcohol, Quiet hours, custom rules (up to 5 lines).

**Step 5. Plan and budget**
1. Estimated budget per person, as a range in BDT, with what it includes (transport, stay, food, entry fees). This is an estimate, not a price; Abhijatri does not take payments.
2. Travel style, pace and activities (same lists as section 4).
3. Transport mode (Bus, Train, Launch, Private car, Mixed).
4. Optional first itinerary outline (can be filled after confirmation).

**Review and publish.** The final screen shows the tour as others will see it, plus the safety advisory currently in force for each destination (from the existing advisories). The creator ticks "I will share accurate information and follow the community rules", then publishes. The tour becomes **Recruiting**.

### 5.2 Rules on creation

- A Verified Member may have at most **3 tours in Recruiting or Confirmed** at a time, and at most **5 drafts**. Both are configuration values.
- Two tours by the same creator may not overlap in dates.
- Text fields pass the same content checks as community posts (blocked words, links, phone numbers in the description are removed and the creator is told to use the workspace instead).
- After publishing, the creator can edit the description, rules, budget and itinerary freely. Changes to **dates, destinations, size limits or access policy** follow section 7.6.

---

## 6. Access Policies (S3)

| Policy | Who may request | Shown in Find Tours | How eligibility is checked |
|---|---|---|---|
| Open | Any Verified Member | Yes | Verified status |
| Students only | Verified Members with a current student attribute | Yes, only to eligible users | Student attribute and end date set by the moderator from the student ID (Q3; sign-up form Step 5) |
| Family groups | Verified Members travelling with family | Yes | The requester lists named companions (section 8.3) |
| Women only | Verified Members whose verified gender is Female | Yes, only to eligible users | Gender attribute set by the moderator from the identity document (Q3; sign-up form Step 2) |
| Men only | Verified Members whose verified gender is Male | Yes, only to eligible users | Same as above |
| Invite only | Only people with the tour code, link or a direct invitation | **No** | The code or invitation token |

Rules:

1. The creator must satisfy their own tour's policy (a man cannot create a Women-only tour).
2. Eligibility is checked by the server on every request, approval and invitation. Hiding a tour in the interface is a convenience, never the security control.
3. A user who does not meet a tour's policy never sees it in Find Tours. If they open its link, they see "This tour isn't open to you" and no details beyond the title and dates.
4. A policy can be made **stricter** only while the tour has no approved tourmates other than organisers. It can always be made **looser**. Existing members are never removed by a policy change.
5. Every join request needs approval by the creator or a co-organizer (Q2). Invite only does not skip approval for code or link requests; a **direct invitation** from an organiser counts as approval in advance (section 11).

---

## 7. Tour Statuses and Confirmation (S4)

A tour has **two independent statuses** and **two flags**. Keeping them separate removes the conflicts in the original draft (section 17).

### 7.1 Lifecycle status (one at a time)

| Status | Meaning | Who sees it |
|---|---|---|
| Draft | Being written, not published | Creator only |
| Recruiting | Published, collecting members, below the minimum | Eligible users in Find Tours (except Invite only) |
| Confirmed | Reached the minimum; the tour will happen | Members; still listed in Find Tours if seats remain and recruitment is Open |
| Ongoing | Between the start and end dates | Members |
| Completed | The end date has passed | Members |
| Cancelled | Ended early by the creator, by the system, or by staff | Members (with the reason) |
| Archived | Closed and read-only, 90 days after Completed or Cancelled | Members (read only) |

**Upcoming is not a separate status.** "Upcoming" and "Starts in 3 days" are display labels shown on Confirmed tours whose start date is near. This avoids two statuses meaning the same thing.

**Allowed transitions** (anything else is refused with `TRANSITION_NOT_ALLOWED`):

```
Draft ──publish──▶ Recruiting ──minimum reached (automatic)──▶ Confirmed
Recruiting ──deadline passed below minimum (automatic)──▶ Cancelled
Recruiting / Confirmed ──creator cancels / staff cancels──▶ Cancelled
Confirmed ──start date reached (automatic)──▶ Ongoing
Ongoing ──end date passed (automatic)──▶ Completed
Completed / Cancelled ──90 days (automatic)──▶ Archived
Draft ──creator deletes──▶ (removed)
```

A Confirmed tour **never goes back to Recruiting**, because chat, safety data and plans already exist. If it falls below the minimum, it gets the At Risk flag instead (section 7.4).

### 7.2 Recruitment status (one at a time, only while Recruiting or Confirmed)

| Status | Meaning | Set by |
|---|---|---|
| Open | Accepting requests | Default; the organiser |
| Paused | Temporarily not accepting requests; pending requests stay | The organiser |
| Full | Approved members equal the maximum | System, automatically |
| Closed | The organiser stopped recruitment | The organiser |
| Expired | The recruitment deadline passed | System, automatically |

Full is reversed automatically to Open (or the previous organiser choice) when a seat opens before the deadline. Expired and the lifecycle states after Confirmed are final for recruitment. When a tour becomes Cancelled, Ongoing, Completed or Archived, recruitment is shown as Closed.

### 7.3 Flags (can be combined with a lifecycle status)

| Flag | Meaning | Effect |
|---|---|---|
| At Risk | A Confirmed tour has fewer approved members than the minimum | Organisers and members alerted; recruitment reopens if seats and time remain |
| Suspended | Staff froze the tour during an investigation | Read only for members: no requests, no edits, chat read only. Hidden from discovery. Lifting the suspension returns the tour to exactly where it was. |

### 7.4 Confirmation rules

1. **Automatic confirmation.** The tour becomes Confirmed in the **same database transaction** that approves the member who brings the approved count to the minimum. There is no delay, no separate button, and no race: two organisers approving at the same moment can never confirm twice or exceed the maximum (see the architecture document, section 6).
2. The count includes the creator and co-organizers. Invited people count once they accept. Pending requests never count.
3. At confirmation the system, in that same transaction: records `confirmed_at` (set once, never changed), opens the tour chat, unlocks the Safety and Budget modules, and queues notifications to every member: "Your tour is confirmed."
4. **At Risk.** If a Confirmed tour drops below the minimum (someone leaves, is removed, or loses verification), it stays Confirmed and gets the At Risk flag. The organisers can:
   - recruit again (recruitment reopens automatically if the deadline has not passed);
   - lower the minimum, but never below the current approved count and never below 2;
   - cancel the tour.
5. **At Risk deadline (Q4).** If a tour is still At Risk **24 hours before the start**, it is cancelled automatically, unless an organiser lowers the minimum to the current count. All members get 48-hour and 24-hour warnings before that happens.
6. **Recruitment deadline.** If a Recruiting tour has not reached the minimum by its deadline, it is cancelled automatically with the reason "Not enough tourmates", and members are told. The creator can copy it into a new draft in one tap.

### 7.5 Leaving and removal

| Action | Before confirmation | After confirmation |
|---|---|---|
| A tourmate leaves | Allowed any time; no record shown to others | Allowed until the start date; the tour may become At Risk; others see "N left the tour" |
| Organiser removes a tourmate | Allowed with a reason chosen from a list | Allowed with a reason; the removed person can report the removal to staff |
| The creator leaves | Must transfer ownership to a co-organizer or cancel | Same |
| Leaving during Ongoing | Allowed; the Safety module asks for a short "I'm safe and leaving" check-out | |

A person who left or was removed cannot request the same tour again unless an organiser invites them.

### 7.6 Changes to key details after people have joined

If an organiser changes the **dates, destinations, minimum or maximum, or access policy** after anyone besides the organisers is approved:

1. Every member is notified with a clear before-and-after view.
2. Members get **72 hours to leave without any mark** against them ("Plan changed" is recorded as the reason).
3. A change of dates must still keep the recruitment deadline at least 24 hours before the new start.
4. The maximum can never be lowered below the current approved count.
5. Dates cannot be changed once the tour is Ongoing.

---

## 8. Joining a Tour (S5)

### 8.1 Step by step for the requester

1. The user opens a tour from Find Tours, a tour code, a private link, or an invitation.
2. They see the **tour summary**: title, destinations, dates, recruitment deadline, budget estimate, style and pace, activities, rules, access policy, current members as `approved / minimum / maximum`, and for each member only their first name, verified badge and travel-style tags. Names of other members are shown only after the requester is approved.
3. They see their **compatibility score** with the tour and why (section 9).
4. They press **Request to join**, answer the join question if there is one, write an optional message (up to 300 characters) and confirm they accept the tour rules.
5. The request is **Pending**. The requester can withdraw it any time before a decision.
6. Organisers are notified. They must answer before the recruitment deadline. A request still pending at the deadline becomes **Expired**, and the requester is told.
7. On **Approved**, the requester becomes a tourmate, sees the other members' names, and the workspace opens (chat only after confirmation). On **Declined**, they see a polite message and an optional reason chosen from a list; the organiser's free text is never shown.

### 8.2 Request rules

- One pending request per user per tour; at most **10 pending requests** per user across all tours; at most **20 new requests per user per day**.
- A user cannot request tours whose dates overlap a tour they are already approved for.
- A user cannot request a tour if they and any approved member have blocked each other. The requester is told only "You can't request this tour"; who blocked whom is never revealed.
- A requester declined by a tour cannot request it again for 7 days.
- Approval is refused if the tour is Full, Paused, Closed, Expired, Suspended or past its deadline, or if the requester is no longer eligible (lost verification, restricted, policy no longer met). The organiser sees the exact reason.

### 8.3 Family group requests

For a **Family groups** tour, a request may include up to 4 **named companions** under 18 (first name, age band, relationship). Companions are not accounts and are not shown to anyone except the organisers and, after confirmation, the tour members. Each companion takes one seat in the count and capacity checks. The requester is responsible for them (Q3). Adult family members must have their own Verified Member accounts and send their own requests (the organiser can approve them together).

### 8.4 Step by step for the organiser

1. **To review** shows each pending request with: first name, verified badge, compatibility score and reasons, answer to the join question, message, number of completed tours on Abhijatri, and whether any current member has reported or blocked them (shown only as "Can't be approved").
2. The organiser presses **Approve** or **Decline**. Both can be undone only by inviting or removing later, never silently.
3. Co-organizers can approve and decline. Every decision records who made it.
4. If approving would make the tour Full, the interface warns that pending requests will be closed automatically, and they are, with the message "The tour filled up."

---

## 9. Compatibility Score

### 9.1 Formula

The score is a whole number from 0 to 100. Each part is between 0 and 1 and is multiplied by its weight.

| Part | Weight | How it is measured |
|---|---|---|
| Dates | 30 | Share of the tour's days that fall inside the user's available ranges. "Flexible" counts as 0.7. |
| Budget | 25 | Overlap of the user's daily budget range with the tour's estimate, divided by the smaller range. 1 if fully inside. |
| Destinations | 20 | 1 if the main destination is a preferred one; 0.6 if it is in a preferred region; 0 otherwise |
| Style | 15 | Average of travel style match (1 same, 0.5 one step apart, 0 two apart) and pace match (same rule) |
| Activities | 10 | Number of shared activities divided by the number of the tour's activities |

**Missing data.** If the user has not filled a part, that part is left out and the remaining weights are scaled up to 100. The card then says "Based on 3 of 5 factors. Add your preferences for a better match." A score is never shown as precise when it is not.

### 9.2 Hard filters (applied before scoring)

A tour is not shown or scored at all if any of these is true: the user is not eligible under its policy; the dates overlap a tour the user is already in; there is a block between the user and any member; the tour's rules conflict with a hard preference (for example the tour allows smoking and the user chose "No smoking" as a must).

### 9.3 Explanation

Every score shows its parts in plain words, for example:

> **82% match.** Dates: fits all 4 days. Budget: ৳2,500 to ৳3,000 a day, inside your range. Destination: Bandarban is on your list. Style: same pace, one step more comfortable. Activities: you share Hiking and Photography.

The weights are shown on a help screen, so users understand why a tour ranks high. The score is advice, not a gate: it never blocks a request.

---

## 10. Find a Tourmate (S6, S10)

Find a Tourmate has two tabs: **Tours** and **People**.

### 10.1 Find Tours

Lists **Recruiting** and **Confirmed-with-open-seats** tours the user is eligible for, excluding Invite only.

| Filter | Values |
|---|---|
| Destination or region | Published destinations |
| Dates | From and to; "Flexible" |
| Budget per person | Range in BDT |
| Group size | Small (up to 5), Medium (6 to 12), Large (13 to 30) |
| Access policy | Policies the user is eligible for |
| Style and pace | Lists from section 4 |
| Activities | Lists from section 4 |
| Status | Recruiting, Confirmed with seats |
| Starts within | 7, 14, 30, 60 days |
| Seats left | At least 1, 2, 4 |
| Departure city | List |

**Sorting:** Best match (default), Starting soonest, Seats left, Newest. Results are paged (20 per page). Each card: title, destinations, dates, budget estimate, members `approved / minimum / maximum`, deadline, match score, policy badge.

**Search by code:** a box at the top accepts a tour code (`ABH-7K92PX`) and opens that tour's summary (section 12).

### 10.2 Find People (opt-in)

Find People lets a verified user find other verified users with similar plans and invite them to a tour.

**Privacy rules (fixes to the draft, section 17):**

1. **Off by default.** A user appears in Find People only after turning on "Let other verified travellers find me". They can turn it off any time and vanish at once.
2. **Coarse information only.** A person card shows first name, verified badge, age band (18 to 24, 25 to 34, 35 to 44, 45+), home division (not city), languages, style, pace, activities, preferred destinations, an approximate travel window ("Mid-December"), and number of completed tours. Never: full name, photo unless they chose to show it, phone, email, exact dates, or current location.
3. **Same eligibility.** A searcher sees only people who could join one of the searcher's own tours, plus people who are discoverable to everyone. Women can choose "Show me only to women", and men "Show me only to men".
4. **Blocks hide both ways.** People who blocked each other never see each other.
5. **No messaging from search.** The only action on a person is **Invite to my tour** (section 11). There are no direct messages, followers or likes, which keeps Abhijatri from becoming a dating or cold-message channel.
6. **Limits.** A user can view at most 100 person cards and send at most 10 invitations a day.

Find People filters: destination, travel window, budget range, style, pace, activities, languages, age band, home division. Sorting: Best match (the same formula, using the person's profile against the searcher's selected tour), Recently active.

---

## 11. Direct Invitations (S10)

1. An organiser opens a person card (or enters a tour member's username shared with them offline) and presses **Invite to my tour**, choosing one of their Recruiting or Confirmed tours with seats.
2. The server checks: the invitee is a Verified Member, eligible under the policy, not blocked either way, not already in or requesting the tour, has no date overlap, and has not declined an invitation to this tour before.
3. The invitee gets a notification and an entry in Invitations. The invitation shows the tour summary and the match score. It expires after **7 days** or at the recruitment deadline, whichever is first.
4. **Accept** makes the invitee an approved tourmate at once (the organiser's invitation counts as approval). Capacity is re-checked at the moment of acceptance; if the tour filled up, the invitee is told and the invitation closes.
5. **Decline** closes it. The organiser sees only "Declined". The same organiser cannot invite the same person to the same tour again.
6. An invitee can mark "Don't invite me again" for that organiser, which acts like a soft block for invitations.
7. Limits: an organiser can have at most **2 × (seats left)** pending invitations per tour, and 10 new invitations per day.

---

## 12. Tour Identity: ID, Code and Private Link (S7)

| Identifier | Example | Purpose | Who sees it |
|---|---|---|---|
| Internal ID | UUID | Database and API only | Never shown |
| Public tour ID | `T-2026-7Q3MK` | Reference in support, reports and the staff app | Members and staff |
| Tour code | `ABH-7K92PX` | Typed or shared to find an Invite only tour | Organisers share it |
| Private link | `https://abhijatri.app/t/ABH-7K92PX` | Opens the tour summary | Organisers share it |

**Fix to the draft:** the public ID is **not sequential** (`T-2026-000142` would reveal how many tours exist and invite guessing). It is the year plus 5 random characters from an unambiguous alphabet (no 0/O, 1/I/L).

**Tour code rules:**

1. Six random characters from a 31-character unambiguous alphabet, giving about 887 million combinations. Codes are unique among active tours.
2. A code opens only the **tour summary** and a **Request to join** button. A request made through a code still needs approval. The code is not a password that grants membership.
3. Organisers can **regenerate** the code at any time, which makes the old code and link stop working at once.
4. Code lookups are limited to **10 failed attempts per user per hour**. Repeated failures are logged and shown to staff as possible guessing.
5. A code stops working when the tour leaves Recruiting/Confirmed, or when recruitment is Closed or Expired.
6. Only signed-in Verified Members can use codes or links. Anyone else is asked to sign in and get verified; the tour's existence is not confirmed to them.

---

## 13. The Tour Workspace (S8)

Every approved member of a tour has a workspace at `/tours/{publicId}`. It has six tabs.

### 13.1 Modules

| Tab | Available from | Contents |
|---|---|---|
| Overview | Approval | Status and flags, dates, countdown, destinations with current advisories, members count, rules, key announcements pinned by organisers, recent changes log |
| Tourmates | Approval | List of members with role, verified badge, joined date; pending requests and invitations (organisers only); leave button; report a member |
| Itinerary | Approval (view); organisers edit | Day-by-day plan: stops, times, transport legs, stays, notes. Each stop can link to a published destination or place. Members can suggest changes, which organisers accept or reject. |
| Discussion (chat) | Confirmation | Native group chat (section 14) |
| Budget | Confirmation | Planned budget, shared expense list, split calculation (section 13.3) |
| Safety | Confirmation | Emergency info, meeting points, check-ins (section 13.4) |

Before confirmation, the Discussion, Budget and Safety tabs show a lock and the line "Opens when the tour is confirmed (N more tourmates needed)."

### 13.2 Permissions

| Action | Creator | Co-organizer | Tourmate | Staff |
|---|---|---|---|---|
| Edit basics, rules, itinerary | Yes | Yes | Suggest only | No |
| Change dates, destinations, size, policy | Yes | No | No | No |
| Approve or decline requests | Yes | Yes | No | No |
| Send invitations | Yes | Yes | No | No |
| Remove a tourmate | Yes | Yes, but not another organiser | No | Yes (moderation) |
| Appoint or remove co-organizers | Yes | No | No | No |
| Transfer ownership | Yes | No | No | No |
| Pause, close or reopen recruitment | Yes | Yes | No | No |
| Regenerate tour code | Yes | Yes | No | No |
| Cancel the tour | Yes | No | No | Yes |
| Pin announcements in chat | Yes | Yes | No | No |
| Delete any chat message | Yes | Yes | Own only | Yes (moderation) |
| Add expenses | Yes | Yes | Yes | No |
| Edit Safety meeting points | Yes | Yes | No | No |
| Add own emergency contact | Yes | Yes | Yes | No |
| See others' emergency contacts | Only during Ongoing, or on SOS | Same | No | Break-glass only |
| Suspend the tour | No | No | No | Yes |

### 13.3 Budget (S11)

1. The **planned budget** is the creator's estimate split by category.
2. Any member can add an **expense**: description, amount in BDT, category, who paid, and who shares it (all, or chosen members). Receipts can be attached as images.
3. The **balance view** shows who owes whom, using the fewest possible transfers.
4. Members mark a balance as **Settled** themselves after paying outside Abhijatri (bKash, cash).
5. **Abhijatri never moves, holds or requests money**, and never stores payment account numbers (SRS C3, C8). The screen says so.
6. Expenses can be edited by their author until settled; every change is kept in a history visible to members.

### 13.4 Safety (S12)

1. **Emergency contact** (each member, required before the start date): a name, relationship and phone number. Stored encrypted. Visible to organisers only during the Ongoing period or when an SOS is raised.
2. **Meeting points** with time and map link, set by organisers, shown only to members.
3. **Medical notes** (optional, each member): free text such as allergies, visible to organisers only during Ongoing.
4. **Check-ins:** organisers can request a check-in ("Everyone reached the hotel?"); each member taps "I'm OK". Members who do not answer within 30 minutes are highlighted to organisers.
5. **SOS screen:** national emergency number 999, the nearest police, hospital and tourist police contacts for the destination (from the guide data), the tour's meeting point, and a button that sends an urgent alert to all members and organisers. Abhijatri does not track location continuously.
6. **Destination advisories** in force are shown at the top.
7. Safety data (contacts, medical notes) is deleted **30 days after the tour ends**.

---

## 14. Native Tour Chat (S9)

### 14.1 Rules

1. Chat opens **only when the tour is Confirmed**, and only for approved members. Pending requesters and invitees cannot read it.
2. A member who leaves or is removed loses access at once. Messages they sent stay, labelled with their first name.
3. Chat is **read only** when the tour is Suspended, Cancelled or Completed, and for 90 days after it ends. It is deleted when the tour is Archived, except messages held for an open report.
4. **Message types:** text (up to 2,000 characters), replies to a message, organiser announcements (pinned), system messages ("Rafi joined", "Dates changed"), polls (P2), and photos and short videos (P2, section 14.3).
5. Members can **edit** their own text messages for 15 minutes and **delete** their own messages any time (shown as "Message deleted").
6. **Report** any message to staff. Reporting attaches that message and the 20 messages around it to the report.
7. **Mute** a tour's notifications. **Block** a member: their messages are collapsed for the blocker, and the blocker may leave without a mark.
8. Read receipts are shown as a count ("Seen by 4"), not names, to avoid pressure.
9. Rate limit: 30 messages a minute per member; links are shown as plain text with a warning on unknown sites.

### 14.2 Offline queue

Travellers often lose signal in the hills and on launches. The chat works offline:

1. A message written offline is saved on the phone and shown with a clock icon ("Waiting to send").
2. When the connection returns, queued messages are sent in order. Each carries a client-generated ID, so a message sent twice by a flaky network appears once.
3. The chat keeps the last 500 messages of each tour on the phone for reading offline, and fetches missed messages on reconnect from the last one it saw.
4. If a message cannot be sent within 24 hours or the user lost access, it is shown as "Not sent" with options to retry or delete.

### 14.3 Media (P2)

Members can send photos (up to 10 MB) and short videos (up to 60 seconds, 50 MB). Uploads resume after a lost connection. Media is checked and resized before others can see it; other members see a placeholder until it is ready. In low-data mode, media loads only when tapped.

### 14.4 WhatsApp or Messenger link (optional)

An organiser may add an external group link in the Overview after confirmation. The interface warns: "Members will see each other's phone numbers in WhatsApp. Abhijatri can't moderate or protect messages there." The link is visible to members only and can be removed. Native chat stays the official channel for safety and reports.

---

## 15. Notifications

All are delivered in the app (live stream and the notification list) and, where marked, by email. Users can mute categories in settings except safety.

| Event | Who | Email |
|---|---|---|
| New join request | Organisers | Daily digest |
| Request approved / declined / expired | Requester | Yes (approved) |
| Invitation received / accepted / declined | Invitee / organisers | Yes (received) |
| Tour confirmed | All members | Yes |
| Tour At Risk; 48 h and 24 h cancellation warnings | All members | Yes |
| Tour cancelled (any reason) | All members and pending requesters | Yes |
| Key details changed (section 7.6) | All members | Yes |
| Tour starts tomorrow | All members | Yes |
| Emergency contact missing (3 days before start) | That member | Yes |
| Check-in requested; SOS | All members | Push and email for SOS |
| New chat message, mentions | Members (not muted) | No |
| Tour suspended or restored | Organisers and members | Yes |

---

## 16. Tour Operations: Moderation (S13)

Tour Operations is part of the **existing staff dashboard** (`staff/` on admin.<domain>, `Docs/Moderation-Dashboard-Specification.md`). It reuses that dashboard's Queue, leases, decision pipeline, reason codes, enforcement cases, sanctions, appeals, audit and notifications. Nothing here is a second moderation system.

### 16.1 Screens

| Tab | Change | Contents | Role |
|---|---|---|---|
| Queue (existing) | New task types `tour_report`, `chat_report`, `tour_safety` | Reports about tours, members, requests, invitations and chat messages, with the attached context; SOS and safety reports sort first | Moderator |
| Tours (new) | New tab | Search by public ID, code or creator; filter by status and flags; tour summary, members, change history | Moderator |
| Enforcement (existing) | Subjects extended to tours, tour members and chat messages; new sanction kind `tourmate_restriction` | Suspend or cancel tours, remove members, hide messages, restrict users | Moderator (restrictions up to 30 days), Superadmin (longer, permanent, cancel Confirmed tours) |
| Monitoring (existing) | New counters | Abuse signals (code guessing, mass requests or invitations, repeated removals), open safety cases, At Risk tours | Moderator |
| Settings (superadmin) | New section | Limits in this document (caps, rates, deadlines) | Superadmin |

Every decision follows the staff dashboard rules: claim before deciding, `expected_version`, `Idempotency-Key`, reason code, no deciding one's own tour, escalated items for superadmins only.

### 16.2 Actions

All actions are enforcement cases (moderation spec 11.1), so they are audited, notify the people affected, and can be **appealed within 30 days** to an independent reviewer.

| Action | Effect | Requires |
|---|---|---|
| Suspend tour | Freeze as in section 7.3 | Reason code |
| Restore tour | `restore` on the case; returns the tour to the earlier state | Reason code |
| Cancel tour | Lifecycle Cancelled, members told "Cancelled by Abhijatri" | Reason code; superadmin for Confirmed tours |
| Remove member | Removes a tourmate | Reason code |
| Hide message | Message replaced with "Removed by a moderator" | Linked report |
| Restrict user | `tourmate_restriction` sanction with an end date; blocks TourMate actions | Reason code; user notified |
| Revoke verification | Account enforcement case (sign-up form section 5); TourMate effects as in section 2.1 | Superadmin |

### 16.3 Break-glass access

Staff cannot read a tour's chat, Safety data or expenses as a routine. To read them without a report, a moderator requests **break-glass access** with a written reason; it lasts **60 minutes**, is recorded in the audit log, is shown in the superadmin's daily review, and the tour's organisers are told afterwards ("Abhijatri staff reviewed this tour for safety"), unless that would endanger someone. An SOS automatically grants the safety queue access to that tour's Safety module for 24 hours.

---

## 17. Issues Found in the Draft and How They Are Fixed

| # | Issue in the draft | Fix in this plan |
|---|---|---|
| F1 | "Upcoming" and "Confirmed" mean the same thing | Upcoming is a label on Confirmed tours, not a status (7.1) |
| F2 | "Suspended" as a lifecycle status loses where the tour was | Suspended is a flag; restore returns to the exact state (7.3) |
| F3 | "At Risk" mixed into statuses, and no rule for what happens next | At Risk is a flag with organiser options and an automatic deadline (7.4) |
| F4 | "Expired" recruitment had no deadline to expire against | Required recruitment deadline (5.1, 7.2) |
| F5 | Confirmation could race when two organisers approve at once | Confirmation happens in the same locked transaction as the approval (7.4; architecture 6) |
| F6 | Sequential tour ID `T-2026-000142` reveals volume and invites guessing | Random public ID; UUID inside (12) |
| F7 | A tour code could be treated as a password to join | Code opens the summary only; request still needs approval; rate limited; regenerable (12) |
| F8 | Invite only tours could appear in discovery | Never listed (6, 10.1) |
| F9 | Find People exposed every verified user | Opt-in, coarse data, no messaging, block both ways (10.2) |
| F10 | Women-only and Men-only relied on self-declared gender | Attribute set by the moderator from the identity document (6; Q3) |
| F11 | Budget suggested Abhijatri handles money | Tracking and splitting only; no money movement (13.3; SRS C3) |
| F12 | Emergency contacts with no protection or deletion rule | Encrypted, time-limited visibility, deleted after 30 days (13.4) |
| F13 | WhatsApp link with no privacy warning | Optional, members only, clear warning (14.4) |
| F14 | No rule for changing dates after people joined | Notice and 72-hour no-penalty leave window (7.6) |
| F15 | No minimum and maximum bounds | 2 to 30, with defaults (5.1) |
| F16 | Staff could read private tours freely | Report-based or break-glass access with audit (16.3) |
| F17 | No age rule | 18+ only (Q5) |
| F18 | No spam limits on requests and invitations | Limits in 8.2 and 11 |
| F19 | Scope conflict: the Proposal excluded chat and group tours, Execution.md lists XFR-03 | The full system is in scope (Q6); older scope lines are superseded |
| F20 | No definition of how a person becomes verified, or where gender and student status come from | Verification application with document, selfie and phone, reviewed by moderators (`Verified user sign-up form.md`) |

---

## 18. Owner Decisions (6 Nov 2026)

All six questions are decided. The document above follows these answers.

| # | Question | Decision |
|---|---|---|
| Q1 | What does "verified user" mean? | A Verified Member: email verification only proves the inbox; a moderator must approve the person's identity through the verification application (`Features/Verified user sign-up form.md`). Email-only Members get no TourMate access. |
| Q2 | Should every join request need a human approval? | Yes. Every request is approved by the creator or a co-organizer, because people are travelling with strangers. A direct invitation counts as approval in advance. Auto-approval is not offered. |
| Q3 | How are gender, student and family attributes established? | Gender and student status are set by the moderator from the identity and student documents in the verification application. "Family group" means named under-18 companions on the requester's request; adults join with their own accounts. |
| Q4 | What happens when the minimum is not reached? | Required recruitment deadline; auto-cancel if not reached. A tour still At Risk 24 h before the start auto-cancels unless the minimum is lowered (never below the current count or 2). |
| Q5 | Minimum age? | 18+ to create, join or appear in discovery. |
| Q6 | What is built? | The full production platform described here. P0 to P3 (section 19) is the build order, not a scope cut. Earlier scope exclusions of chat and group tours (Proposal, Review.md 12.4) are superseded and should be updated to match. |

**Gender (owner, 6 Nov).** Verified gender is Female, Male or Third gender, as on the identity document. There is no separate Third-gender-only policy. Women-only tours accept verified Female members and Men-only tours accept verified Male members; every other policy is open to all three.

---

## 19. Priorities

| Priority | Meaning | Contents |
|---|---|---|
| **P0** | Required for the feature to exist | Access gate (2.1); preference profile basics (4); tour creation (5); access policies (6); statuses, flags, automatic confirmation, deadlines (7); joining and approval (8); Find Tours with score (9, 10.1); tour code and link (12); workspace Overview and Tourmates (13); notifications for P0 events (15); Tour Operations reports, suspend, restore, cancel (16); audit of every action |
| **P1** | Required for a safe, complete first release | Native chat with offline queue (14.1, 14.2); Itinerary, Budget, Safety (13); Find People and invitations (10.2, 11); co-organizers; change notice window (7.6); break-glass (16.3); abuse signals |
| **P2** | Valuable next | Chat media (14.3); polls; post-tour feedback and trip reviews; WhatsApp link; calendar export (.ics); Bangla push notifications on Android |
| **P3** | Future | Learned matching weights; saved searches with alerts; suggested tourmates for a tour; public tour templates; verified organiser badges |

---

## 20. Acceptance Criteria

Each criterion is tested end to end (see architecture, section 15).

**Access**
- AC-01 A Member who is not a Verified Member gets 404 for every tour API and sees the "Get verified" page.
- AC-02 A user under 18 cannot create, request or appear in Find People.

**Creation and policies**
- AC-03 A tour cannot be published without a recruitment deadline at least 24 hours before the start, or with a minimum below 2 or a maximum above 30.
- AC-04 An ineligible user never receives a policy-restricted tour in search results, and the API refuses their request even if they call it directly.
- AC-05 An Invite only tour never appears in Find Tours, and its code opens only the summary.

**Confirmation**
- AC-06 Approving the member who reaches the minimum confirms the tour in the same request; chat opens and every member is notified.
- AC-07 Twenty simultaneous approvals on a tour with 5 seats left produce exactly 5 approved members and exactly one confirmation event.
- AC-08 A Confirmed tour that falls below the minimum shows At Risk, reopens recruitment if allowed, and is auto-cancelled 24 hours before the start if still At Risk.
- AC-09 A Recruiting tour below minimum at its deadline is cancelled, and pending requests expire.

**Joining**
- AC-10 A user cannot have two pending requests for one tour, more than 10 pending in total, or a request overlapping an approved tour's dates.
- AC-11 Blocked users cannot request, approve or invite each other, and the reason is never revealed.

**Codes and IDs**
- AC-12 After 10 failed code lookups in an hour, further lookups by that user are refused for the rest of the hour.
- AC-13 Regenerating a code makes the old code and link return "not found" immediately.

**Chat**
- AC-14 A non-member, a pending requester and a removed member cannot read or receive any message, including over an open live connection, within 5 seconds of removal.
- AC-15 Ten messages written offline are delivered once each, in order, after reconnection.

**Privacy and safety**
- AC-16 Find People shows only opted-in users, and only coarse fields.
- AC-17 Emergency contacts are unreadable in the database without the application key, visible to organisers only during Ongoing or SOS, and deleted 30 days after the tour ends.
- AC-18 Every staff action and every break-glass view appears in the audit log with actor, reason and time.

**Budget**
- AC-19 The balance view produces settlements whose sum is zero, and no screen asks for or stores payment account numbers.

---

## 21. Screens List

| Screen | Route | Priority |
|---|---|---|
| TourMate landing (non-verified) | `/tours` | P0 |
| Verified dashboard | `/tours` | P0 |
| Preferences | `/tours/preferences` | P0 |
| Create tour wizard | `/tours/new` | P0 |
| Find Tours | `/tours/find` | P0 |
| Find People | `/tours/find/people` | P1 |
| Tour summary (request screen) | `/t/{code}` and `/tours/{publicId}/summary` | P0 |
| Workspace tabs | `/tours/{publicId}/{tab}` | P0 / P1 |
| Requests and invitations | `/tours/requests`, `/tours/invitations` | P0 / P1 |
| Staff: Tour Operations | `admin.<domain>/tours/*` | P0 / P1 |

All screens follow the existing design system, are Bangla and English, work on a 360 px phone, meet WCAG 2.2 AA, and support low-data mode.
