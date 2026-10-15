from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Destination,
    DestinationRatingStats,
    DestinationStatus,
    ModerationActionRecord,
    ModerationDecision,
    OutboxEvent,
    RatingEligibility,
    Review,
    ReviewReceipt,
    ReviewRevision,
    ReviewStatus,
    RevisionStatus,
    User,
    Verification,
)
from app.schemas import GuestReviewCreate


class ReviewError(Exception):
    pass


class ReviewNotFound(ReviewError):
    pass


class ReviewConflict(ReviewError):
    pass


class ReviewForbidden(ReviewError):
    pass


@dataclass(frozen=True)
class GuestSubmissionResult:
    review: Review
    receipt_token: str
    duplicate_recovered: bool


RESERVED_NAME_SKELETONS = {
    "admin",
    "administrator",
    "moderator",
    "official",
    "verified",
    "abhijatristaff",
}


def now_utc() -> datetime:
    return datetime.now(UTC)


def hash_secret(value: str) -> bytes:
    pepper = get_settings().receipt_pepper.encode("utf-8")
    return hmac.new(pepper, value.encode("utf-8"), hashlib.sha256).digest()


def _name_skeleton(value: str) -> str:
    folded = value.casefold()
    return "".join(character for character in folded if character.isalnum())


def normalize_guest_name(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized or len(normalized) > 80:
        raise ReviewConflict("invalid guest display name")
    skeleton = _name_skeleton(normalized)
    if skeleton in RESERVED_NAME_SKELETONS or "✓" in normalized or "✔" in normalized:
        raise ReviewConflict("reserved or misleading guest display name")
    return normalized


def _new_receipt_token() -> str:
    return secrets.token_urlsafe(32)


def _issue_receipt(session: Session, review_id: uuid.UUID) -> str:
    token = _new_receipt_token()
    session.add(ReviewReceipt(review_id=review_id, token_hash=hash_secret(token)))
    return token


def submit_guest_review(session: Session, payload: GuestReviewCreate) -> GuestSubmissionResult:
    destination = session.scalar(
        select(Destination).where(
            Destination.id == payload.destination_id,
            Destination.status == DestinationStatus.PUBLISHED,
        )
    )
    if destination is None:
        raise ReviewNotFound("published destination not found")

    scope_hash = hash_secret(payload.guest_scope_secret)
    existing = session.scalar(
        select(Review).where(
            Review.author_user_id.is_(None),
            Review.guest_scope_hash == scope_hash,
            Review.client_draft_id == payload.client_draft_id,
        )
    )
    if existing is not None:
        # The same high-entropy Guest scope proves ownership of this offline draft.
        # Rotate the receipt so a lost response can be recovered without a duplicate.
        return GuestSubmissionResult(
            review=existing,
            receipt_token=_issue_receipt(session, existing.id),
            duplicate_recovered=True,
        )

    review = Review(
        destination_id=payload.destination_id,
        guest_display_name=normalize_guest_name(payload.guest_display_name),
        guest_scope_hash=scope_hash,
        client_draft_id=payload.client_draft_id,
        status=ReviewStatus.PENDING,
        rating_eligibility=RatingEligibility.NOT_EVALUATED,
        overall_rating=payload.overall_rating,
        visit_month=payload.visit_month,
    )
    try:
        with session.begin_nested():
            session.add(review)
            session.flush()
    except IntegrityError:
        # A simultaneous retry can pass the read check while the first request
        # is still uncommitted. The partial unique index is authoritative.
        existing = session.scalar(
            select(Review).where(
                Review.author_user_id.is_(None),
                Review.guest_scope_hash == scope_hash,
                Review.client_draft_id == payload.client_draft_id,
            )
        )
        if existing is None:
            raise
        return GuestSubmissionResult(
            review=existing,
            receipt_token=_issue_receipt(session, existing.id),
            duplicate_recovered=True,
        )

    revision = ReviewRevision(
        review_id=review.id,
        sequence=1,
        status=RevisionStatus.PENDING,
        language=payload.language,
        traveller_type=payload.traveller_type,
        comfort_tier=payload.comfort_tier,
        title=payload.title,
        body=payload.body,
        overall_rating=payload.overall_rating,
        consent_version=payload.consent_version,
    )
    session.add(revision)
    session.flush()
    review.current_revision_id = revision.id

    session.execute(
        insert(DestinationRatingStats)
        .values(destination_id=payload.destination_id)
        .on_conflict_do_nothing(index_elements=[DestinationRatingStats.destination_id])
    )
    receipt_token = _issue_receipt(session, review.id)
    session.add(
        OutboxEvent(
            topic="review.submitted",
            aggregate_id=review.id,
            payload={"review_id": str(review.id), "destination_id": str(review.destination_id)},
        )
    )
    return GuestSubmissionResult(review=review, receipt_token=receipt_token, duplicate_recovered=False)


def _lock_review(session: Session, review_id: uuid.UUID) -> Review:
    review = session.scalar(select(Review).where(Review.id == review_id).with_for_update())
    if review is None:
        raise ReviewNotFound("review not found")
    return review


def _lock_stats(session: Session, destination_id: uuid.UUID) -> DestinationRatingStats:
    stats = session.scalar(
        select(DestinationRatingStats)
        .where(DestinationRatingStats.destination_id == destination_id)
        .with_for_update()
    )
    if stats is None:
        session.execute(
            insert(DestinationRatingStats)
            .values(destination_id=destination_id)
            .on_conflict_do_nothing(index_elements=[DestinationRatingStats.destination_id])
        )
        stats = session.scalar(
            select(DestinationRatingStats)
            .where(DestinationRatingStats.destination_id == destination_id)
            .with_for_update()
        )
    if stats is None:
        raise RuntimeError("rating aggregate could not be created")
    return stats


def _remove_counted_rating(review: Review, stats: DestinationRatingStats) -> None:
    if review.counted_rating is None:
        return
    if review.author_user_id is None:
        stats.guest_rating_sum -= review.counted_rating
        stats.guest_rating_count -= 1
    else:
        stats.community_rating_sum -= review.counted_rating
        stats.community_rating_count -= 1
    review.counted_rating = None
    stats.version += 1
    stats.updated_at = now_utc()


def _is_verified_member_eligible(session: Session, review: Review) -> bool:
    if review.author_user_id is None or review.conflict_declared:
        return False
    author = session.get(User, review.author_user_id)
    if author is None or author.is_team_account:
        return False
    now = now_utc()
    return (
        session.scalar(
            select(Verification.id).where(
                Verification.user_id == review.author_user_id,
                Verification.verification_type == "VERIFIED_MEMBER",
                Verification.status == "APPROVED",
                Verification.revoked_at.is_(None),
                or_(Verification.expires_at.is_(None), Verification.expires_at > now),
            )
        )
        is not None
    )


def _add_published_rating(
    session: Session,
    review: Review,
    stats: DestinationRatingStats,
) -> None:
    if review.conflict_declared:
        review.rating_eligibility = RatingEligibility.INELIGIBLE_CONFLICT
        review.counted_rating = None
        return
    if review.author_user_id is None:
        review.rating_eligibility = RatingEligibility.INELIGIBLE_GUEST
        stats.guest_rating_sum += review.overall_rating
        stats.guest_rating_count += 1
    elif _is_verified_member_eligible(session, review):
        review.rating_eligibility = RatingEligibility.ELIGIBLE
        stats.community_rating_sum += review.overall_rating
        stats.community_rating_count += 1
    else:
        review.rating_eligibility = RatingEligibility.INELIGIBLE_UNVERIFIED
        review.counted_rating = None
        return
    review.counted_rating = review.overall_rating
    stats.version += 1
    stats.updated_at = now_utc()


def moderate_review(
    session: Session,
    *,
    review_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    expected_version: int,
    decision: ModerationDecision,
    reason_code: str,
    note: str | None,
) -> Review:
    review = _lock_review(session, review_id)
    if review.version != expected_version:
        raise ReviewConflict("review version changed")
    if review.author_user_id == actor_user_id:
        raise ReviewForbidden("moderators cannot act on their own reviews")

    actor = session.get(User, actor_user_id)
    if actor is None:
        raise ReviewForbidden("moderator not found")

    previous_status = review.status
    stats = _lock_stats(session, review.destination_id)
    revision = session.get(ReviewRevision, review.current_revision_id)
    if revision is None:
        raise ReviewConflict("review has no current revision")

    if decision == ModerationDecision.PUBLISH:
        if review.status not in {ReviewStatus.PENDING, ReviewStatus.UNDER_REVIEW}:
            raise ReviewConflict("review cannot be published from its current state")
        _remove_counted_rating(review, stats)
        review.status = ReviewStatus.PUBLISHED
        review.published_at = now_utc()
        revision.status = RevisionStatus.PUBLISHED
        _add_published_rating(session, review, stats)
    elif decision == ModerationDecision.REJECT:
        if review.status not in {ReviewStatus.PENDING, ReviewStatus.UNDER_REVIEW}:
            raise ReviewConflict("review cannot be rejected from its current state")
        _remove_counted_rating(review, stats)
        review.status = ReviewStatus.REJECTED
        review.rating_eligibility = RatingEligibility.INELIGIBLE_REMOVED
        revision.status = RevisionStatus.REJECTED
    elif decision == ModerationDecision.HIDE:
        if review.status != ReviewStatus.PUBLISHED:
            raise ReviewConflict("only a published review can be hidden")
        _remove_counted_rating(review, stats)
        review.status = ReviewStatus.HIDDEN
        review.rating_eligibility = RatingEligibility.INELIGIBLE_REPORTED
    elif decision == ModerationDecision.RESTORE:
        if review.status != ReviewStatus.HIDDEN:
            raise ReviewConflict("only a hidden review can be restored")
        _remove_counted_rating(review, stats)
        review.status = ReviewStatus.PUBLISHED
        _add_published_rating(session, review, stats)
    else:
        raise ReviewConflict("unsupported moderation decision")

    review.version += 1
    review.updated_at = now_utc()
    session.add(
        ModerationActionRecord(
            review_id=review.id,
            actor_user_id=actor_user_id,
            decision=decision,
            previous_status=previous_status,
            new_status=review.status,
            reason_code=reason_code,
            note=note,
        )
    )
    session.add(
        OutboxEvent(
            topic="review.state_changed",
            aggregate_id=review.id,
            payload={
                "review_id": str(review.id),
                "destination_id": str(review.destination_id),
                "status": review.status.value,
                "version": review.version,
            },
        )
    )
    return review


def set_review_conflict(
    session: Session,
    *,
    review_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    expected_version: int,
    conflict_declared: bool,
    reason_code: str,
    note: str | None,
) -> Review:
    review = _lock_review(session, review_id)
    if review.version != expected_version:
        raise ReviewConflict("review version changed")
    if review.author_user_id == actor_user_id:
        raise ReviewForbidden("moderators cannot act on their own reviews")
    if session.get(User, actor_user_id) is None:
        raise ReviewForbidden("moderator not found")
    if review.conflict_declared == conflict_declared:
        return review

    stats = _lock_stats(session, review.destination_id)
    previous_status = review.status
    _remove_counted_rating(review, stats)
    review.conflict_declared = conflict_declared
    if review.status == ReviewStatus.PUBLISHED:
        _add_published_rating(session, review, stats)
    review.version += 1
    review.updated_at = now_utc()

    decision = (
        ModerationDecision.SET_CONFLICT
        if conflict_declared
        else ModerationDecision.CLEAR_CONFLICT
    )
    session.add(
        ModerationActionRecord(
            review_id=review.id,
            actor_user_id=actor_user_id,
            decision=decision,
            previous_status=previous_status,
            new_status=review.status,
            reason_code=reason_code,
            note=note,
        )
    )
    session.add(
        OutboxEvent(
            topic="review.conflict_changed",
            aggregate_id=review.id,
            payload={
                "review_id": str(review.id),
                "destination_id": str(review.destination_id),
                "conflict_declared": conflict_declared,
                "version": review.version,
            },
        )
    )
    return review


def withdraw_review(session: Session, review_id: uuid.UUID, expected_version: int) -> Review:
    review = _lock_review(session, review_id)
    if review.version != expected_version:
        raise ReviewConflict("review version changed")
    if review.status in {ReviewStatus.WITHDRAWN, ReviewStatus.DELETED}:
        return review
    stats = _lock_stats(session, review.destination_id)
    _remove_counted_rating(review, stats)
    review.status = ReviewStatus.WITHDRAWN
    review.rating_eligibility = RatingEligibility.INELIGIBLE_REMOVED
    review.withdrawn_at = now_utc()
    review.updated_at = now_utc()
    review.version += 1
    session.add(
        OutboxEvent(
            topic="review.withdrawn",
            aggregate_id=review.id,
            payload={"review_id": str(review.id), "destination_id": str(review.destination_id)},
        )
    )
    return review


def full_guest_recompute(session: Session, destination_id: uuid.UUID) -> tuple[int, int]:
    result = session.execute(
        select(func.coalesce(func.sum(Review.counted_rating), 0), func.count(Review.id)).where(
            Review.destination_id == destination_id,
            Review.author_user_id.is_(None),
            Review.status == ReviewStatus.PUBLISHED,
            Review.counted_rating.is_not(None),
        )
    ).one()
    return int(result[0]), int(result[1])


def encode_cursor(published_at: datetime, review_id: uuid.UUID) -> str:
    raw = f"{published_at.isoformat()}|{review_id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

