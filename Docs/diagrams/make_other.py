"""State, sequence, ER, Venn and use case figures for the Abhijatri documents.   Usage: python make_other.py

Every figure is drawn from data in this file and checked for layout problems (a line under a box, a label on another
label or arrow, a Venn label outside its region). The script exits non-zero if any check fails.
"""

import sys
from pathlib import Path

from diagram_lib import _trim, PAL, draw_erd, draw_sequence, draw_states, draw_usecases, draw_venn3

OUT = Path(__file__).resolve().parent


def states() -> list[str]:
    lilac, green, red, grey, amber = "#EDE3F2", "#E3F3EA", "#F7DDD4", "#EFEFEF", "#FFF1D6"
    st = {
        "REJECTED": (27, 82, red),
        "HIDDEN": (69, 82, red),
        "PENDING": (27, 55, lilac),
        "PUBLISHED": (69, 55, green),
        "CHANGES_REQUESTED": (27, 28, amber),
        "WITHDRAWN": (69, 8, grey),
    }
    edges = [
        ("__start", "PENDING", "submit"),
        ("PENDING", "PUBLISHED", "PUBLISH (rating counted)"),
        ("PENDING", "REJECTED", "REJECT"),
        ("REJECTED", "PENDING", "appeal overturned: back to the queue"),
        ("PENDING", "CHANGES_REQUESTED", "REQUEST_CHANGES"),
        ("CHANGES_REQUESTED", "PENDING", "author edits (new revision)"),
        ("PUBLISHED", "HIDDEN", "HIDE or enforcement takedown (rating removed)"),
        ("HIDDEN", "PUBLISHED", "RESTORE, appeal overturned or enforcement lifted"),
        ("__group", "WITHDRAWN", "withdraw"),
    ]
    probs = draw_states(
        str(OUT / "review-state.png"), "", st, edges,  # no in-image title: the SRS caption names the figure
        size=(9.0, 10.4), dashed=set(), start=(5, 55),
        group=(12, 19, 86, 93, "Withdrawable states"))
    _trim(str(OUT / "review-state.png"), 200)
    return probs


SEQ_STYLE = dict(fs=11.0, tight=True, call_colour="#1F6F5C", return_colour="#C8641E", self_colour="#8E44AD")
PART = {  # (fill, edge) per kind of participant; no blue
    "person": ("#FFF1D6", "#D55E00"), "api": ("#E3F3EA", "#009E73"), "external": ("#FCF3CF", "#B7950B"),
    "db": ("#EDE3F2", "#8E44AD"), "staff": ("#F7DDD4", "#C0504D"), "worker": ("#E9EFE0", "#5E7D1E"),
}


def sequences() -> list[str]:
    p = draw_sequence(
        str(OUT / "seq-submit-moderate.png"),
        "",
        ["Guest browser (PWA)", "API (FastAPI)", "Cloudflare Turnstile", "PostgreSQL", "Moderator (staff app)", "Outbox\nworker"],
        [
            (0, 1, "POST /reviews/guest: review, receipt, draft id, Turnstile token"),
            (1, 2, "verify the challenge token"),
            (2, 1, "pass", "return"),
            (1, 1, "validate; check rate limits and duplicates", "self"),
            (1, 3, "insert review, first revision, receipt digest, task, outbox event (one transaction)"),
            (3, 1, "committed", "return"),
            (1, 0, "201 { review_id, status PENDING }", "return"),
            (4, 1, "POST /admin/tasks/{id}/claim"),
            (1, 4, "lease token (300 s)", "return"),
            (4, 1, "POST moderation-actions: PUBLISH + lease + version"),
            (1, 3, "PUBLISHED, rating totals, action, audit, outbox event (one transaction)"),
            (1, 4, "200 decision result", "return"),
            (5, 3, "claim due outbox events (FOR UPDATE SKIP LOCKED)"),
            (3, 5, "review.state_changed", "return"),
            (5, 5, "find recipients: a Guest author has no account, so no notification or email", "self"),
            (0, 1, "POST /review-receipts/status: review id + receipt"),
            (1, 0, "status PUBLISHED", "return"),
        ],
        size=(9.0, 14.6), colours=[PART[k] for k in ("person", "api", "external", "db", "staff", "worker")], **SEQ_STYLE,
    )
    p += draw_sequence(
        str(OUT / "seq-guest-edit.png"),
        "",
        ["Moderator (staff app)", "API (FastAPI)", "PostgreSQL", "Guest browser (PWA)"],
        [
            (0, 1, "moderation-actions: REQUEST_CHANGES + reason code + lease + version"),
            (1, 2, "CHANGES_REQUESTED, action, audit, outbox event"),
            (1, 0, "200 decision result", "return"),
            (3, 1, "POST /review-receipts/status: review id + receipt"),
            (1, 2, "read review and receipt digest"),
            (2, 1, "status, public reason", "return"),
            (1, 3, "CHANGES_REQUESTED + public reason", "return"),
            (3, 1, "PATCH /reviews/{id}/pending: receipt, expected_version, changed fields"),
            (1, 2, "lock review; read receipt digest and current revision"),
            (1, 1, "verify the receipt; check state and version; validate", "self"),
            (1, 2, "new revision (old one SUPERSEDED), PENDING, task re-queued, review.edited"),
            (1, 3, "200 { status PENDING, version, revision }", "return"),
            (0, 1, "claim the task and decide again"),
        ],
        size=(9.0, 12.6), colours=[PART[k] for k in ("staff", "api", "db", "person")], **SEQ_STYLE,
    )
    return p


