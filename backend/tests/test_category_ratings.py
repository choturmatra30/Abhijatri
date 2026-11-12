"""Seven category ratings (Review.md 3.1, amendment A2): validation, storage and aggregates."""

import secrets
import uuid
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from receipts import new_receipt
from sqlalchemy import select

from app.api import require_staff
from app.db import get_session
from app.main import create_app
from app.models import (
    Destination,
    DestinationCategoryStats,
    DestinationStatus,
    ModerationDecision,
    RatingAudience,
    Review,
    ReviewCategory,
    ReviewCategoryRating,
    ReviewStatus,
    User,
)
from app.schemas import GuestReviewCreate
from app.services import (
    full_guest_category_recompute,
    moderate_review,
    submit_guest_review,
    withdraw_review,
)

CATEGORIES = {"CLEANLINESS": 3, "FOOD": 4, "SAFETY_PERCEPTION": 5}
SEVEN = {c.value: 4 for c in ReviewCategory}


def _fields(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "destination_id": uuid.uuid4(),
        "client_draft_id": uuid.uuid4(),
        "guest_scope_secret": secrets.token_urlsafe(32),
        "receipt_secret": new_receipt(),
        "guest_display_name": "সাদিয়া রহমান",
        "language": "BN",
        "traveller_type": "FAMILY",
        "comfort_tier": "STANDARD",
        "visit_month": date(2026, 9, 1),
        "title": "পরিবার নিয়ে ভালো অভিজ্ঞতা",
        "body": "যাতায়াত সহজ ছিল এবং স্থানীয় মানুষের সহযোগিতা খুব ভালো পেয়েছি।",
        "overall_rating": 4,
        "consent_version": "2026-10-01",
    }
    fields.update(overrides)
    return fields


# ---- schema (no database) ----


def test_category_ratings_are_required() -> None:
    with pytest.raises(ValidationError):
        GuestReviewCreate(**_fields())


@pytest.mark.parametrize("ratings", [{}, CATEGORIES, {c.value: 5 for c in list(ReviewCategory)[:6]}])
def test_fewer_than_seven_categories_are_refused(ratings: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="all seven"):
        GuestReviewCreate(**_fields(category_ratings=ratings))


def test_valid_category_ratings_are_kept_as_enum_keys() -> None:
    payload = GuestReviewCreate(**_fields(category_ratings=SEVEN, overall_rating=None))
    assert payload.category_ratings == {c: SEVEN[c.value] for c in ReviewCategory}


@pytest.mark.parametrize(
    ("scores", "expected"),
    [
        ([5, 5, 5, 5, 4, 4, 4], 5),  # 32 / 7 = 4.57
        ([5, 5, 5, 4, 4, 4, 4], 4),  # 31 / 7 = 4.43
        ([3, 3, 3, 3, 3, 3, 3], 3),
        ([1, 1, 1, 1, 1, 1, 1], 1),
        ([5, 5, 5, 5, 5, 5, 5], 5),
        ([4, 4, 4, 4, 4, 3, 3], 4),  # 26 / 7 = 3.71
        ([4, 4, 3, 3, 3, 3, 3], 3),  # 23 / 7 = 3.29
        ([5, 4, 4, 4, 3, 3, 3], 4),  # 26 / 7
        ([5, 1, 1, 1, 1, 1, 1], 2),  # 11 / 7 = 1.57
    ],
)
def test_overall_is_the_rounded_mean_of_the_seven(scores: list[int], expected: int) -> None:
    ratings = {c.value: score for c, score in zip(ReviewCategory, scores, strict=True)}
    assert GuestReviewCreate(**_fields(category_ratings=ratings, overall_rating=None)).overall_rating == expected


def test_a_sent_overall_that_differs_from_the_calculated_one_is_refused() -> None:
    with pytest.raises(ValidationError, match="calculated"):
        GuestReviewCreate(**_fields(category_ratings=SEVEN, overall_rating=1))
    assert GuestReviewCreate(**_fields(category_ratings=SEVEN, overall_rating=4)).overall_rating == 4


def test_all_seven_categories_are_accepted() -> None:
    every = {category.value: 5 for category in ReviewCategory}
    assert len(GuestReviewCreate(**_fields(category_ratings=every, overall_rating=None)).category_ratings or {}) == 7


