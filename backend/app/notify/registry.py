"""The controlled notification catalogue (Notification spec 3, 5, 7.6, 7.7).

Everything that decides who is told what lives here and is reviewed as code:

- ``RULES`` map a domain event (the outbox ``topic`` plus simple equality conditions on its payload)
  to one notification kind, a recipient resolver, a priority, an audience and an internal route;
- ``RESOLVERS`` is the allowlist of recipient policies: ``payload_user`` (one person named in the
  event) and ``captured_staff`` (staff captured when the event happened, re-checked against their
  current role before anything is shown);
- ``TEMPLATES`` are the version-1 texts in Bangla and English. Superadmins can add later versions in
  ``notification_templates``; only the variables listed here can appear in them;
- ``ROUTES`` is the allowlist of links. A link is never built from a URL somebody typed.

The live ``notification_rules`` table can only switch a rule's email on or off, change its priority
or disable it; it can never add an event, a resolver or a route.
"""

from dataclasses import dataclass

PRIORITIES = ("critical", "high", "normal", "low")
RESOLVERS = ("payload_user", "payload_users", "captured_staff")
ROUTES = (
    "/account",
    "/account/appeals",
    "/account/verification",
    "/verify",
    "/verify/status",
    "/account/notifications",
    "/destinations/{destination_id}",
    "staff:/",
    "/tours",
    "/tours/requests",
    "/tours/invitations",
    "/tours/{public_id}",
    "/tours/{public_id}/safety",
    "/tours/{public_id}/discussion",
)
VARIABLES = ("reference", "deadline", "question", "count", "outcome", "role", "tour")


@dataclass(frozen=True)
class Template:
    title_bn: str
    title_en: str
    body_bn: str
    body_en: str
    variables: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rule:
    event_type: str
    template_key: str  # also the notification kind
    resolver: str
    source: str  # payload field with the user id (payload_user) or the captured id list (captured_staff)
    priority: str
    audience: str = "member"
    email: bool = True
    route: str | None = None
    when: tuple[tuple[str, tuple[str, ...]], ...] = ()  # payload field -> allowed values
    role: str | None = None  # captured_staff: the role the person must still hold (None: any staff role)
    appeal_field: str | None = None  # payload field naming the appeal this notice belongs to


