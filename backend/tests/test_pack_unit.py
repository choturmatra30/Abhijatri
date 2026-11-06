"""R14 offline packs: canonical hashing, versioning rules and freshness arithmetic (no database)."""

import base64
import hashlib
import json
import unicodedata
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from app.config import Settings
from app.destination_services import today_in_display_tz
from app.errors import CATALOGUE
from app.models import DestinationPackVersion
from app.offline.packs import (
    PACK_SCHEMA_VERSION,
    advisory_window,
    canonical_json,
    content_digest,
    needs_rebuild,
    pack_url,
    sha256_hex,
)
from app.offline.routes import if_none_match

NOW = datetime(2026, 11, 6, 6, 0, tzinfo=UTC)
CONTENT = "a" * 64
REBUILD = timedelta(hours=24)


def _row(**overrides: Any) -> DestinationPackVersion:
    values: dict[str, Any] = {
        "destination_id": uuid.uuid4(),
        "pack_version": 3,
        "content_version": CONTENT,
        "sha256": "b" * 64,
        "size_bytes": 10,
        "schema_version": PACK_SCHEMA_VERSION,
        "generated_at": NOW - timedelta(hours=1),
        "expires_at": NOW + timedelta(days=6),
        "body": b"{}",
    }
    values.update(overrides)
    return DestinationPackVersion(**values)


# ---- canonical JSON and hashes ----


def test_canonical_json_is_compact_sorted_and_keeps_bangla() -> None:
    assert canonical_json({"b": 1, "a": ["সাজেক", None]}) == '{"a":["সাজেক",null],"b":1}'.encode()


def test_canonical_json_refuses_nan() -> None:
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(),
    lambda children: st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=8), children, max_size=4),
    max_leaves=20,
)


@given(st.dictionaries(st.text(max_size=8), json_values, max_size=6))
def test_hash_does_not_depend_on_key_order(value: dict[str, Any]) -> None:
    reordered = dict(reversed(list(value.items())))
    assert sha256_hex(canonical_json(value)) == sha256_hex(canonical_json(reordered))
    assert json.loads(canonical_json(value)) == value


@given(st.text(alphabet=st.sampled_from("অআকখগঘঙচছজঝটঠডঢণতথদধনপফবভমযরলশষসহ়ািীুূৃেৈোৌ্ংঃঁ "), max_size=40))
def test_bangla_text_survives_byte_for_byte(text: str) -> None:
    nfc = unicodedata.normalize("NFC", text)
    assert json.loads(canonical_json({"t": nfc}).decode("utf-8"))["t"] == nfc


def test_sha256_and_content_digest_agree() -> None:
    body = canonical_json({"pack": 1})
    digest = sha256_hex(body)
    assert digest == hashlib.sha256(body).hexdigest()
    assert content_digest(digest) == "sha-256=:" + base64.b64encode(hashlib.sha256(body).digest()).decode() + ":"


def test_pack_url_names_the_version() -> None:
    destination = uuid.uuid4()
    assert pack_url(destination, 7) == f"/api/v1/destinations/{destination}/pack?version=7"


# ---- rebuild decision ----


def test_first_build_is_needed() -> None:
    assert needs_rebuild(None, CONTENT, NOW, rebuild_after=REBUILD)


def test_same_content_young_build_is_reused() -> None:
    assert not needs_rebuild(_row(), CONTENT, NOW, rebuild_after=REBUILD)


def test_changed_content_rebuilds() -> None:
    assert needs_rebuild(_row(), "c" * 64, NOW, rebuild_after=REBUILD)


def test_old_build_rebuilds_even_with_same_content() -> None:
    assert needs_rebuild(_row(generated_at=NOW - REBUILD), CONTENT, NOW, rebuild_after=REBUILD)
    assert not needs_rebuild(_row(generated_at=NOW - REBUILD + timedelta(seconds=1)), CONTENT, NOW, rebuild_after=REBUILD)


def test_expired_build_rebuilds() -> None:
    assert needs_rebuild(_row(expires_at=NOW), CONTENT, NOW, rebuild_after=timedelta(days=30))


def test_schema_change_rebuilds() -> None:
    assert needs_rebuild(_row(schema_version=PACK_SCHEMA_VERSION + 1), CONTENT, NOW, rebuild_after=REBUILD)


# ---- freshness arithmetic on the Dhaka calendar ----


def test_advisory_window_spans_the_pack_lifetime() -> None:
    assert advisory_window(date(2026, 11, 6), 7) == (date(2026, 11, 6), date(2026, 11, 13))


def test_pack_dates_use_the_dhaka_day() -> None:
    late_utc = datetime(2026, 11, 5, 20, 30, tzinfo=UTC)  # already 6 November in Dhaka
    assert today_in_display_tz(late_utc) == date(2026, 11, 6)
    assert advisory_window(today_in_display_tz(late_utc), 7)[0] == date(2026, 11, 6)


# ---- conditional requests ----


def test_if_none_match_uses_weak_comparison() -> None:
    assert if_none_match('"abc"', '"abc"')
    assert if_none_match('W/"abc"', '"abc"')
    assert if_none_match('"x", W/"abc"', '"abc"')
    assert if_none_match("*", '"abc"')
    assert not if_none_match('"abd"', '"abc"')
    assert not if_none_match(None, '"abc"')


# ---- configuration and error catalogue ----


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pack_max_age_days", 0),
        ("pack_max_age_days", 31),
        ("pack_rebuild_after_hours", 0),
        ("pack_rebuild_after_hours", 169),
        ("pack_review_snapshot_limit", -1),
        ("pack_review_snapshot_limit", 51),
    ],
)
def test_pack_settings_are_bounded(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="test", **{field: value})


def test_pack_settings_defaults() -> None:
    settings = Settings(app_env="test")
    assert (settings.pack_max_age_days, settings.pack_rebuild_after_hours, settings.pack_review_snapshot_limit) == (
        7,
        24,
        20,
    )


def test_pack_error_codes_are_catalogued() -> None:
    assert CATALOGUE["PACK_VERSION_SUPERSEDED"][0] == 409
    assert CATALOGUE["PACK_WITHDRAWN"][0] == 410