def erd() -> list[str]:
    head = {"core": "#DCEBF7", "review": "#FFF1D6", "mod": "#F7DDD4", "notify": "#E3F3EA"}
    ents = {
        "users": (16, 108, ["PK id", "email, display_name", "status, last_visit_on"], head["core"]),
        "user_roles": (16, 80, ["PK id", "FK user_id", "role, revoked_at"], head["core"]),
        "destinations": (58, 112, ["PK id", "name_bn, name_en", "status"], head["core"]),
        "destination_rating_stats": (100, 112, ["PK/FK destination_id", "community sum, count", "guest sum, count"], head["core"]),
        "reviews": (58, 80, ["PK id", "FK destination_id", "FK author_user_id (null: guest)", "status, version", "counted_rating"], head["review"]),
        "review_revisions": (94, 84, ["PK id", "FK review_id", "sequence, status", "title, body, rating"], head["review"]),
        "review_category_ratings": (130, 84, ["PK/FK revision_id", "PK category", "rating 1..5"], head["review"]),
        "review_receipts": (16, 22, ["PK id", "FK review_id", "key_id, digest"], head["review"]),
        "review_media": (100, 58, ["PK id", "FK review_id", "FK uploader_id", "kind, state"], head["review"]),
        "moderation_actions": (58, 50, ["PK id", "FK review_id", "FK actor_user_id", "decision, new_status"], head["mod"]),
        "enforcement_cases": (16, 48, ["PK id", "FK review_id", "FK subject_user_id", "kind, state"], head["mod"]),
        "verification_cases": (130, 32, ["PK id", "FK applicant_user_id", "state, decided_by"], head["mod"]),
        "appeals": (58, 22, ["PK id", "FK appellant_user_id (null: guest)", "FK moderation_action_id", "FK enforcement_case_id",
                             "FK verification_case_id", "state, deadline_at"], head["mod"]),
        "outbox_events": (100, 30, ["PK id", "topic, aggregate_id", "status, attempts"], head["notify"]),
        "notifications": (100, 10, ["PK id", "FK event_id", "FK recipient_user_id"], head["notify"]),
    }
    ents = {k: (v[0], v[1] + 5, v[2], v[3]) for k, v in ents.items()}
    rels = [
        ("users", "user_roles", "has", "1", "0..N"),
        ("destinations", "reviews", "is reviewed in", "1", "0..N"),
        ("users", "reviews", "writes", "0..1", "0..N"),
        ("destinations", "destination_rating_stats", "has", "1", "0..1"),
        ("reviews", "review_revisions", "has", "1", "1..N"),
        ("review_revisions", "review_category_ratings", "scores", "1", "0..N"),
        ("reviews", "review_receipts", "proved by", "1", "0..N"),
        ("reviews", "review_media", "shows", "1", "0..N"),
        ("reviews", "moderation_actions", "decided by", "1", "0..N"),
        ("reviews", "enforcement_cases", "taken down in", "0..1", "0..N"),
        ("moderation_actions", "appeals", "appealed in", "0..1", "0..N"),
        ("enforcement_cases", "appeals", "appealed in", "0..1", "0..N"),
        ("verification_cases", "appeals", "appealed in", "0..1", "0..N"),
        ("outbox_events", "notifications", "becomes", "1", "0..N"),
    ]
    return draw_erd(
        str(OUT / "erd.png"), "Entity-relationship diagram: the main tables (crow's-foot notation, from backend/app/models.py)", ents, rels,
        size=(14.4, 13.0),
        note="Each appeal targets exactly one of a moderation action, an enforcement case or a verification case. Not drawn, to keep the "
             "figure readable: review_media.uploader_id, moderation_actions.actor_user_id, appeals.appellant_user_id, "
             "verification_cases.applicant_user_id and notifications.recipient_user_id all point to users. moderation_tasks.subject_id "
             "and audit_events have no database foreign key.")


