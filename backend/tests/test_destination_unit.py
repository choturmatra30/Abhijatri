"""Pure-logic tests for destination services: advisory freshness, cursors, cache helpers."""

import uuid
from datetime import UTC, date, datetime

import pytest

from app.destination_api import _etag, _matches
from app.destination_services import (
    InvalidCursor,
    advisory_state,
    decode_destination_cursor,
    encode_destination_cursor,
    today_in_display_tz,
)
from app.schemas import DestinationList

TODAY = date(2026, 10, 20)


def _state(*, effective_on: date, valid_until: date, verified_on: date, stale_after_days: int = 30) -> str:
    return advisory_state(
        effective_on=effective_on,
        valid_until=valid_until,
        verified_on=verified_on,
        today=TODAY,
        stale_after_days=stale_after_days,
    )


def test_advisory_valid_through_its_last_day_is_current() -> None:
    assert _state(effective_on=date(2026, 10, 1), valid_until=TODAY, verified_on=TODAY) == "CURRENT"


def test_advisory_is_expired_the_day_after_valid_until() -> None:
    state = _state(effective_on=date(2026, 10, 1), valid_until=date(2026, 10, 19), verified_on=TODAY)
    assert state == "EXPIRED"


def test_advisory_before_its_effective_date_is_not_yet_effective() -> None:
    state = _state(effective_on=date(2026, 10, 21), valid_until=date(2026, 12, 1), verified_on=TODAY)
    assert state == "NOT_YET_EFFECTIVE"


@pytest.mark.parametrize(
    ("verified_on", "expected"),
    [
        (date(2026, 9, 20), "CURRENT"),  # exactly 30 days ago: still within the window
        (date(2026, 9, 19), "STALE"),  # 31 days ago
        (date(2026, 10, 25), "CURRENT"),  # verified date in the future never makes it stale
    ],
)
def test_advisory_staleness_threshold(verified_on: date, expected: str) -> None:
    state = _state(effective_on=date(2026, 9, 1), valid_until=date(2026, 12, 1), verified_on=verified_on)
    assert state == expected


def test_expired_wins_over_stale() -> None:
    state = _state(effective_on=date(2026, 1, 1), valid_until=date(2026, 6, 1), verified_on=date(2026, 1, 2))
    assert state == "EXPIRED"


def test_calendar_day_uses_dhaka_not_utc() -> None:
    # 20:30 UTC on 19 Oct is already 02:30 on 20 Oct in Asia/Dhaka (UTC+6).
    late_utc = datetime(2026, 10, 19, 20, 30, tzinfo=UTC)
    assert today_in_display_tz(late_utc) == date(2026, 10, 20)
    assert late_utc.date() == date(2026, 10, 19)


def test_destination_cursor_round_trips_names_containing_the_separator() -> None:
    destination_id = uuid.uuid4()
    cursor = encode_destination_cursor("Sylhet | Sreemangal", destination_id)
    assert decode_destination_cursor(cursor) == ("Sylhet | Sreemangal", destination_id)


@pytest.mark.parametrize("cursor", ["not-a-cursor", "", "bm8tc2VwYXJhdG9y", "Zm9vfG5vdC1hLXV1aWQ"])
def test_malformed_destination_cursor_is_rejected(cursor: str) -> None:
    with pytest.raises(InvalidCursor):
        decode_destination_cursor(cursor)


def test_etag_is_stable_for_equal_payloads_and_changes_with_content() -> None:
    first = DestinationList(items=[], next_cursor=None)
    same = DestinationList(items=[], next_cursor=None)
    other = DestinationList(items=[], next_cursor="abc")
    assert _etag(first) == _etag(same)
    assert _etag(first) != _etag(other)
    assert _etag(first).startswith('W/"')


def test_if_none_match_matching() -> None:
    etag = 'W/"abc"'
    assert _matches(etag, etag)
    assert _matches('W/"zzz", W/"abc"', etag)
    assert _matches("*", etag)
    assert not _matches('W/"other"', etag)
    assert not _matches(None, etag)
