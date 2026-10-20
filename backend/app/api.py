import base64
import logging
import uuid
from datetime import UTC, datetime
from typing import NoReturn

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from app import abuse
from app.abuse import CounterSessions
from app.client_address import network_digest, trusted_client_address
from app.config import get_settings
from app.db import get_session
from app.destination_api import public_cache_headers
from app.errors import ApiError
from app.guest_services import guest_visit_stats, register_guest_visit
from app.limits import guest_submit_limit, guest_visit_limit, limiter, receipt_limit
from app.models import (
    DestinationRatingStats,
    ModerationDecision,
    PlatformRole,
    RatingAudience,
    Review,
    ReviewRevision,
    ReviewStatus,
    User,
    UserPlatformRole,
)
from app.schemas import (
    ConflictFlagRequest,
    GuestReviewCreate,
    GuestReviewCreated,
    GuestVisitRequest,
    GuestVisitResponse,
    GuestVisitStats,
    HealthResponse,
    ModerationQueueItem,
    ModerationRequest,
    ModerationResult,
    PublicReview,
    ReceiptStatus,
    ReceiptStatusRequest,
    ReviewFeed,
    WithdrawRequest,
)
from app.services import (
    ReviewError,
    category_averages,
    encode_cursor,
    find_recoverable_draft,
    moderate_review,
    rejection_details,
    revision_category_ratings,
    set_review_conflict,
    submit_guest_review,
    verify_receipt,
    withdraw_review,
)
from app.turnstile import ACTION_GUEST_REVIEW, TurnstileDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


def _raise_service_error(error: Exception) -> NoReturn:
    if isinstance(error, ReviewError):
        raise ApiError(error.code) from error
    raise error


