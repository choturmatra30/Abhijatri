import base64
import hmac
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models import (
    DestinationRatingStats,
    ModerationDecision,
    PlatformRole,
    Review,
    ReviewReceipt,
    ReviewRevision,
    ReviewStatus,
    User,
    UserPlatformRole,
)
from app.schemas import (
    ConflictFlagRequest,
    GuestReviewCreate,
    GuestReviewCreated,
    HealthResponse,
    ModerationRequest,
    ModerationResult,
    PublicReview,
    ReceiptExchange,
    ReceiptStatus,
    ReviewFeed,
    WithdrawRequest,
)
from app.services import (
    ReviewConflict,
    ReviewForbidden,
    ReviewNotFound,
    encode_cursor,
    hash_secret,
    moderate_review,
    set_review_conflict,
    submit_guest_review,
    withdraw_review,
)

router = APIRouter(prefix="/api/v1")


def _raise_service_error(error: Exception) -> None:
    if isinstance(error, ReviewNotFound):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, ReviewForbidden):
        raise HTTPException(status_code=403, detail=str(error)) from error
    if isinstance(error, ReviewConflict):
        raise HTTPException(status_code=409, detail=str(error)) from error
    raise error


def require_staff(
    x_test_staff_id: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    settings = get_settings()
    if settings.app_env not in {"development", "test"}:
        raise HTTPException(status_code=501, detail="staff authentication adapter is not configured")
    if x_test_staff_id is None:
        raise HTTPException(status_code=401, detail="test staff identity required")
    try:
        user_id = uuid.UUID(x_test_staff_id)
    except ValueError as error:
        raise HTTPException(status_code=401, detail="invalid staff identity") from error

    now = datetime.now(UTC)
    user = session.scalar(
        select(User)
        .join(UserPlatformRole, UserPlatformRole.user_id == User.id)
        .join(PlatformRole, PlatformRole.id == UserPlatformRole.role_id)
        .where(
            User.id == user_id,
            PlatformRole.code.in_(["MODERATOR", "ADMINISTRATOR", "SUPER_ADMINISTRATOR"]),
            or_(UserPlatformRole.expires_at.is_(None), UserPlatformRole.expires_at > now),
        )
    )
    if user is None:
        raise HTTPException(status_code=403, detail="staff permission required")
    return user


@router.get("/health", response_model=HealthResponse, operation_id="health_get")
@router.head("/health", response_model=HealthResponse, operation_id="health_head")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=HealthResponse, operation_id="health_ready_get")
@router.head("/health/ready", response_model=HealthResponse, operation_id="health_ready_head")
def health_ready(session: Session = Depends(get_session)) -> HealthResponse:
    try:
        session.execute(text("SELECT 1"))
    except Exception as error:
        raise HTTPException(status_code=503, detail="database unavailable") from error
    return HealthResponse(status="ok")


@router.post(
    "/reviews/guest",
    response_model=GuestReviewCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_guest_review(
    payload: GuestReviewCreate,
    session: Session = Depends(get_session),
) -> GuestReviewCreated:
    try:
        result = submit_guest_review(session, payload)
        session.commit()
        return GuestReviewCreated(
            review_id=result.review.id,
            status=result.review.status,
            version=result.review.version,
            receipt_token=result.receipt_token,
            duplicate_recovered=result.duplicate_recovered,
        )
    except (ReviewNotFound, ReviewConflict, ReviewForbidden) as error:
        session.rollback()
        _raise_service_error(error)
        raise AssertionError("unreachable")


@router.get("/staff/moderation/reviews", response_model=list[ModerationResult])
def moderation_queue(
    staff: User = Depends(require_staff),
    session: Session = Depends(get_session),
) -> list[ModerationResult]:
    del staff
    reviews = session.scalars(
        select(Review)
        .where(Review.status.in_([ReviewStatus.PENDING, ReviewStatus.UNDER_REVIEW]))
        .order_by(Review.created_at.asc(), Review.id.asc())
        .limit(100)
    ).all()
    return [
        ModerationResult(
            review_id=review.id,
            status=review.status,
            version=review.version,
            counted_rating=review.counted_rating,
        )
        for review in reviews
    ]


@router.post(
    "/staff/moderation/reviews/{review_id}/decisions",
    response_model=ModerationResult,
)
def decide_review(
    review_id: uuid.UUID,
    payload: ModerationRequest,
    staff: User = Depends(require_staff),
    session: Session = Depends(get_session),
) -> ModerationResult:
    try:
        decision = ModerationDecision(payload.decision.upper())
    except ValueError as error:
        raise HTTPException(status_code=422, detail="unsupported moderation decision") from error
    try:
        review = moderate_review(
            session,
            review_id=review_id,
            actor_user_id=staff.id,
            expected_version=payload.expected_version,
            decision=decision,
            reason_code=payload.reason_code,
            note=payload.note,
        )
        session.commit()
        return ModerationResult(
            review_id=review.id,
            status=review.status,
            version=review.version,
            counted_rating=review.counted_rating,
        )
    except (ReviewNotFound, ReviewConflict, ReviewForbidden) as error:
        session.rollback()
        _raise_service_error(error)
        raise AssertionError("unreachable")


@router.put(
    "/staff/moderation/reviews/{review_id}/conflict",
    response_model=ModerationResult,
)
def change_review_conflict(
    review_id: uuid.UUID,
    payload: ConflictFlagRequest,
    staff: User = Depends(require_staff),
    session: Session = Depends(get_session),
) -> ModerationResult:
    try:
        review = set_review_conflict(
            session,
            review_id=review_id,
            actor_user_id=staff.id,
            expected_version=payload.expected_version,
            conflict_declared=payload.conflict_declared,
            reason_code=payload.reason_code,
            note=payload.note,
        )
        session.commit()
        return ModerationResult(
            review_id=review.id,
            status=review.status,
            version=review.version,
            counted_rating=review.counted_rating,
        )
    except (ReviewNotFound, ReviewConflict, ReviewForbidden) as error:
        session.rollback()
        _raise_service_error(error)
        raise AssertionError("unreachable")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded).decode("utf-8")
        timestamp, review_id = raw.rsplit("|", 1)
        return datetime.fromisoformat(timestamp), uuid.UUID(review_id)
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=422, detail="invalid cursor") from error


