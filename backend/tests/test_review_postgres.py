import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from receipts import new_receipt  # noqa: E402
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import get_session
from app.main import create_app
from app.models import (
    ComfortTier,
    Destination,
    DestinationCategoryStats,
    DestinationRatingStats,
    DestinationStatus,
    ModerationDecision,
    RatingEligibility,
    Review,
    ReviewCategory,
    ReviewLanguage,
    ReviewRevision,
    ReviewStatus,
    RevisionStatus,
    TravellerType,
    User,
    Verification,
)
from app.schemas import GuestReviewCreate
from app.services import (
    ReviewConflict,
    full_guest_category_recompute,
    full_guest_recompute,
    moderate_review,
    set_review_conflict,
    submit_guest_review,
    withdraw_review,
)

pytestmark = pytest.mark.integration


def _payload(destination_id: uuid.UUID, draft_id: uuid.UUID | None = None) -> GuestReviewCreate:
    return GuestReviewCreate(
        destination_id=destination_id,
        client_draft_id=draft_id or uuid.uuid4(),
        guest_scope_secret=secrets.token_urlsafe(32),
        receipt_secret=new_receipt(),
        guest_display_name="সাদিয়া রহমান",
        language="BN",
        traveller_type="FAMILY",
        comfort_tier="STANDARD",
        visit_month=date(2026, 9, 1),
        title="পরিবার নিয়ে ভালো অভিজ্ঞতা",
        body="যাতায়াত সহজ ছিল এবং স্থানীয় মানুষের সহযোগিতা খুব ভালো পেয়েছি।",
        overall_rating=4,
        consent_version="2026-10-01",
    )


def _seed(session):
    destination = Destination(
        status=DestinationStatus.PUBLISHED,
        name_bn="সাজেক ভ্যালি",
        name_en="Sajek Valley",
    )
    moderator = User(email=f"moderator-{uuid.uuid4()}@example.test", display_name="Moderator")
    session.add_all([destination, moderator])
    session.commit()
    return destination, moderator


def test_guest_vertical_slice_and_retry_deduplication(postgres_session) -> None:
    destination, moderator = _seed(postgres_session)
    payload = _payload(destination.id)

    first = submit_guest_review(postgres_session, payload)
    postgres_session.commit()
    duplicate = submit_guest_review(postgres_session, payload)
    postgres_session.commit()

    assert duplicate.review.id == first.review.id
    assert duplicate.duplicate_recovered is True
    assert postgres_session.scalar(select(Review).where(Review.id == first.review.id)) is not None

    published = moderate_review(
        postgres_session,
        review_id=first.review.id,
        actor_user_id=moderator.id,
        expected_version=1,
        decision=ModerationDecision.PUBLISH,
        reason_code="APPROVED",
        note=None,
    )
    postgres_session.commit()

    stats = postgres_session.get(DestinationRatingStats, destination.id)
    assert published.status == ReviewStatus.PUBLISHED
    assert (stats.guest_rating_sum, stats.guest_rating_count) == (4, 1)
    assert full_guest_recompute(postgres_session, destination.id) == (4, 1)
    application = create_app()
    application.dependency_overrides[get_session] = lambda: postgres_session
    response = TestClient(application).get(f"/api/v1/destinations/{destination.id}/reviews")
    assert response.status_code == 200
    feed = response.json()
    assert [item["id"] for item in feed["items"]] == [str(published.id)]
    assert feed["guest_rating_average"] == 4.0
    assert feed["guest_rating_count"] == 1


def test_concurrent_publish_counts_once(postgres_session) -> None:
    destination, moderator = _seed(postgres_session)
    created = submit_guest_review(postgres_session, _payload(destination.id))
    postgres_session.commit()
    database_url = postgres_session.get_bind().url.render_as_string(hide_password=False)
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def publish_once() -> str:
        with factory() as session:
            try:
                moderate_review(
                    session,
                    review_id=created.review.id,
                    actor_user_id=moderator.id,
                    expected_version=1,
                    decision=ModerationDecision.PUBLISH,
                    reason_code="APPROVED",
                    note=None,
                )
                session.commit()
                return "published"
            except ReviewConflict:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: publish_once(), range(2)))

    postgres_session.expire_all()
    stats = postgres_session.get(DestinationRatingStats, destination.id)
    assert sorted(outcomes) == ["conflict", "published"]
    assert (stats.guest_rating_sum, stats.guest_rating_count) == (4, 1)
    engine.dispose()