@pytest.mark.parametrize(
    "ratings",
    [{"FOOD": 0}, {"FOOD": 6}, {"FOOD": 2.5}, {"WIFI": 4}, {"food": 4}],
)
def test_invalid_category_ratings_are_rejected(ratings: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        GuestReviewCreate(**_fields(category_ratings=ratings))


def test_unknown_category_is_a_field_error_over_http() -> None:
    application = create_app()
    application.dependency_overrides[get_session] = lambda: None
    body = _fields(category_ratings={"WIFI": 4})
    body = {key: str(value) if isinstance(value, uuid.UUID | date) else value for key, value in body.items()}
    response = TestClient(application).post("/api/v1/reviews/guest", json=body)
    assert response.status_code == 422
    fields = {error["field"] for error in response.json()["error"]["field_errors"]}
    assert any(field.startswith("category_ratings") for field in fields)


# ---- PostgreSQL ----


def _legacy(**overrides: Any) -> GuestReviewCreate:
    """A review written before 2026-11-11, with fewer than seven categories (validation skipped on purpose).

    Such reviews still exist and still feed the per-category averages, so those paths keep their tests.
    """
    fields = _fields(**overrides)
    ratings = fields.get("category_ratings")
    if ratings is not None:
        fields["category_ratings"] = {ReviewCategory(name): score for name, score in ratings.items()}
    return GuestReviewCreate.model_construct(**fields)


def _seed(session) -> tuple[Destination, User]:
    destination = Destination(status=DestinationStatus.PUBLISHED, name_bn="সাজেক", name_en="Sajek")
    moderator = User(email=f"moderator-{uuid.uuid4()}@example.test", display_name="Moderator")
    session.add_all([destination, moderator])
    session.commit()
    return destination, moderator


def _decide(session, review: Review, moderator: User, decision: ModerationDecision) -> None:
    moderate_review(
        session,
        review_id=review.id,
        actor_user_id=moderator.id,
        expected_version=review.version,
        decision=decision,
        reason_code="TEST",
        note=None,
    )
    session.commit()


def _guest_stats(session, destination_id: uuid.UUID) -> dict[ReviewCategory, tuple[int, int]]:
    session.expire_all()
    rows = session.scalars(
        select(DestinationCategoryStats).where(
            DestinationCategoryStats.destination_id == destination_id,
            DestinationCategoryStats.audience == RatingAudience.GUEST,
            DestinationCategoryStats.rating_count > 0,
        )
    )
    return {row.category: (row.rating_sum, row.rating_count) for row in rows}


@pytest.mark.integration
def test_category_rows_follow_every_rating_transition(postgres_session) -> None:
    destination, moderator = _seed(postgres_session)
    created = submit_guest_review(
        postgres_session,
        _legacy(destination_id=destination.id, category_ratings=CATEGORIES),
    )
    postgres_session.commit()
    review = created.review

    rows = postgres_session.scalars(
        select(ReviewCategoryRating).where(ReviewCategoryRating.revision_id == review.current_revision_id)
    ).all()
    assert {row.category.value: row.rating for row in rows} == CATEGORIES
    # Pending: stored, but counted nowhere (Review.md 12.2).
    assert _guest_stats(postgres_session, destination.id) == {}

    _decide(postgres_session, review, moderator, ModerationDecision.PUBLISH)
    expected = {ReviewCategory(name): (score, 1) for name, score in CATEGORIES.items()}
    assert _guest_stats(postgres_session, destination.id) == expected
    assert full_guest_category_recompute(postgres_session, destination.id) == expected

    _decide(postgres_session, review, moderator, ModerationDecision.HIDE)
    assert _guest_stats(postgres_session, destination.id) == {}

    _decide(postgres_session, review, moderator, ModerationDecision.RESTORE)
    assert _guest_stats(postgres_session, destination.id) == expected

    withdraw_review(postgres_session, review.id, review.version)
    postgres_session.commit()
    assert review.status == ReviewStatus.WITHDRAWN
    assert _guest_stats(postgres_session, destination.id) == {}
    assert full_guest_category_recompute(postgres_session, destination.id) == {}


@pytest.mark.integration
def test_rejected_review_never_counts_categories(postgres_session) -> None:
    destination, moderator = _seed(postgres_session)
    created = submit_guest_review(
        postgres_session,
        _legacy(destination_id=destination.id, category_ratings=CATEGORIES),
    )
    postgres_session.commit()
    _decide(postgres_session, created.review, moderator, ModerationDecision.REJECT)
    assert _guest_stats(postgres_session, destination.id) == {}


@pytest.mark.integration
def test_api_returns_category_ratings_and_averages(postgres_session) -> None:
    destination, moderator = _seed(postgres_session)
    for ratings in (CATEGORIES, {"FOOD": 2}, None):
        created = submit_guest_review(
            postgres_session,
            _legacy(destination_id=destination.id, category_ratings=ratings),
        )
        postgres_session.commit()
        _decide(postgres_session, created.review, moderator, ModerationDecision.PUBLISH)

    application = create_app()
    application.dependency_overrides[get_session] = lambda: postgres_session
    client = TestClient(application)

    response = client.get(f"/api/v1/destinations/{destination.id}/reviews")
    feed = response.json()
    assert sorted(len(item["category_ratings"]) for item in feed["items"]) == [0, 1, 3]
    # A guest's typed name is never public: only "Anonymous guest · tag" (owner, 22 Oct 2026).
    assert all(item["author_type"] == "GUEST" and "guest_display_name" not in item for item in feed["items"])
    assert "সাদিয়া রহমান" not in response.text
    averages = {row["category"]: row for row in feed["guest_category_averages"]}
    assert averages["FOOD"] == {"category": "FOOD", "average": 3.0, "count": 2}
    assert averages["CLEANLINESS"]["count"] == 1
    # Display order is the Review.md 3.1 order.
    assert [row["category"] for row in feed["guest_category_averages"]] == [
        "CLEANLINESS",
        "FOOD",
        "SAFETY_PERCEPTION",
    ]

    profile = client.get(f"/api/v1/destinations/{destination.id}").json()
    assert profile["guest_feedback"]["category_averages"] == feed["guest_category_averages"]
    assert profile["community_rating"]["category_averages"] == []
    (item,) = client.get("/api/v1/destinations").json()["items"]
    assert item["guest_feedback"]["category_averages"] == feed["guest_category_averages"]


@pytest.mark.integration
def test_moderation_queue_shows_the_full_review(postgres_session) -> None:
    destination, moderator = _seed(postgres_session)
    created = submit_guest_review(
        postgres_session,
        _legacy(destination_id=destination.id, category_ratings=CATEGORIES),
    )
    postgres_session.commit()

    application = create_app()
    application.dependency_overrides[get_session] = lambda: postgres_session
    application.dependency_overrides[require_staff] = lambda: moderator
    (item,) = TestClient(application).get("/api/v1/staff/moderation/reviews").json()
    assert item["review_id"] == str(created.review.id)
    assert item["title"] == "পরিবার নিয়ে ভালো অভিজ্ঞতা"
    assert item["guest_display_name"] == "সাদিয়া রহমান"
    assert item["category_ratings"] == CATEGORIES
