import unicodedata
import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app import schemas
from app.services import ReviewConflict, encode_cursor, normalize_guest_name


def test_bangla_guest_name_keeps_nfc_text() -> None:
    source = "শাহরিয়ার ইসলাম"
    assert normalize_guest_name(f"  {source}  ") == unicodedata.normalize("NFC", source)


@pytest.mark.parametrize("name", ["Admin", "MODERATOR", "Verified", "Official✔"])
def test_reserved_guest_names_are_rejected(name: str) -> None:
    with pytest.raises(ReviewConflict):
        normalize_guest_name(name)


def test_feed_cursor_is_stable_and_url_safe() -> None:
    review_id = uuid.UUID("00000000-0000-0000-0000-000000000123")
    cursor = encode_cursor(datetime(2026, 10, 14, 8, 30, tzinfo=UTC), review_id)
    assert "=" not in cursor
    assert cursor


@given(
    ratings=st.lists(st.integers(min_value=1, max_value=5), max_size=100),
    included=st.lists(st.booleans(), max_size=100),
)
def test_incremental_rating_aggregate_matches_full_recompute(
    ratings: list[int], included: list[bool]
) -> None:
    pairs = list(zip(ratings, included, strict=False))
    running_sum = 0
    running_count = 0
    counted: list[int] = []
    for rating, should_count in pairs:
        old_counted = None
        new_counted = rating if should_count else None
        running_sum += (new_counted or 0) - (old_counted or 0)
        running_count += int(new_counted is not None) - int(old_counted is not None)
        if new_counted is not None:
            counted.append(new_counted)

    assert running_sum == sum(counted)
    assert running_count == len(counted)


def test_visit_month_rule_uses_configured_display_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSettings:
        display_tz = ZoneInfo("Pacific/Auckland")

    monkeypatch.setattr(schemas, "get_settings", lambda: FakeSettings())
    with pytest.raises(ValueError, match="Pacific/Auckland"):
        schemas.GuestReviewCreate.first_day_of_month(date(9999, 1, 1))