def require_staff(
    x_test_staff_id: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    settings = get_settings()
    if settings.is_production or not settings.allow_test_staff_header:
        raise ApiError("STAFF_AUTH_NOT_CONFIGURED")
    if x_test_staff_id is None:
        raise ApiError("AUTH_REQUIRED")
    try:
        user_id = uuid.UUID(x_test_staff_id)
    except ValueError as error:
        raise ApiError("AUTH_REQUIRED") from error

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
        raise ApiError("FORBIDDEN")
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
        logger.exception("readiness check failed")
        raise ApiError("SERVICE_UNAVAILABLE", headers={"Retry-After": "5"}) from error
    return HealthResponse(status="ok")


@router.post(
    "/reviews/guest",
    response_model=GuestReviewCreated,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(guest_submit_limit)
def create_guest_review(
    request: Request,
    response: Response,
    payload: GuestReviewCreate,
    sessions: CounterSessions,
    verify_challenge: TurnstileDep,
    session: Session = Depends(get_session),
) -> GuestReviewCreated:
    """Order of checks (API.md 5.2, PF 14.4)."""
    settings = get_settings()
    try:
        # 1-2. Schema and receipt format are validated; a recoverable draft returns here,
        #      free of charge: no challenge, no counters.
        recovered = find_recoverable_draft(session, payload)
        if recovered is not None:
            response.status_code = status.HTTP_200_OK
            return GuestReviewCreated(
                review_id=recovered.id,
                status=recovered.status,
                version=recovered.version,
                duplicate_recovered=True,
            )
        # 3. Idempotency-Key replay: WP4.
        # Emergency switch: stop new Guest writes before spending a challenge.
        abuse.ensure_guest_writes_allowed(settings)
        # 4. Turnstile (hostname and action checked; single use).
        address = trusted_client_address(request)
        verify_challenge(
            payload.turnstile_token,
            action=ACTION_GUEST_REVIEW,
            remote_address=str(address) if address else None,
        )
        # 5-6. Durable counters commit on their own before the limits and ceilings are checked.
        abuse.enforce(
            sessions,
            abuse.guest_submit_checks(
                settings, abuse.scope_key(payload.guest_scope_secret), network_digest(request)
            ),
        )
        abuse.check_pending_ceilings(session, payload.destination_id)
        # 7. Business transaction.
        result = submit_guest_review(session, payload)
        session.commit()
    except ReviewError as error:
        session.rollback()
        _raise_service_error(error)
    if result.duplicate_recovered:
        response.status_code = status.HTTP_200_OK
    return GuestReviewCreated(
        review_id=result.review.id,
        status=result.review.status,
        version=result.review.version,
        duplicate_recovered=result.duplicate_recovered,
    )


@router.post("/guest-visits", response_model=GuestVisitResponse)
@limiter.limit(guest_visit_limit)
def create_guest_visit(
    request: Request,
    payload: GuestVisitRequest,
    sessions: CounterSessions,
    session: Session = Depends(get_session),
) -> GuestVisitResponse:
    """Stable "Guest #N" for this device. The guest's name never reaches the server."""
    abuse.enforce(sessions, abuse.guest_visit_checks(get_settings(), network_digest(request)))
    guest_number, total = register_guest_visit(session, payload.guest_scope_secret)
    session.commit()
    return GuestVisitResponse(guest_number=guest_number, total_guests=total)


@router.get("/guest-visits/stats", response_model=GuestVisitStats)
@limiter.limit("60/minute")
def guest_visits_stats(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> GuestVisitStats:
    total, today = guest_visit_stats(session)
    response.headers.update(public_cache_headers())
    return GuestVisitStats(total_guests=total, guests_today=today)


@router.get("/staff/moderation/reviews", response_model=list[ModerationQueueItem])
def moderation_queue(
    staff: User = Depends(require_staff),
    session: Session = Depends(get_session),
) -> list[ModerationQueueItem]:
    del staff
    rows = session.execute(
        select(Review, ReviewRevision)
        .join(ReviewRevision, ReviewRevision.id == Review.current_revision_id)
        .where(Review.status.in_([ReviewStatus.PENDING, ReviewStatus.UNDER_REVIEW]))
        .order_by(Review.created_at.asc(), Review.id.asc())
        .limit(100)
    ).all()
    categories = revision_category_ratings(session, [revision.id for _, revision in rows])
    return [
        ModerationQueueItem(
            review_id=review.id,
            status=review.status,
            version=review.version,
            counted_rating=review.counted_rating,
            destination_id=review.destination_id,
            guest_display_name=review.guest_display_name,
            overall_rating=review.overall_rating,
            title=revision.title,
            body=revision.body,
            category_ratings=categories[revision.id],
            created_at=review.created_at,
        )
        for review, revision in rows
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
    decision = ModerationDecision(payload.decision)
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
    except ReviewError as error:
        session.rollback()
        _raise_service_error(error)


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
    except ReviewError as error:
        session.rollback()
        _raise_service_error(error)


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded).decode("utf-8")
        timestamp, review_id = raw.rsplit("|", 1)
        moment = datetime.fromisoformat(timestamp)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return moment, uuid.UUID(review_id)
    except (ValueError, UnicodeDecodeError) as error:
        raise ApiError("INVALID_CURSOR") from error


@router.get("/destinations/{destination_id}/reviews", response_model=ReviewFeed)
@limiter.limit("60/minute")
def public_reviews(
    request: Request,
    response: Response,
    destination_id: uuid.UUID,
    after: str | None = Query(default=None, max_length=200),
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
    categories = revision_category_ratings(session, [revision.id for _, revision in rows])
    items = [
        PublicReview(
            id=review.id,
            guest_display_name=review.guest_display_name,
            status=review.status,
            overall_rating=review.overall_rating,
            published_at=review.published_at,
            title=revision.title,
            body=revision.body,
            category_ratings=categories[revision.id],
        )
        for review, revision in rows
        if review.published_at is not None
    ]
    next_cursor = None
    if has_more and rows:
        last_review = rows[-1][0]
        if last_review.published_at is not None:
            next_cursor = encode_cursor(last_review.published_at, last_review.id)
    stats = session.get(DestinationRatingStats, destination_id)
    guest_count = stats.guest_rating_count if stats else 0
    guest_average = (
        stats.guest_rating_sum / guest_count if stats is not None and guest_count else None
    )
    response.headers.update(public_cache_headers())
    return ReviewFeed(
        items=items,
        next_cursor=next_cursor,
        guest_rating_average=guest_average,
        guest_rating_count=guest_count,
        guest_category_averages=category_averages(session, [destination_id]).get(
            (destination_id, RatingAudience.GUEST), []
        ),
    )


_RECEIPT_FAILURE_CODES = {"RECEIPT_NOT_FOUND", "INVALID_RECEIPT_FORMAT"}


def _receipt_status(session: Session, review: Review) -> ReceiptStatus:
    details = rejection_details(session, review)
    return ReceiptStatus(
        review_id=review.id,
        status=review.status,
        version=review.version,
        published_at=review.published_at,
        decision_reason=details.decision_reason,
        appeal_deadline=details.appeal_deadline,
    )


def _guard_receipt_operation(
    request: Request, sessions: CounterSessions, receipt_secret: str
) -> tuple[bytes, bytes]:
    """Progressive delay after repeated failures, then the per-receipt and per-network limits."""
    settings = get_settings()
    receipt, network = abuse.receipt_key(receipt_secret), network_digest(request)
    abuse.guard_receipt_failures(sessions, receipt, network)
    abuse.enforce(sessions, abuse.receipt_op_checks(settings, receipt, network))
    return receipt, network


@router.post("/review-receipts/status", response_model=ReceiptStatus)
@limiter.limit(receipt_limit)
def receipt_status(
    request: Request,
    payload: ReceiptStatusRequest,
    sessions: CounterSessions,
    session: Session = Depends(get_session),
) -> ReceiptStatus:
    receipt, network = _guard_receipt_operation(request, sessions, payload.receipt_secret)
    try:
        review = verify_receipt(session, payload.review_id, payload.receipt_secret)
        result = _receipt_status(session, review)
        session.commit()  # persists a re-digest under the current key after rotation
    except ReviewError as error:
        session.rollback()
        if error.code in _RECEIPT_FAILURE_CODES:
            abuse.record_receipt_failure(sessions, receipt, network)
        _raise_service_error(error)
    return result


@router.post("/reviews/{review_id}/withdraw", response_model=ReceiptStatus)
@limiter.limit(receipt_limit)
def withdraw_guest_review(
    request: Request,
    review_id: uuid.UUID,
    payload: WithdrawRequest,
    sessions: CounterSessions,
    session: Session = Depends(get_session),
) -> ReceiptStatus:
    receipt, network = _guard_receipt_operation(request, sessions, payload.receipt_secret)
    try:
        verify_receipt(session, review_id, payload.receipt_secret)
        review = withdraw_review(session, review_id, payload.expected_version)
        result = _receipt_status(session, review)
        session.commit()
    except ReviewError as error:
        session.rollback()
        if error.code in _RECEIPT_FAILURE_CODES:
            abuse.record_receipt_failure(sessions, receipt, network)
        _raise_service_error(error)
    return result
