"""Test-only reference calculator for the cost planner (Features/Cost-Planner.md 7).

It follows the written algorithm step by step in ``Decimal`` and reads every constant from
``app.planner.rules``. It is deliberately naive and shares no code with the future engine (E07), which
must reproduce ``planner_examples.json`` too. It is not part of the application.
"""

from __future__ import annotations

import calendar
import math
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.planner import rules as R

RANGES = ("low", "expected", "high")


def _d(value: str | int) -> Decimal:
    return Decimal(str(value))


def add_months(day: date, months: int) -> date:
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def season_factor(day: date, bands: dict[str, list[str]]) -> Decimal:
    names = {R.SeasonBand.REGULAR}
    if day.weekday() in R.WEEKEND_WEEKDAYS:
        names.add(R.SeasonBand.WEEKEND)
    names.update(R.SeasonBand(b) for b in bands.get(day.isoformat(), []))
    return max(R.SEASON_FACTORS[n] for n in names)  # highest wins, never stacked


def is_stale(rec: dict[str, Any], as_of: date) -> bool:
    official = R.SourceType(rec["source_type"]) is R.SourceType.OFFICIAL
    months = R.REFRESH_MONTHS_OFFICIAL if official else R.REFRESH_MONTHS_OTHER
    return add_months(date.fromisoformat(rec["verified_on"]), months) < as_of


def is_expired(rec: dict[str, Any], as_of: date) -> bool:
    until = rec.get("valid_until")
    return until is not None and date.fromisoformat(until) < as_of


def pick_record(records: list[dict[str, Any]], as_of: date) -> dict[str, Any] | None:
    live = [r for r in records if not is_expired(r, as_of)]
    if not live:
        return None
    live.sort(
        key=lambda r: (
            is_stale(r, as_of),
            -R.AUTHORITY[R.SourceType(r["source_type"])],
            -date.fromisoformat(r["verified_on"]).toordinal(),
            r["id"],
        )
    )
    return live[0]


def agreement(low: Decimal, exp: Decimal, high: Decimal) -> Decimal:
    if exp == 0:
        return Decimal(1) if high == low else Decimal(0)
    return max(Decimal(0), 1 - (high - low) / (2 * exp))


def confidence(rec: dict[str, Any], stale: bool) -> Decimal:
    source = R.SourceType(rec["source_type"])
    reports = Decimal(1) if source is R.SourceType.OFFICIAL else min(
        Decimal(rec.get("reports", 0)) / R.REPORTS_FOR_FULL_SCORE, Decimal(1)
    )
    return (
        R.W_AUTHORITY * R.AUTHORITY[source]
        + R.W_FRESHNESS * (R.FRESHNESS_STALE if stale else R.FRESHNESS_FRESH)
        + R.W_REPORTS * reports
        + R.W_AGREEMENT * agreement(_d(rec["low"]), _d(rec["expected"]), _d(rec["high"]))
    )


def label(score: Decimal) -> R.ConfidenceLabel:
    if score >= R.HIGH_THRESHOLD:
        return R.ConfidenceLabel.HIGH
    if score >= R.MEDIUM_THRESHOLD:
        return R.ConfidenceLabel.MEDIUM
    return R.ConfidenceLabel.LOW


def display(value: Decimal) -> Decimal:
    return (value / R.DISPLAY_STEP).quantize(Decimal(1), rounding=R.DISPLAY_ROUNDING) * R.DISPLAY_STEP


def period_sum(rec: dict[str, Any], trip: dict[str, Any], scaled: bool, rule: R.UnitRule) -> Decimal:
    start = date.fromisoformat(trip["start"])
    bands = trip.get("bands", {})
    days, nights = trip["days"], trip["nights"]

    def over(count: int) -> Decimal:
        total = Decimal(0)
        for i in range(count):
            total += season_factor(start + timedelta(days=i), bands) if scaled else Decimal(1)
        return total

    period = rule.period
    if period is R.Period.ONCE:
        return Decimal(1)
    if period is R.Period.NIGHTS:
        return over(nights)
    if period is R.Period.DAYS:
        return over(trip.get("vehicle_days", days))
    if period is R.Period.MEALS:
        return trip.get("meals_per_day", R.DEFAULT_MEALS_PER_DAY) * over(days)
    basis = rec["basis"]  # per_group and per_day_night state day, night or trip
    if basis == "trip":
        return Decimal(1)
    return over(nights if basis == "night" else days)


def estimate(example: dict[str, Any]) -> dict[str, Any]:
    trip, as_of = example["trip"], date.fromisoformat(example["as_of"])
    n = trip["party"]
    assert R.MIN_PARTY <= n <= R.MAX_PARTY and R.MIN_DAYS <= trip["days"] <= R.MAX_DAYS

    by_item: dict[str, list[dict[str, Any]]] = {}
    for rec in example["records"]:
        by_item.setdefault(rec["item"], []).append(rec)

    lines, expired, no_data, warnings = [], [], [], []
    for item in example.get("requested", list(by_item)):
        records = by_item.get(item, [])
        expired += [r["id"] for r in records if is_expired(r, as_of)]
        rec = pick_record(records, as_of)
        if rec is None:
            no_data.append(item)
            continue
        unit = R.PricingUnit(rec["unit"])
        rule = R.UNIT_RULES[unit]
        if unit in R.CAPACITY_UNITS:
            assert rec["capacity"] >= 1
        assert _d(rec["low"]) <= _d(rec["expected"]) <= _d(rec["high"])
        official = R.SourceType(rec["source_type"]) is R.SourceType.OFFICIAL
        scaled = rule.season_scaled and not official
        qty = {
            R.Quantity.ELIGIBLE: n,
            R.Quantity.CEILING: math.ceil(n / rec.get("capacity", 1)),
            R.Quantity.ONE: 1,
        }[rule.quantity]
        sigma = period_sum(rec, trip, scaled, rule)
        stale = is_stale(rec, as_of)
        if stale:
            warnings.append(f"stale:{rec['id']}")
        costs = {v: _d(rec[v]) * qty * sigma for v in RANGES}
        lines.append(
            {
                "item": item,
                "id": rec["id"],
                "q": qty,
                "sigma": sigma,
                "shared": rule.shared,
                "cost": costs,
                "confidence": confidence(rec, stale),
            }
        )

    total = {v: sum((ln["cost"][v] for ln in lines), Decimal(0)) for v in RANGES}
    shared = sum((ln["cost"]["expected"] for ln in lines if ln["shared"]), Decimal(0))
    weight = total["expected"]
    overall = (
        sum((ln["cost"]["expected"] * ln["confidence"] for ln in lines), Decimal(0)) / weight
        if weight
        else Decimal(0)
    )
    result_label = label(overall)
    if no_data:
        warnings.append("incomplete")
        if result_label is R.ConfidenceLabel.HIGH:
            result_label = R.ConfidenceLabel.MEDIUM  # an incomplete estimate is never High
    if result_label is R.ConfidenceLabel.LOW:
        warnings.append("low_confidence")
    return {
        "lines": lines,
        "total": total,
        "per_person": {v: total[v] / n for v in RANGES},
        "shared_expected": shared,
        "individual_expected": total["expected"] - shared,
        "display_total": {v: display(total[v]) for v in RANGES},
        "display_per_person": {v: display(total[v] / n) for v in RANGES},
        "overall_confidence": overall,
        "label": result_label.value,
        "expired": sorted(expired),
        "no_data": sorted(no_data),
        "warnings": sorted(warnings),
        "rules_version": R.RULES_VERSION,
    }
