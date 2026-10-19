"""The destination seed content satisfies the database constraints and PF 17 provenance rules."""

import re
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from app.models import AdvisorySeverity, ContactKind, GuideCategory, SourceType

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from destination_seed_content import DESTINATIONS  # noqa: E402

PHONE = re.compile(r"^\+?[0-9][0-9 -]{2,30}$")  # ck_contact_phone_format
SEMESTER_SCOPE = {"Cox's Bazar", "Sajek Valley", "Sylhet", "Sundarbans", "Bandarban"}


def _records():
    for destination in DESTINATIONS:
        for group in ("guide_items", "advisories", "contacts"):
            for item in destination[group]:
                yield destination["key"], group, item


def test_the_five_semester_destinations_are_present_once() -> None:
    names = [d["name_en"] for d in DESTINATIONS]
    assert sorted(names) == sorted(SEMESTER_SCOPE)
    assert len({d["key"] for d in DESTINATIONS}) == len(DESTINATIONS)


@pytest.mark.parametrize("destination", DESTINATIONS, ids=lambda d: d["key"])
def test_destination_profile_fields(destination: dict) -> None:
    for field in ("name_bn", "name_en", "region_bn", "region_en"):
        assert 0 < len(destination[field]) <= 160
    for field in ("summary", "seasonality", "restrictions"):
        assert destination[f"{field}_bn"].strip() and destination[f"{field}_en"].strip()
    assert -90 <= Decimal(destination["latitude"]) <= 90
    assert -180 <= Decimal(destination["longitude"]) <= 180
    assert destination["guide_items"] and destination["advisories"] and destination["contacts"]


@pytest.mark.parametrize(("key", "group", "item"), list(_records()), ids=lambda v: v if isinstance(v, str) else "")
def test_every_record_has_provenance_and_fits_its_columns(key: str, group: str, item: dict) -> None:
    del key
    assert SourceType(item["source_type"])
    assert item["source_ref"].startswith("https://")
    assert 0 < len(item["publisher"]) <= 160
    assert 0 < len(item["licence"]) <= 160
    if group == "guide_items":
        assert GuideCategory(item["category"])
        assert 0 < len(item["title_bn"]) <= 160 and 0 < len(item["title_en"]) <= 160
        assert item["body_bn"].strip() and item["body_en"].strip()
    elif group == "advisories":
        assert AdvisorySeverity(item["severity"])
        assert 0 < len(item["title_bn"]) <= 160 and 0 < len(item["title_en"]) <= 160
        assert item["valid_until"] >= item["effective_on"]  # ck_advisory_validity_window
    else:
        assert ContactKind(item["kind"])
        assert PHONE.fullmatch(item["phone"]) and len(item["phone"]) <= 32
        assert 0 < len(item["name_bn"]) <= 160 and 0 < len(item["name_en"]) <= 160


def test_record_keys_are_unique_within_each_destination() -> None:
    for destination in DESTINATIONS:
        for group in ("guide_items", "advisories", "contacts"):
            keys = [item["key"] for item in destination[group]]
            assert len(keys) == len(set(keys)), (destination["key"], group)
