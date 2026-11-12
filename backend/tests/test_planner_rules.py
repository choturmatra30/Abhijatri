"""E01: the frozen cost-planner rules (Features/Cost-Planner.md) agree with the code and the hand examples.

Test IDs PLN-E01-01 to PLN-E01-07 are listed in Cost-Planner.md section 16. No database is needed.
"""

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest
from planner_oracle import estimate

from app.planner import rules as R

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "Features" / "Cost-Planner.md"
EXAMPLES = json.loads((Path(__file__).parent / "planner_examples.json").read_text(encoding="utf-8"))
CASES = EXAMPLES["examples"]
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def code_contract() -> dict:
    """The frozen constants exactly as the specification's JSON block states them."""
    return {
        "rules_version": R.RULES_VERSION,
        "season_factors": {k.value: str(v) for k, v in R.SEASON_FACTORS.items()},
        "weekend": [WEEKDAY_NAMES[i] for i in R.WEEKEND_WEEKDAYS],
        "confidence_weights": {
            "authority": str(R.W_AUTHORITY),
            "freshness": str(R.W_FRESHNESS),
            "reports": str(R.W_REPORTS),
            "agreement": str(R.W_AGREEMENT),
        },
        "authority": {k.value: str(v) for k, v in R.AUTHORITY.items()},
        "freshness": {"fresh": str(R.FRESHNESS_FRESH), "stale": str(R.FRESHNESS_STALE)},
        "reports_for_full_score": R.REPORTS_FOR_FULL_SCORE,
        "thresholds": {"high": str(R.HIGH_THRESHOLD), "medium": str(R.MEDIUM_THRESHOLD)},
        "refresh_months": {"official": R.REFRESH_MONTHS_OFFICIAL, "other": R.REFRESH_MONTHS_OTHER},
        "display_step": str(R.DISPLAY_STEP),
        "limits": {
            "party": [R.MIN_PARTY, R.MAX_PARTY],
            "days": [R.MIN_DAYS, R.MAX_DAYS],
            "meals_per_day": [R.MIN_MEALS_PER_DAY, R.MAX_MEALS_PER_DAY],
            "default_meals_per_day": R.DEFAULT_MEALS_PER_DAY,
        },
        "capacity_units": sorted(u.value for u in R.CAPACITY_UNITS),
        "units": {
            u.value: {
                "quantity": r.quantity.value,
                "period": r.period.value,
                "shared": r.shared,
                "season_scaled": r.season_scaled,
            }
            for u, r in R.UNIT_RULES.items()
        },
    }


def spec_contract() -> dict:
    text = SPEC.read_text(encoding="utf-8")
    block = re.search(r"```json planner-rules\n(.*?)\n```", text, re.S)
    assert block, "Features/Cost-Planner.md has no ```json planner-rules block"
    return json.loads(block.group(1))


# PLN-E01-01
def test_rule_constants_are_internally_valid() -> None:
    assert sum([R.W_AUTHORITY, R.W_FRESHNESS, R.W_REPORTS, R.W_AGREEMENT]) == Decimal(1)
    assert Decimal(0) < R.MEDIUM_THRESHOLD < R.HIGH_THRESHOLD <= Decimal(1)
    assert set(R.UNIT_RULES) == set(R.PricingUnit) and len(R.PricingUnit) == 8
    assert set(R.PricingUnit) >= R.CAPACITY_UNITS
    assert R.SEASON_FACTORS[R.SeasonBand.REGULAR] == Decimal("1.00")
    assert all(f >= Decimal("1.00") for f in R.SEASON_FACTORS.values())
    assert set(R.AUTHORITY) == set(R.SourceType)
    assert R.AUTHORITY[R.SourceType.OFFICIAL] > R.AUTHORITY[R.SourceType.VERIFIED_OPERATOR]
    assert R.AUTHORITY[R.SourceType.VERIFIED_OPERATOR] > R.AUTHORITY[R.SourceType.COMMUNITY_REPORT]
    assert R.FRESHNESS_STALE < R.FRESHNESS_FRESH
    assert R.RULES_VERSION.startswith("planner-rules-")
    for unit in R.CAPACITY_UNITS:
        assert R.UNIT_RULES[unit].quantity is R.Quantity.CEILING
    for rule in R.UNIT_RULES.values():
        if rule.period is R.Period.ONCE:
            assert not rule.season_scaled  # a single occurrence is never scaled


# PLN-E01-02
def test_specification_and_code_state_the_same_constants() -> None:
    assert spec_contract() == code_contract()