def venns() -> list[str]:
    """The three Venn figures carry no title: the document's caption names each one, and the fonts are sized to stay
    readable when the figure is printed at text width (about 15 cm)."""
    p_, g, o = PAL["purple"], PAL["green"], PAL["orange"]
    circles = [dict(x=64, y=78, r=35, colour=p_), dict(x=107, y=78, r=35, colour=g), dict(x=85.5, y=41, r=35, colour=o)]
    big, mid, ctr = 21, 18, 21
    common = dict(size=(17.4, 13.6), name_size=21, tight=True, names_vertical=True)
    p = draw_venn3(
        str(OUT / "venn-product.png"), "",
        [dict(circles[0], name="Bangla-First"), dict(circles[1], name="Moderated and Dated"), dict(circles[2], name="Offline and Priced")],
        {
            "A": ("Bangla\ninterface\n(built)", big, "normal"),
            "B": ("Moderated\nreviews, dated\nadvisories\n(built)", big, "normal"),
            "C": ("Cost estimates,\noffline packs\n(prototype)", big, "normal"),
            "AB": ("Bangla\ncontent with\nfreshness\nlabels\n(built)", mid, "normal"),
            "AC": ("Bangla\npages\noffline\n(planned)", mid, "normal"),
            "BC": ("Estimates\nfrom dated\nprices\n(planned)", mid, "normal"),
            "ABC": ("ABHIJATRI", ctr, "bold"),
        },
        **common,
    )
    p += draw_venn3(
        str(OUT / "venn-landscape.png"), "",
        [dict(circles[0], name="Bangla-First"), dict(circles[1], name="Moderated and Dated"), dict(circles[2], name="Works Offline")],
        {
            "A": ("Social media\ntravel groups\nand blogs", big, "normal"),
            "B": ("Booking and\nguide sites", big, "normal"),
            "C": ("Maps and\noffline apps", big, "normal"),
            "AB": ("None of the\ntools\ncompared", mid, "normal"),
            "AC": ("None of the\ntools\ncompared", mid, "normal"),
            "BC": ("None of the\ntools\ncompared", mid, "normal"),
            "ABC": ("ABHIJATRI\n(offline\nplanned)", 18, "bold"),
        },
        **common,
    )
    p += draw_venn3(
        str(OUT / "venn-roles.png"), "",
        [dict(circles[0], name="Frontend and Offline\n(Abdullah)"), dict(circles[1], name="Backend and Data\n(Syed Muhtasim)"),
         dict(circles[2], name="Quality Assurance (Irfan)")],
        {
            "A": ("React,\nbilingual UI,\nPWA", big, "normal"),
            "B": ("FastAPI,\nPostgreSQL,\nauthentication", big, "normal"),
            "C": ("Test strategy,\npilot, defects", big, "normal"),
            "AB": ("API\ncontract,\nerror\nhandling", mid, "normal"),
            "AC": ("Offline\nand real-\ndevice\ntests", mid, "normal"),
            "BC": ("Integration\nand\nsecurity\ntests", mid, "normal"),
            "ABC": ("Leader\n(Shahriar)", 19, "bold"),
        },
        **common,
    )
    return p