@router.get("/destinations/{destination_id}/reviews", response_model=ReviewFeed)
def public_reviews(
    destination_id: uuid.UUID,
    after: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    session: Session = Depends(get_session),
) -> ReviewFeed:
    statement = (
        select(Review, ReviewRevision)
        .join(ReviewRevision, ReviewRevision.id == Review.current_revision_id)
        .where(
            Review.destination_id == destination_id,
            Review.status == ReviewStatus.PUBLISHED,
            Review.published_at.is_not(None),
        )
        .order_by(Review.published_at.desc(), Review.id.desc())
        .limit(limit + 1)
    )
    if after:
        published_at, review_id = _decode_cursor(after)
        statement = statement.where(
            or_(
                Review.published_at < published_at,
                and_(Review.published_at == published_at, Review.id < review_id),
            )
        )
    rows = session.execute(statement).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [
        PublicReview(
            id=review.id,
            guest_display_name=review.guest_display_name,
            status=review.status,
            overall_rating=review.overall_rating,
            published_at=review.published_at,
            title=revision.title,
            body=revision.body,
        )
        for review, revision in rows
    ]
    next_cursor = None
    if has_more and rows:
        last_review = rows[-1][0]
        next_cursor = encode_cursor(last_review.published_at, last_review.id)
    stats = session.get(DestinationRatingStats, destination_id)
    guest_count = stats.guest_rating_count if stats else 0
    guest_average = (
        stats.guest_rating_sum / guest_count if stats is not None and guest_count else None
    )
    return ReviewFeed(
        items=items,
        next_cursor=next_cursor,
        guest_rating_average=guest_average,
        guest_rating_count=guest_count,
    )


def _verify_receipt(session: Session, review_id: uuid.UUID, raw_token: str) -> Review:
    receipts = session.scalars(
        select(ReviewReceipt).where(
            ReviewReceipt.review_id == review_id,
            ReviewReceipt.revoked_at.is_(None),
        )
    ).all()
    candidate_hash = hash_secret(raw_token)
    if not any(hmac.compare_digest(receipt.token_hash, candidate_hash) for receipt in receipts):
        raise HTTPException(status_code=404, detail="receipt not found")
    review = session.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="review not found")
    return review


@router.post("/review-receipts/exchange", response_model=ReceiptStatus)
def exchange_receipt(
    payload: ReceiptExchange,
    session: Session = Depends(get_session),
) -> ReceiptStatus:
    review = _verify_receipt(session, payload.review_id, payload.receipt_token)
    return ReceiptStatus(
        review_id=review.id,
        status=review.status,
        version=review.version,
        published_at=review.published_at,
    )


@router.post("/reviews/{review_id}/withdraw", response_model=ReceiptStatus)
def withdraw_guest_review(
    review_id: uuid.UUID,
    payload: WithdrawRequest,
    session: Session = Depends(get_session),
) -> ReceiptStatus:
    try:
        _verify_receipt(session, review_id, payload.receipt_token)
        review = withdraw_review(session, review_id, payload.expected_version)
        session.commit()
        return ReceiptStatus(
            review_id=review.id,
            status=review.status,
            version=review.version,
            published_at=review.published_at,
        )
    except (ReviewNotFound, ReviewConflict, ReviewForbidden) as error:
        session.rollback()
        _raise_service_error(error)
        raise AssertionError("unreachable")