# PLN-E01-03
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_worked_example_matches_the_hand_calculation(case: dict) -> None:
    got, want = estimate(case), case["expect"]
    for key in ("total", "per_person", "display_total", "display_per_person"):
        for v in ("low", "expected", "high"):
            assert abs(got[key][v] - Decimal(want[key][v])) < Decimal("1e-20"), (key, v)
    assert got["shared_expected"] == Decimal(want["shared_expected"])
    assert got["individual_expected"] == Decimal(want["individual_expected"])
    assert got["overall_confidence"].quantize(Decimal("0.0001")) == Decimal(want["overall_confidence"])
    assert got["label"] == want["label"]
    assert got["expired"] == want["expired"]
    assert got["no_data"] == want["no_data"]
    assert got["warnings"] == want["warnings"]
    assert got["rules_version"] == EXAMPLES["rules_version"] == R.RULES_VERSION
    assert [(ln["item"], ln["id"], ln["q"]) for ln in got["lines"]] == [
        (e["item"], e["id"], e["q"]) for e in want["lines"]
    ]
    for ln, e in zip(got["lines"], want["lines"], strict=True):
        assert ln["sigma"] == Decimal(e["sigma"]), e["item"]
        for v in ("low", "expected", "high"):
            assert ln["cost"][v] == Decimal(e[v]), (e["item"], v)


# PLN-E01-04
def test_proposal_example_with_meals_seasoned() -> None:
    """The case in the proposal, recomputed with the season factor on meals (decision of 11 Nov 2026)."""
    got = estimate(next(c for c in CASES if c["id"] == "EX01"))
    assert [got["total"][v] for v in ("low", "expected", "high")] == [
        Decimal(27758),
        Decimal(36560),
        Decimal(48540),
    ]
    assert got["shared_expected"] == Decimal(16860) and got["individual_expected"] == Decimal(19700)
    assert got["per_person"]["low"] == Decimal("6939.5")  # unrounded
    assert got["display_per_person"]["low"] == Decimal(6940)  # half rounds up
    assert got["label"] == "Medium"


# PLN-E01-05
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_invariants_hold_for_every_example(case: dict) -> None:
    got = estimate(case)
    n = case["trip"]["party"]
    assert got["total"]["low"] <= got["total"]["expected"] <= got["total"]["high"]
    assert Decimal(0) <= got["overall_confidence"] <= Decimal(1)
    assert got["shared_expected"] + got["individual_expected"] == got["total"]["expected"]
    assert abs(got["per_person"]["expected"] * n - got["total"]["expected"]) < Decimal("1e-20")
    for v in ("low", "expected", "high"):
        assert abs(got["display_total"][v] - got["total"][v]) <= 5  # nearest BDT 10
        assert got["display_total"][v] % 10 == 0 and got["display_per_person"][v] % 10 == 0
    assert all(ln["cost"]["low"] <= ln["cost"]["expected"] <= ln["cost"]["high"] for ln in got["lines"])


# PLN-E01-06
@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SEASON_FACTORS", {**R.SEASON_FACTORS, R.SeasonBand.WEEKEND: Decimal("1.20")}),
        ("W_AUTHORITY", Decimal("0.30")),
        ("REFRESH_MONTHS_OTHER", 6),
        ("HIGH_THRESHOLD", Decimal("0.70")),
    ],
)
def test_changing_a_frozen_constant_is_detected(
    monkeypatch: pytest.MonkeyPatch, name: str, value: object
) -> None:
    """Mutation check: the guard tests are not vacuous."""
    monkeypatch.setattr(R, name, value)
    assert spec_contract() != code_contract()  # the doc guard fires
    failures = 0
    for case in CASES:
        got, want = estimate(case), case["expect"]
        same = (
            got["total"]["expected"] == Decimal(want["total"]["expected"])
            and got["overall_confidence"].quantize(Decimal("0.0001"))
            == Decimal(want["overall_confidence"])
            and got["label"] == want["label"]
            and got["warnings"] == want["warnings"]
        )
        failures += not same
    assert failures >= 1  # and at least one hand example fires


# PLN-E01-07
def test_the_planner_package_stays_pure() -> None:
    """E01 adds constants only: no table, route, migration or import of the web layer."""
    source = (Path(R.__file__)).read_text(encoding="utf-8")
    for forbidden in ("sqlalchemy", "fastapi", "app.db", "app.main", "requests", "httpx"):
        assert forbidden not in source, forbidden
