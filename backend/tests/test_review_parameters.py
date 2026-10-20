"""`GET /review-parameters` publishes exactly the rules `GuestReviewCreate` enforces."""

import pytest
from fastapi.testclient import TestClient

from app import review_parameters as rp
from app.db import get_session
from app.limits import limiter
from app.main import create_app
from app.models import ReviewCategory
from app.schemas import GuestReviewCreate


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    limiter.reset()


def _parameters() -> dict:
    application = create_app()
    application.dependency_overrides[get_session] = lambda: None
    response = TestClient(application).get("/api/v1/review-parameters")
    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("public")
    return response.json()


def test_seven_optional_categories_in_review_order() -> None:
    parameters = _parameters()
    assert [c["code"] for c in parameters["categories"]] == [c.value for c in ReviewCategory]
    assert all(c["required"] is False and (c["min"], c["max"]) == (1, 5) for c in parameters["categories"])
    food = next(c for c in parameters["categories"] if c["code"] == "FOOD")
    assert food["name"] == {"bn": "খাবার", "en": "Food"}
    assert food["prompt"]["en"]


def test_overall_rating_and_note_are_required() -> None:
    parameters = _parameters()
    assert parameters["overall_rating"] == {"required": True, "min": 1, "max": 5}
    assert parameters["note"] == {"field": "body", "required": True, "min_length": 20, "max_length": 6000}
    assert parameters["version"] == rp.PARAMETERS_VERSION


def test_published_limits_match_the_validation_schema() -> None:
    parameters = _parameters()
    fields = GuestReviewCreate.model_json_schema()["properties"]
    for key in ("note", "title", "display_name"):
        rule = parameters[key]
        schema = fields[rule["field"]]
        assert (schema["minLength"], schema["maxLength"]) == (rule["min_length"], rule["max_length"])
    overall = fields["overall_rating"]
    assert (overall["minimum"], overall["maximum"]) == (1, 5)
    choices = {
        "traveller_types": "TravellerType",
        "comfort_tiers": "ComfortTier",
        "languages": "ReviewLanguage",
    }
    definitions = GuestReviewCreate.model_json_schema()["$defs"]
    for key, enum_name in choices.items():
        assert [o["value"] for o in parameters[key]] == definitions[enum_name]["enum"]


def test_rating_rules_state_the_bayesian_prior() -> None:
    rules = _parameters()["rating_rules"]
    assert (rules["community_prior_mean"], rules["community_prior_weight"], rules["community_min_reviews"]) == (
        3.5,
        5,
        5,
    )


@pytest.mark.parametrize(
    ("rating_sum", "rating_count", "expected"),
    [(0, 0, None), (20, 4, None), (25, 5, (25 + 17.5) / 10), (40, 10, (40 + 17.5) / 15)],
)
def test_community_score(rating_sum: int, rating_count: int, expected: float | None) -> None:
    assert rp.community_score(rating_sum, rating_count) == expected