@settings(
    max_examples=25,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    actions=st.lists(
        st.sampled_from(["publish", "hide", "withdraw", "restore"]),
        min_size=1,
        max_size=30,
    )
)
def test_random_rating_transitions_equal_full_recompute(postgres_session, actions) -> None:
    destination, moderator = _seed(postgres_session)
    payload = _payload(destination.id).model_copy(
        update={"category_ratings": {ReviewCategory.FOOD: 4, ReviewCategory.VALUE: 2}}
    )
    created = submit_guest_review(postgres_session, payload)
    postgres_session.commit()

    for action in actions:
        review = postgres_session.get(Review, created.review.id)
        if action == "publish" and review.status == ReviewStatus.PENDING:
            moderate_review(
                postgres_session,
                review_id=review.id,
                actor_user_id=moderator.id,
                expected_version=review.version,
                decision=ModerationDecision.PUBLISH,
                reason_code="PROPERTY_TEST",
                note=None,
            )
        elif action == "hide" and review.status == ReviewStatus.PUBLISHED:
            moderate_review(
                postgres_session,
                review_id=review.id,
                actor_user_id=moderator.id,
                expected_version=review.version,
                decision=ModerationDecision.HIDE,
                reason_code="PROPERTY_TEST",
                note=None,
            )
        elif action == "restore" and review.status == ReviewStatus.HIDDEN:
            moderate_review(
                postgres_session,
                review_id=review.id,
                actor_user_id=moderator.id,
                expected_version=review.version,
                decision=ModerationDecision.RESTORE,
                reason_code="PROPERTY_TEST",
                note=None,
            )
        elif action == "withdraw" and review.status not in {
            ReviewStatus.WITHDRAWN,
            ReviewStatus.DELETED,
        }:
            withdraw_review(postgres_session, review.id, review.version)
        postgres_session.commit()
        stats = postgres_session.get(DestinationRatingStats, destination.id)
        assert (stats.guest_rating_sum, stats.guest_rating_count) == full_guest_recompute(
            postgres_session, destination.id
        )
        category_rows = postgres_session.scalars(
            select(DestinationCategoryStats).where(
                DestinationCategoryStats.destination_id == destination.id,
                DestinationCategoryStats.rating_count > 0,
            )
        )
        assert {
            row.category: (row.rating_sum, row.rating_count) for row in category_rows
        } == full_guest_category_recompute(postgres_session, destination.id)


def test_conflict_flag_uses_locked_rating_delta(postgres_session) -> None:
    destination, moderator = _seed(postgres_session)
    member = User(email=f"member-{uuid.uuid4()}@example.test", display_name="Verified Member")
    postgres_session.add(member)
    postgres_session.flush()
    postgres_session.add(
        Verification(
            user_id=member.id,
            verification_type="VERIFIED_MEMBER",
            status="APPROVED",
            method="TEST_FIXTURE",
        )
    )
    review = Review(
        destination_id=destination.id,
        author_user_id=member.id,
        client_draft_id=uuid.uuid4(),
        status=ReviewStatus.PENDING,
        rating_eligibility=RatingEligibility.NOT_EVALUATED,
        overall_rating=5,
        visit_month=date(2026, 9, 1),
    )
    postgres_session.add(review)
    postgres_session.flush()
    revision = ReviewRevision(
        review_id=review.id,
        sequence=1,
        status=RevisionStatus.PENDING,
        language=ReviewLanguage.BN,
        traveller_type=TravellerType.SOLO,
        comfort_tier=ComfortTier.STANDARD,
        title="নিরাপদ ও পরিচ্ছন্ন",
        body="স্থানটি পরিচ্ছন্ন ছিল এবং যাতায়াতের নির্দেশনা যথেষ্ট পরিষ্কার ছিল।",
        overall_rating=5,
        consent_version="2026-10-01",
    )
    postgres_session.add(revision)
    postgres_session.flush()
    review.current_revision_id = revision.id
    postgres_session.commit()

    moderate_review(
        postgres_session,
        review_id=review.id,
        actor_user_id=moderator.id,
        expected_version=1,
        decision=ModerationDecision.PUBLISH,
        reason_code="APPROVED",
        note=None,
    )
    postgres_session.commit()
    stats = postgres_session.get(DestinationRatingStats, destination.id)
    assert (stats.community_rating_sum, stats.community_rating_count) == (5, 1)

    set_review_conflict(
        postgres_session,
        review_id=review.id,
        actor_user_id=moderator.id,
        expected_version=2,
        conflict_declared=True,
        reason_code="OWNER_CONFLICT",
        note=None,
    )
    postgres_session.commit()
    assert review.counted_rating is None
    assert review.rating_eligibility == RatingEligibility.INELIGIBLE_CONFLICT
    assert (stats.community_rating_sum, stats.community_rating_count) == (0, 0)

    set_review_conflict(
        postgres_session,
        review_id=review.id,
        actor_user_id=moderator.id,
        expected_version=3,
        conflict_declared=False,
        reason_code="CONFLICT_CLEARED",
        note=None,
    )
    postgres_session.commit()
    assert review.counted_rating == 5
    assert review.rating_eligibility == RatingEligibility.ELIGIBLE
    assert (stats.community_rating_sum, stats.community_rating_count) == (5, 1)