def _when(**conditions: str | tuple[str, ...]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple((key, value if isinstance(value, tuple) else (value,)) for key, value in conditions.items())


APPEAL_HINT = ("৩০ দিনের মধ্যে আপিল করতে পারবেন।", "You can appeal within 30 days.")

TEMPLATES: dict[str, Template] = {
    # ---- members: content ----
    "content.published": Template("আপনার রিভিউ প্রকাশিত হয়েছে", "Your review is published", "মডারেটর আপনার রিভিউ প্রকাশ করেছেন।", "A moderator published your review."),
    "content.changes_requested": Template("আপনার রিভিউতে পরিবর্তন দরকার", "Your review needs changes", "মডারেটর রিভিউটি ফেরত পাঠিয়েছেন। সম্পাদনা করে আবার জমা দিন।", "A moderator sent your review back. Edit it and it returns to the queue."),
    "content.rejected": Template("আপনার রিভিউ প্রকাশ করা হয়নি", "Your review was not published", f"রিভিউটি নীতিমালার সাথে মেলেনি। {APPEAL_HINT[0]}", f"The review did not meet the policy. {APPEAL_HINT[1]}"),
    "content.hidden": Template("আপনার রিভিউ লুকানো হয়েছে", "Your review was hidden", f"রিভিউটি এখন জনসমক্ষে দেখা যাচ্ছে না। {APPEAL_HINT[0]}", f"The review is no longer public. {APPEAL_HINT[1]}"),
    "content.taken_down": Template("আপনার রিভিউ সরিয়ে নেওয়া হয়েছে", "Your review was taken down", f"নীতিমালা অনুযায়ী রিভিউটি সরানো হয়েছে। {APPEAL_HINT[0]}", f"The review was taken down under the policy. {APPEAL_HINT[1]}"),
    "content.removed": Template("আপনার রিভিউ স্থায়ীভাবে সরানো হয়েছে", "Your review was removed", f"পর্যালোচনার পর রিভিউটি সরানোর সিদ্ধান্ত বহাল। {APPEAL_HINT[0]}", f"After review, the removal stands. {APPEAL_HINT[1]}"),
    "content.reopened": Template("আপনার রিভিউ আবার পর্যালোচনায়", "Your review is being reviewed again", "একজন সুপারঅ্যাডমিন আপনার বাতিল হওয়া রিভিউটি আবার মডারেশনে পাঠিয়েছেন। এখনো এটি প্রকাশিত হয়নি।", "A superadmin sent your rejected review back to moderation. It is not published yet."),
    "content.restored": Template("আপনার রিভিউ আবার দেখা যাচ্ছে", "Your review is visible again", "মডারেটর আপনার রিভিউ ফিরিয়ে দিয়েছেন।", "A moderator restored your review."),
    # ---- members: account ----
    "account.case_opened": Template("আপনার অ্যাকাউন্টে পর্যালোচনা", "Your account is under review", f"নীতিমালা অনুযায়ী আপনার অ্যাকাউন্ট পর্যালোচনা হচ্ছে। {APPEAL_HINT[0]}", f"Your account is being reviewed under the policy. {APPEAL_HINT[1]}"),
    "account.warning": Template("আপনার অ্যাকাউন্টে সতর্কবার্তা", "A warning on your account", f"নীতিমালা ভঙ্গের জন্য সতর্ক করা হয়েছে। {APPEAL_HINT[0]}", f"You received a warning for a policy breach. {APPEAL_HINT[1]}"),
    "account.restricted": Template("আপনার অ্যাকাউন্টে সীমাবদ্ধতা", "Your account is restricted", f"কিছু সময়ের জন্য রিভিউ দেওয়া বন্ধ। {APPEAL_HINT[0]}", f"Posting is restricted for a while. {APPEAL_HINT[1]}"),
    "account.restriction_lifted": Template("সীমাবদ্ধতা শেষ", "Restriction lifted", "আপনার অ্যাকাউন্টের সীমাবদ্ধতা তুলে নেওয়া হয়েছে।", "The restriction on your account was lifted."),
    "account.suspended": Template("আপনার অ্যাকাউন্ট স্থগিত", "Your account is suspended", f"অ্যাকাউন্টটি সাময়িকভাবে স্থগিত করা হয়েছে। {APPEAL_HINT[0]}", f"Your account is suspended for now. {APPEAL_HINT[1]}"),
    "account.suspension_lifted": Template("স্থগিতাদেশ উঠে গেছে", "Suspension lifted", "আপনার অ্যাকাউন্ট আবার সক্রিয়।", "Your account is active again."),
    "account.removed": Template("আপনার অ্যাকাউন্ট সরানো হয়েছে", "Your account was removed", f"পর্যালোচনার পর অ্যাকাউন্টটি সরানো হয়েছে। {APPEAL_HINT[0]}", f"After review, your account was removed. {APPEAL_HINT[1]}"),
    "security.mfa_reset": Template("দ্বি-স্তরের যাচাই রিসেট হয়েছে", "Two-step verification was reset", "পরের সাইন-ইনে নতুন করে অথেনটিকেটর সেট করুন। এটি আপনি না চাইলে এখনই জানান।", "Set up your authenticator again at the next sign-in. If you did not ask for this, report it now."),
    "security.account_action_required": Template("আপনার পাসওয়ার্ড বদলানো হয়েছে", "Your password was changed", "এটি আপনি না করলে এখনই পাসওয়ার্ড রিসেট করুন।", "If this was not you, reset your password now."),
    # ---- members: verification ----
    "verification.submitted": Template("যাচাই আবেদন পাওয়া গেছে", "Verification request received", "একজন মডারেটর আপনার আবেদন দেখবেন।", "A moderator will review your request."),
    "verification.clarification_requested": Template("যাচাইয়ের জন্য আরও তথ্য দরকার", "More information is needed", "মডারেটরের প্রশ্ন: {question} — যাচাই পাতায় উত্তর দিন।", "The moderator asks: {question} — answer on the verification page.", ("question",)),
    "verification.approved": Template("আপনি এখন যাচাইকৃত সদস্য", "You are now a Verified Member", "অভিনন্দন! আপনার রিভিউ এখন কমিউনিটি রেটিংয়ে গণনা হবে।", "Congratulations! Your reviews now count towards the Community Rating."),
    "verification.rejected": Template("যাচাই আবেদন অনুমোদিত হয়নি", "Verification was not approved", APPEAL_HINT[0], APPEAL_HINT[1]),
    "verification.revoked": Template("যাচাইকৃত সদস্যের মর্যাদা বাতিল হয়েছে", "Your Verified Member status was removed", "আপনার রিভিউগুলো প্রকাশিত থাকবে, তবে কমিউনিটি রেটিংয়ে গণনা হবে না। সিদ্ধান্ত নিয়ে আপত্তি থাকলে আপিল করুন।", "Your reviews stay published but no longer count towards the Community Rating. You can appeal this decision."),
    "verification.renewal_due": Template("যাচাই নবায়নের সময় হয়েছে", "Time to renew your verification", "{count} দিনের মধ্যে নবায়ন করুন: বর্তমান নথি ও নতুন সেলফি দিন, নইলে ব্যাজ লুকানো হবে।", "Renew within {count} days: add a current document and a new selfie, or the badge will be hidden.", ("count",)),
    "verification.lapsed": Template("যাচাইয়ের মেয়াদ শেষ", "Your verification has lapsed", "ব্যাজ লুকানো হয়েছে এবং ট্যুরের সদস্যপদ নিষ্ক্রিয়। নবায়ন করলে সব ফিরে আসবে।", "Your badge is hidden and tour memberships are inactive. Renewing brings them back."),
    # ---- members: Tours and TourMates ----
    "tour.published": Template("ট্যুর প্রকাশিত হয়েছে", "Tour published", "{tour} এখন সদস্য নিচ্ছে।", "{tour} is now recruiting.", ("tour",)),
    "tour.request_received": Template("নতুন যোগদানের অনুরোধ", "New join request", "{tour}-এ একটি নতুন অনুরোধ এসেছে।", "A new request arrived for {tour}.", ("tour",)),
    "tour.request_approved": Template("অনুরোধ অনুমোদিত", "Request approved", "আপনি {tour}-এ যোগ দিয়েছেন।", "You joined {tour}.", ("tour",)),
    "tour.request_declined": Template("অনুরোধ অনুমোদিত হয়নি", "Request not approved", "{tour}-এর আয়োজক আপনার অনুরোধটি অনুমোদন করেননি।", "The organiser did not approve your request for {tour}.", ("tour",)),
    "tour.request_closed": Template("অনুরোধ বন্ধ হয়েছে", "Request closed", "{tour}-এ আর আসন নেই বা সদস্য নেওয়া বন্ধ।", "{tour} filled up or stopped recruiting.", ("tour",)),
    "tour.request_expired": Template("অনুরোধের সময় শেষ", "Request expired", "{tour}-এর অনুরোধের সময় শেষ হয়েছে।", "Your request for {tour} expired.", ("tour",)),
    "tour.confirmed": Template("ট্যুর নিশ্চিত", "Tour confirmed", "{tour} নিশ্চিত হয়েছে। আলোচনা, বাজেট ও সেফটি এখন খোলা।", "{tour} is confirmed. Discussion, budget and safety are now open.", ("tour",)),
    "tour.at_risk": Template("ট্যুর ঝুঁকিতে", "Tour at risk", "{tour}-এ ন্যূনতম সদস্য নেই।", "{tour} is below its minimum membership.", ("tour",)),
    "tour.risk_cleared": Template("ট্যুরের ঝুঁকি কেটেছে", "Tour risk cleared", "{tour} আবার ন্যূনতম সদস্যে পৌঁছেছে।", "{tour} has reached its minimum again.", ("tour",)),
    "tour.at_risk_warning": Template("ট্যুর বাতিল হতে পারে", "Tour may be cancelled", "{tour}: আর {count} ঘণ্টার মধ্যে ন্যূনতম সদস্য দরকার।", "{tour}: reach the minimum within {count} hours.", ("tour", "count")),
    "tour.key_details_changed": Template("ট্যুরের গুরুত্বপূর্ণ তথ্য বদলেছে", "Key tour details changed", "{tour}-এর তারিখ, গন্তব্য, আকার বা নীতি বদলেছে।", "Dates, destinations, size or policy changed for {tour}.", ("tour",)),
    "tour.member_left": Template("একজন সদস্য ট্যুর ছেড়েছেন", "A member left", "{tour}-এর সদস্যসংখ্যা বদলেছে।", "Membership changed for {tour}.", ("tour",)),
    "tour.member_removed": Template("ট্যুর সদস্যপদ শেষ", "Tour membership ended", "আপনাকে {tour} থেকে সরানো হয়েছে।", "You were removed from {tour}.", ("tour",)),
    "tour.cancelled": Template("ট্যুর বাতিল", "Tour cancelled", "{tour} বাতিল হয়েছে।", "{tour} was cancelled.", ("tour",)),
    "tour.started": Template("ট্যুর শুরু হয়েছে", "Tour started", "{tour} এখন চলছে।", "{tour} is now ongoing.", ("tour",)),
    "tour.starts_tomorrow": Template("ট্যুর আগামীকাল", "Tour starts tomorrow", "{tour} আগামীকাল শুরু হবে। সেফটি তথ্য দেখুন।", "{tour} starts tomorrow. Check the Safety tab.", ("tour",)),
    "tour.completed": Template("ট্যুর সম্পন্ন", "Tour completed", "{tour} সম্পন্ন হয়েছে।", "{tour} is complete.", ("tour",)),
    "tour.invitation_received": Template("ট্যুরে আমন্ত্রণ", "Tour invitation", "আপনাকে {tour}-এ আমন্ত্রণ জানানো হয়েছে।", "You were invited to {tour}.", ("tour",)),
    "tour.invitation_answered": Template("আমন্ত্রণের উত্তর", "Invitation answered", "{tour}-এর আমন্ত্রণ: {outcome}।", "Invitation to {tour}: {outcome}.", ("tour", "outcome")),
    "tour.checkin_requested": Template("সেফটি চেক-ইন", "Safety check-in", "{tour}-এর আয়োজক সবাইকে চেক-ইন করতে বলেছেন।", "An organiser asked everyone in {tour} to check in.", ("tour",)),
    "tour.sos": Template("জরুরি SOS", "Emergency SOS", "{tour}-এ SOS দেওয়া হয়েছে। এখনই সেফটি ট্যাব দেখুন; তাৎক্ষণিক বিপদে ৯৯৯-এ কল করুন।", "An SOS was raised in {tour}. Check Safety now; call 999 for immediate danger.", ("tour",)),
    "tour.contact_missing": Template("জরুরি যোগাযোগ যোগ করুন", "Add an emergency contact", "{tour} শুরুর আগে সেফটি তথ্য পূরণ করুন।", "Complete your Safety details before {tour} starts.", ("tour",)),
    "tour.suspended": Template("ট্যুর সাময়িক স্থগিত", "Tour temporarily suspended", "{tour} নিরাপত্তা পর্যালোচনার জন্য স্থগিত।", "{tour} is suspended for a safety review.", ("tour",)),
    "tour.restored": Template("ট্যুর পুনরুদ্ধার", "Tour restored", "{tour} আবার চালু হয়েছে।", "{tour} is available again.", ("tour",)),
    "tour.staff_reviewed": Template("স্টাফ ট্যুরের ব্যক্তিগত তথ্য দেখেছেন", "Staff reviewed private tour data", "নিরাপত্তা বা অভিযোগের জন্য অনুমোদিত স্টাফ {tour}-এর ব্যক্তিগত অংশ দেখেছেন; অডিট লগে রেকর্ড আছে।", "Authorised staff viewed a private part of {tour} for safety or a report; it is recorded in the audit log.", ("tour",)),
    "tour.sos_staff": Template("ট্যুর SOS: জরুরি পর্যালোচনা", "Tour SOS: urgent review", "একটি ট্যুর SOS সেফটি সারিতে অপেক্ষা করছে।", "A Tour SOS is waiting in the safety queue."),
    # ---- members: appeals and reports ----
    "appeal.received": Template("আপিল গ্রহণ করা হয়েছে", "Your appeal was received", "আপিল নম্বর {reference}। একজন স্বাধীন মডারেটর এটি দেখবেন। শেষ তারিখ {deadline}।", "Case reference {reference}. An independent moderator will review it. Deadline {deadline}.", ("reference", "deadline")),
    "appeal.decided": Template("আপিলের সিদ্ধান্ত", "Your appeal was decided", "আপিল {reference}: {outcome}।", "Appeal {reference}: {outcome}.", ("reference", "outcome")),
    "report.actioned": Template("আপনার রিপোর্ট পর্যালোচনা হয়েছে", "Your report was reviewed", "ধন্যবাদ। মডারেটর ব্যবস্থা নিয়েছেন।", "Thank you. A moderator took action."),
    "report.dismissed": Template("আপনার রিপোর্ট পর্যালোচনা হয়েছে", "Your report was reviewed", "ধন্যবাদ। মডারেটর কোনো সমস্যা পাননি।", "Thank you. A moderator found no problem."),
    # ---- staff ----
    "staff.verification_submitted": Template("নতুন যাচাই আবেদন", "New verification request", "সারিতে একটি নতুন যাচাই আবেদন আছে।", "A new verification request is in the queue."),
    "appeal.submitted": Template("নতুন আপিল", "New appeal", "আপিল {reference} সারিতে আছে।", "Appeal {reference} is in the queue.", ("reference",)),
    "moderation.task_assigned": Template("আপনাকে একটি কাজ দেওয়া হয়েছে", "A task was assigned to you", "সারিতে আপনার জন্য একটি কাজ অপেক্ষা করছে।", "A task in the queue is waiting for you."),
    "moderation.appeal_assigned": Template("আপনাকে একটি আপিল দেওয়া হয়েছে", "An appeal was assigned to you", "আপিল {reference} আপনার পর্যালোচনার অপেক্ষায়।", "Appeal {reference} is waiting for your review.", ("reference",)),
    "moderation.task_unassigned": Template("একটি কাজ আপনার থেকে সরানো হয়েছে", "A task was unassigned", "কাজটি এখন অন্য কারও কাছে বা সাধারণ সারিতে।", "The task moved to someone else or back to the shared queue."),
    "moderation.task_lease_expiring": Template("কাজের সময় শেষ হয়ে আসছে", "Your claim is about to expire", "এক মিনিটের মধ্যে সিদ্ধান্ত দিন বা সময় বাড়ান।", "Decide or extend within a minute, or the task is released."),
    "moderation.queue_overdue": Template("সারিতে দেরি হচ্ছে", "The queue is overdue", "{count}টি কাজ ২৪ ঘণ্টার বেশি অপেক্ষায়।", "{count} tasks have waited more than 24 hours.", ("count",)),
    "moderation.escalated": Template("কাজটি সুপারঅ্যাডমিনের কাছে গেছে", "Your task was escalated", "আপনার পাঠানো কাজটি এখন সুপারঅ্যাডমিন দেখবেন।", "The task you escalated is now with a superadmin."),
    "moderation.escalation_required": Template("এসকেলেশন: সিদ্ধান্ত দরকার", "Escalation needs a decision", "একটি কাজ সুপারঅ্যাডমিনের সিদ্ধান্তের অপেক্ষায়।", "A task is waiting for a superadmin decision."),
    "moderation.security_anomaly": Template("অস্বাভাবিক অনুমতি-প্রত্যাখ্যান", "Unusual denied actions", "এক কর্মীর অ্যাকাউন্ট থেকে অল্প সময়ে {count}টি প্রত্যাখ্যাত চেষ্টা। অডিট লগ দেখুন।", "{count} denied attempts from one staff account in a short time. Check the audit log.", ("count",)),
    "ratings.drift_detected": Template("রেটিং যোগফল মিলছে না", "Rating totals do not match", "{count}টি গন্তব্যের সংরক্ষিত রেটিং যোগফল রিভিউয়ের সাথে মিলছে না। অডিট লগ দেখুন।", "{count} destinations have stored rating totals that do not match their reviews. Check the audit log.", ("count",)),
    "moderation.emergency_takedown": Template("জরুরি টেকডাউন: ২৪ ঘণ্টার মধ্যে পর্যালোচনা", "Emergency takedown: review within 24 hours", "একটি জরুরি টেকডাউন সুপারঅ্যাডমিনের পর্যালোচনার অপেক্ষায়।", "An emergency takedown is waiting for a superadmin review."),
    "staff.role_granted": Template("আপনাকে কর্মী-ভূমিকা দেওয়া হয়েছে", "You were given a staff role", "নতুন ভূমিকা: {role}। কর্মী ড্যাশবোর্ডে সাইন ইন করে অথেনটিকেটর চালু করুন।", "New role: {role}. Sign in to the staff dashboard and set up your authenticator.", ("role",)),
    "staff.role_revoked": Template("আপনার কর্মী-ভূমিকা তুলে নেওয়া হয়েছে", "Your staff role was removed", "আপনি আর কর্মী ড্যাশবোর্ড ব্যবহার করতে পারবেন না।", "You can no longer use the staff dashboard."),
    "staff.role_changed": Template("কর্মী-ভূমিকা বদলেছে", "A staff role changed", "একজন কর্মীর ভূমিকা এখন: {role}। অডিট লগে বিস্তারিত আছে।", "A staff member's role is now: {role}. Details are in the audit log.", ("role",)),
    "notification.delivery_failure_threshold_reached": Template("ইমেইল পাঠানো ব্যর্থ হচ্ছে", "Emails are failing", "গত এক ঘণ্টায় {count}টি ইমেইল পাঠানো যায়নি।", "{count} emails could not be sent in the last hour.", ("count",)),
    "notification.outbox_backlog_threshold_reached": Template("নোটিফিকেশন জমে আছে", "Notifications are backed up", "{count}টি ঘটনা ১০ মিনিটের বেশি অপেক্ষায়।", "{count} events have waited more than 10 minutes.", ("count",)),
    "notification.provider_webhook_anomaly": Template("ইমেইল সেবার কলব্যাকে সমস্যা", "Email provider callbacks look wrong", "গত এক ঘণ্টায় {count}টি কলব্যাক যাচাই হয়নি।", "{count} provider callbacks failed verification in the last hour.", ("count",)),
}

SUPERADMIN = "superadmin"

RULES: tuple[Rule, ...] = (
    # content decisions (review.state_changed carries the decision and the author)
    Rule("review.state_changed", "content.published", "payload_user", "author_id", "normal", route="/destinations/{destination_id}", when=_when(decision="PUBLISH")),
    Rule("review.state_changed", "content.changes_requested", "payload_user", "author_id", "high", route="/account", when=_when(decision="REQUEST_CHANGES")),
    Rule("review.state_changed", "content.rejected", "payload_user", "author_id", "critical", route="/account/appeals", when=_when(decision="REJECT")),
    Rule("review.state_changed", "content.hidden", "payload_user", "author_id", "critical", route="/account/appeals", when=_when(decision="HIDE")),
    Rule("review.state_changed", "content.reopened", "payload_user", "author_id", "normal", route="/account", when=_when(decision="REOPEN")),
    Rule("review.state_changed", "content.restored", "payload_user", "author_id", "normal", route="/destinations/{destination_id}", when=_when(decision="RESTORE")),
    # enforcement
    Rule("enforcement.opened", "content.taken_down", "payload_user", "subject_id", "critical", route="/account/appeals", when=_when(kind="takedown")),
    Rule("enforcement.opened", "account.case_opened", "payload_user", "subject_id", "critical", route="/account/appeals", when=_when(kind="account")),
    Rule("enforcement.opened", "moderation.emergency_takedown", "captured_staff", "staff_recipients", "critical", audience="staff", route="staff:/", when=_when(emergency="true"), role=SUPERADMIN),
    Rule("enforcement.state_changed", "content.restored", "payload_user", "subject_id", "normal", route="/account/appeals", when=_when(kind="takedown", state="restored")),
    Rule("enforcement.state_changed", "content.removed", "payload_user", "subject_id", "critical", route="/account/appeals", when=_when(kind="takedown", state="removed")),
    Rule("enforcement.state_changed", "account.removed", "payload_user", "subject_id", "critical", route="/account/appeals", when=_when(kind="account", state="removed")),
    Rule("sanction.created", "account.warning", "payload_user", "user_id", "critical", route="/account/appeals", when=_when(kind="warning")),
    Rule("sanction.created", "account.restricted", "payload_user", "user_id", "critical", route="/account/appeals", when=_when(kind="posting_restriction")),
    Rule("sanction.created", "account.suspended", "payload_user", "user_id", "critical", route="/account/appeals", when=_when(kind="suspension")),
    Rule("sanction.ended", "account.restriction_lifted", "payload_user", "user_id", "critical", when=_when(kind="posting_restriction")),
    Rule("sanction.ended", "account.suspension_lifted", "payload_user", "user_id", "critical", when=_when(kind="suspension")),
    # verification
    Rule("verification.submitted", "verification.submitted", "payload_user", "applicant_id", "normal", route="/verify/status"),
    Rule("verification.submitted", "staff.verification_submitted", "captured_staff", "staff_recipients", "normal", audience="staff", route="staff:/"),
    Rule("verification.state_changed", "verification.clarification_requested", "payload_user", "applicant_id", "high", route="/verify/status", when=_when(state="needs_clarification")),
    Rule("verification.state_changed", "verification.approved", "payload_user", "applicant_id", "critical", route="/verify/status", when=_when(state="approved")),
    Rule("verification.state_changed", "verification.revoked", "payload_user", "applicant_id", "critical", route="/account/appeals", when=_when(state="revoked")),
    Rule("verification.state_changed", "verification.rejected", "payload_user", "applicant_id", "critical", route="/account/appeals", when=_when(state="rejected")),
    Rule("verification.renewal_due", "verification.renewal_due", "payload_user", "user_id", "high", route="/verify/status"),
    Rule("verification.lapsed", "verification.lapsed", "payload_user", "user_id", "critical", route="/verify/status"),
    # Tours and TourMates: recipient ids are captured when the event is written.
    Rule("tour.published", "tour.published", "payload_user", "creator_id", "normal", route="/tours/{public_id}"),
    Rule("tour.request_created", "tour.request_received", "payload_users", "organiser_ids", "high", route="/tours/{public_id}"),
    Rule("tour.request_approved", "tour.request_approved", "payload_user", "user_id", "critical", route="/tours/{public_id}"),
    Rule("tour.request_declined", "tour.request_declined", "payload_user", "user_id", "normal", route="/tours/requests"),
    Rule("tour.request_closed", "tour.request_closed", "payload_user", "user_id", "normal", route="/tours/requests"),
    Rule("tour.request_expired", "tour.request_expired", "payload_user", "user_id", "normal", route="/tours/requests"),
    Rule("tour.confirmed", "tour.confirmed", "payload_users", "member_ids", "critical", route="/tours/{public_id}"),
    Rule("tour.at_risk", "tour.at_risk", "payload_users", "member_ids", "high", route="/tours/{public_id}"),
    Rule("tour.risk_cleared", "tour.risk_cleared", "payload_users", "member_ids", "normal", route="/tours/{public_id}"),
    Rule("tour.at_risk_warning", "tour.at_risk_warning", "payload_users", "member_ids", "high", route="/tours/{public_id}"),
    Rule("tour.key_details_changed", "tour.key_details_changed", "payload_users", "member_ids", "high", route="/tours/{public_id}"),
    Rule("tour.member_left", "tour.member_left", "payload_users", "organiser_ids", "normal", route="/tours/{public_id}"),
    Rule("tour.member_removed", "tour.member_removed", "payload_user", "user_id", "critical", route="/tours"),
    Rule("tour.cancelled", "tour.cancelled", "payload_users", "member_ids", "critical", route="/tours/{public_id}"),
    Rule("tour.started", "tour.started", "payload_users", "member_ids", "high", route="/tours/{public_id}"),
    Rule("tour.starts_tomorrow", "tour.starts_tomorrow", "payload_users", "member_ids", "high", route="/tours/{public_id}/safety"),
    Rule("tour.completed", "tour.completed", "payload_users", "member_ids", "normal", route="/tours/{public_id}"),
    Rule("tour.invitation_received", "tour.invitation_received", "payload_user", "user_id", "high", route="/tours/invitations"),
    Rule("tour.invitation_answered", "tour.invitation_answered", "payload_user", "user_id", "normal", route="/tours/{public_id}"),
    Rule("tour.checkin_requested", "tour.checkin_requested", "payload_users", "member_ids", "critical", route="/tours/{public_id}/safety"),
    Rule("tour.sos", "tour.sos", "payload_users", "member_ids", "critical", route="/tours/{public_id}/safety"),
    Rule("tour.contact_missing", "tour.contact_missing", "payload_users", "member_ids", "high", route="/tours/{public_id}/safety"),
    Rule("tour.suspended", "tour.suspended", "payload_users", "member_ids", "critical", route="/tours/{public_id}"),
    Rule("tour.restored", "tour.restored", "payload_users", "member_ids", "high", route="/tours/{public_id}"),
    Rule("tour.staff_reviewed", "tour.staff_reviewed", "payload_users", "member_ids", "critical", route="/tours/{public_id}"),
    Rule("tour.sos_staff", "tour.sos_staff", "captured_staff", "staff_recipients", "critical", audience="staff", route="staff:/"),
    # appeals and reports
    Rule("appeal.received", "appeal.received", "payload_user", "appellant_id", "critical", route="/account/appeals", appeal_field="appeal_id"),
    Rule("appeal.received", "appeal.submitted", "captured_staff", "staff_recipients", "normal", audience="staff", route="staff:/", appeal_field="appeal_id"),
    Rule("appeal.decided", "appeal.decided", "payload_user", "appellant_id", "critical", route="/account/appeals", appeal_field="appeal_id"),
    Rule("report.state_changed", "report.actioned", "payload_user", "reporter_id", "normal", when=_when(state="actioned")),
    Rule("report.state_changed", "report.dismissed", "payload_user", "reporter_id", "normal", when=_when(state="dismissed")),
    # moderators
    Rule("task.assigned", "moderation.appeal_assigned", "payload_user", "assignee_id", "high", audience="staff", route="staff:/", when=_when(task_type="appeal")),
    Rule("task.assigned", "moderation.task_assigned", "payload_user", "assignee_id", "high", audience="staff", route="staff:/", when=_when(task_type=("review_moderation", "report", "verification", "enforcement", "tour_report", "chat_report", "tour_safety"))),
    Rule("task.assigned", "moderation.task_unassigned", "payload_user", "previous_id", "normal", audience="staff", route="staff:/"),
    Rule("task.lease_expiring", "moderation.task_lease_expiring", "payload_user", "holder_id", "high", audience="staff", email=False, route="staff:/"),
    Rule("moderation.queue_overdue", "moderation.queue_overdue", "captured_staff", "staff_recipients", "normal", audience="staff", route="staff:/"),
    Rule("task.escalated", "moderation.escalated", "payload_user", "holder_id", "normal", audience="staff", email=False, route="staff:/"),
    Rule("task.escalated", "moderation.escalation_required", "captured_staff", "staff_recipients", "high", audience="staff", route="staff:/", role=SUPERADMIN),
    Rule("ratings.drift_detected", "ratings.drift_detected", "captured_staff", "staff_recipients", "high", audience="staff", route="staff:/", role=SUPERADMIN),
    Rule("moderation.security_anomaly", "moderation.security_anomaly", "captured_staff", "staff_recipients", "high", audience="staff", route="staff:/", role=SUPERADMIN),
    # superadmins and role changes (the affected person is told even after losing the role)
    Rule("staff.role_changed", "staff.role_granted", "payload_user", "target_id", "critical", route="staff:/", when=_when(granted="true")),
    Rule("staff.role_changed", "staff.role_revoked", "payload_user", "target_id", "critical", when=_when(granted="false")),
    Rule("staff.role_changed", "staff.role_changed", "captured_staff", "staff_recipients", "normal", audience="staff", route="staff:/", role=SUPERADMIN),
    Rule("notification.delivery_failure_threshold_reached", "notification.delivery_failure_threshold_reached", "captured_staff", "staff_recipients", "high", audience="staff", route="staff:/", role=SUPERADMIN),
    Rule("notification.outbox_backlog_threshold_reached", "notification.outbox_backlog_threshold_reached", "captured_staff", "staff_recipients", "high", audience="staff", route="staff:/", role=SUPERADMIN),
    Rule("notification.provider_webhook_anomaly", "notification.provider_webhook_anomaly", "captured_staff", "staff_recipients", "high", audience="staff", route="staff:/", role=SUPERADMIN),
    # security
    Rule("security.password_changed", "security.account_action_required", "payload_user", "user_id", "critical", route="/account/notifications"),
    Rule("security.mfa_reset", "security.mfa_reset", "payload_user", "user_id", "critical", route="staff:/"),
)

# Catalogued in spec 3 but without a workflow in v1, so never emitted: verification.expired,
# account.removal_requested.
NOT_EMITTED = ("verification.expired", "account.removal_requested")


def rules_for(event_type: str) -> list[Rule]:
    return [rule for rule in RULES if rule.event_type == event_type]


def _check() -> None:
    """Fail at import if the catalogue is inconsistent (a test imports this module)."""
    for rule in RULES:
        assert rule.template_key in TEMPLATES, rule.template_key
        assert rule.resolver in RESOLVERS and rule.priority in PRIORITIES and rule.audience in ("member", "staff")
        assert rule.route is None or rule.route in ROUTES, rule.route
    for key, template in TEMPLATES.items():
        assert set(template.variables) <= set(VARIABLES), key


_check()