def usecases() -> list[str]:
    actors = {
        "Guest": (7, 104, "Guest"),
        "Member": (7, 62, "Member"),
        "Verified": (7, 26, "Verified Member"),
        "Moderator": (97, 104, "Moderator"),
        "Superadmin": (97, 60, "Superadmin"),
        "Ops": (97, 18, "Ops operator"),
    }
    L, R = 39, 71
    cases = [
        ("browse", L, 118, "Browse destinations and advisories", "built"),
        ("read", L, 110, "Read published reviews and ratings", "built"),
        ("submit", L, 102, "Submit a review", "built"),
        ("status", L, 94, "Check, edit or withdraw a review", "built"),
        ("appeal", L, 86, "Appeal a decision", "built"),
        ("estimate", L, 78, "Estimate trip cost", "prototype"),
        ("offline", L, 70, "Download offline pack, save trip", "prototype"),
        ("account", L, 61, "Register, sign in, reset password", "built"),
        ("media", L, 53, "Attach photos and video", "built"),
        ("report", L, 45, "Report a review", "built"),
        ("inbox", L, 37, "Read notifications, set preferences", "built"),
        ("verify_req", L, 29, "Request the verified badge", "built"),
        ("community", L, 18, "Count toward the Community Rating", "built"),
        ("queue", R, 118, "Moderate the review queue", "built"),
        ("appeals", R, 110, "Decide appeals and reports", "built"),
        ("verify", R, 102, "Verify members", "built"),
        ("totp", R, 90, "Sign in with TOTP", "built"),
        ("enforce", R, 78, "Take enforcement action", "built"),
        ("roles", R, 70, "Manage staff roles", "built"),
        ("notifyadmin", R, 62, "Administer notifications", "built"),
        ("audit", R, 54, "Read the audit log", "built"),
        ("content", R, 46, "Edit destination content", "planned"),
        ("panels", R, 18, "Monitor health, content, traffic and queues", "built"),
    ]
    owner = {}
    for a, cs in (("Guest", ("browse", "read", "submit", "status", "appeal", "estimate", "offline")),
                  ("Member", ("account", "media", "report", "inbox", "verify_req")), ("Verified", ("community",)),
                  ("Moderator", ("queue", "appeals", "verify")), ("Superadmin", ("totp", "enforce", "roles", "notifyadmin", "audit", "content")),
                  ("Ops", ("panels",))):
        for c in cs:
            owner[c] = a
    # bow each column towards its actor ("(" on the left, ")" on the right) so no association line cuts another ellipse
    cases = [(cid, x - min(0.42 * abs(y - actors[owner[cid]][1]), 7.0) * (1 if x < 50 else -1), y, text, status) for cid, x, y, text, status in cases]
    links = [("Guest", c) for c in ("browse", "read", "submit", "status", "appeal", "estimate", "offline")]
    links += [("Member", c) for c in ("account", "media", "report", "inbox", "verify_req")]
    links += [("Verified", "community")]
    links += [("Moderator", c) for c in ("queue", "appeals", "verify", "totp")]
    links += [("Superadmin", c) for c in ("totp", "enforce", "roles", "notifyadmin", "audit", "content")]
    links += [("Ops", "panels")]
    return draw_usecases(
        str(OUT / "usecase-asbuilt.png"), "Use case diagram: Abhijatri as built (31 October 2026)", actors, cases, links,
        generalisations=[("Member", "Guest"), ("Verified", "Member")],
        boundary=(16, 10, 88, 124, "Abhijatri platform"),
        size=(10.4, 13.4),
        note="A Member can do everything a Guest can, and a Verified Member everything a Member can (hollow arrows). The Ops operator "
             "uses the separate ops site with a token.",
    )


if __name__ == "__main__":
    problems = states() + sequences() + erd() + venns() + usecases()
    for p in problems:
        print("LAYOUT PROBLEM:", p)
    print("drew state, sequence, ER, Venn and use case figures; layout problems:", len(problems))
    sys.exit(1 if problems else 0)
