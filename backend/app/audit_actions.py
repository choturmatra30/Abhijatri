"""Every action name the application writes to ``audit_events`` (Moderation spec 6.6).

The list is the contract for the audit log's filter and for the tests: ``audit.record`` logs a warning for a name
that is not here, and the test suite turns that into a failure, so a new write cannot ship without being listed.
"""

# Names written as literals.
FIXED = frozenset(
    {
        "appeal.received", "appeal.withdrawn",
        "audit.exported",
        "enforcement.opened",
        "evidence.upload_requested", "evidence.uploaded", "evidence.viewed",
        "notification.delivery_retried", "notification.rule_changed", "notification.suppression_added",
        "notification.suppression_removed", "notification.template_activated", "notification.template_drafted",
        "ratings.reconcile_repair", "ratings.reconcile_run",
        "removal_request.create",
        "report.create", "report.create_anonymous", "report.hide_pending",
        "retention.case_purged", "retention.evidence_purged", "retention.contact_erased",
        "review.conflict_set", "review.purged",
        "sanction.created", "sanction.expired", "sanction.reversed",
        "staff.mfa_reset", "staff.role_changed", "staff.role_granted", "staff.role_revoked",
        "task.assigned", "task.claimed", "task.escalated", "task.released",
        "verification.revoke_for_abuse", "verification.submitted",
        # verification application (Verified user sign-up form)
        "verification.draft_started", "verification.step_saved", "verification.phone_code_sent", "verification.phone_verified",
        "verification.student_email_verified", "verification.liveness_issued", "verification.duplicate_blocked",
        "verification.details_viewed", "verification.responded", "verification.expired", "verification.reopened",
        "verification.banned", "verification.ban_lifted", "retention.case_shredded",
        # user blocks (tours)
        "block.created", "block.removed",
        # Tours and Tour Operations
        "tour.created", "tour.published", "tour.confirmed", "tour.cancelled",
        "tour.request_approved", "tour.request_declined", "tour.member_removed",
        "tour.report_created", "tour.sos_raised", "tour.safety_revealed", "tour.safety_purged",
        "tour.suspended", "tour.restored", "tour.staff_cancel_requested", "tour.staff_cancelled",
        "tour.message_hidden", "tour.user_restricted", "tour.breakglass_granted", "tour.breakglass_viewed", "tour.report_resolved",
    }
)
# Names built from a state or decision: `<prefix>.<suffix>`.
FAMILIES: dict[str, frozenset[str]] = {
    "appeal": frozenset({"upheld", "overturned"}),
    "enforcement": frozenset({"remove", "restore", "close", "reverse_sanction"}),
    "media": frozenset({"approve", "reject"}),
    "report": frozenset({"in_review", "actioned", "dismissed"}),
    "review": frozenset({"publish", "reject", "hide", "restore", "request_changes", "set_conflict", "clear_conflict", "reopen"}),
    "verification": frozenset({"in_review", "needs_clarification", "approved", "rejected", "escalated", "withdrawn"}),
}
AUDIT_ACTIONS = FIXED | frozenset(f"{prefix}.{suffix}" for prefix, suffixes in FAMILIES.items() for suffix in suffixes)


def is_known(action: str) -> bool:
    """A refused attempt is audited as ``denied.<action>``; the action behind it must be known too."""
    return action in AUDIT_ACTIONS or (action.startswith("denied.") and len(action) > len("denied."))
