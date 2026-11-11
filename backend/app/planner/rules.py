"""Frozen rule set of the cost planner (Gantt E01, ``Features/Cost-Planner.md``).

This module is the single place where the planner's numbers live. It holds constants and enums only: no
database, no routes, no calculation. The catalogue (E06) and the rule engine (E07) import it, and
``tests/test_planner_rules.py`` fails if it and ``Features/Cost-Planner.md`` ever disagree.

Changing any value here is a rule change: bump ``RULES_VERSION`` and amend the specification in the same
commit. The version is shown with every estimate.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

RULES_VERSION = "planner-rules-1.0.0"


class PricingUnit(str, Enum):
    PER_PERSON = "per_person"
    PER_ENTRY = "per_entry"
    PER_ROOM = "per_room"
    PER_VEHICLE = "per_vehicle"
    PER_GROUP = "per_group"
    PER_MEAL = "per_meal"
    PER_DAY_NIGHT = "per_day_night"
    PER_TRIP = "per_trip"


class Tier(str, Enum):
    ECONOMY = "economy"
    STANDARD = "standard"
    PREMIUM = "premium"


class SourceType(str, Enum):
    OFFICIAL = "official"
    VERIFIED_OPERATOR = "verified_operator"
    COMMUNITY_REPORT = "community_report"


class Category(str, Enum):
    INTERCITY_TRANSPORT = "intercity_transport"
    ACCOMMODATION = "accommodation"
    FOOD = "food"
    LOCAL_TRANSPORT = "local_transport"
    ENTRY_FEE = "entry_fee"
    GUIDE_PERMIT = "guide_permit"
    ACTIVITY = "activity"
    OTHER = "other"


class SeasonBand(str, Enum):
    REGULAR = "regular"
    WEEKEND = "weekend"
    PEAK = "peak"
    PUBLIC_HOLIDAY = "public_holiday"


class ConfidenceLabel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class RangeValue(str, Enum):
    LOW = "low"
    EXPECTED = "expected"
    HIGH = "high"


class Period(str, Enum):
    """How many periods a unit is charged over (Cost-Planner.md 5)."""

    ONCE = "once"  # one occurrence, factor 1.00
    NIGHTS = "nights"
    DAYS = "days"
    MEALS = "meals"  # meals_per_day x each day
    CHOSEN = "chosen"  # the record states day, night or trip (per_group, per_day_night)


class Quantity(str, Enum):
    ELIGIBLE = "eligible"  # n_e
    CEILING = "ceiling"  # ceil(n / capacity)
    ONE = "one"


@dataclass(frozen=True)
class UnitRule:
    quantity: Quantity
    period: Period
    shared: bool  # shared cost is settled by the group; individual cost is per traveller
    season_scaled: bool  # False: the unit is charged once at factor 1.00


UNIT_RULES: dict[PricingUnit, UnitRule] = {
    PricingUnit.PER_PERSON: UnitRule(Quantity.ELIGIBLE, Period.ONCE, False, False),
    PricingUnit.PER_ENTRY: UnitRule(Quantity.ELIGIBLE, Period.ONCE, False, False),
    PricingUnit.PER_ROOM: UnitRule(Quantity.CEILING, Period.NIGHTS, True, True),
    PricingUnit.PER_VEHICLE: UnitRule(Quantity.CEILING, Period.DAYS, True, True),
    PricingUnit.PER_GROUP: UnitRule(Quantity.CEILING, Period.CHOSEN, True, True),
    PricingUnit.PER_MEAL: UnitRule(Quantity.ELIGIBLE, Period.MEALS, False, True),
    PricingUnit.PER_DAY_NIGHT: UnitRule(Quantity.ONE, Period.CHOSEN, True, True),
    PricingUnit.PER_TRIP: UnitRule(Quantity.ONE, Period.ONCE, True, False),
}

# Units whose record must state a capacity (>= 1).
CAPACITY_UNITS = frozenset({PricingUnit.PER_ROOM, PricingUnit.PER_VEHICLE, PricingUnit.PER_GROUP})

# Season factors. When a period falls in several bands the highest factor applies (no stacking).
# The weekend is Friday and Saturday. Official source records and single-occurrence units use 1.00.
SEASON_FACTORS: dict[SeasonBand, Decimal] = {
    SeasonBand.REGULAR: Decimal("1.00"),
    SeasonBand.WEEKEND: Decimal("1.15"),
    SeasonBand.PEAK: Decimal("1.30"),
    SeasonBand.PUBLIC_HOLIDAY: Decimal("1.25"),
}
WEEKEND_WEEKDAYS = (4, 5)  # datetime.weekday(): Friday, Saturday

# Confidence C_i = W_AUTHORITY*A + W_FRESHNESS*F + W_REPORTS*R + W_AGREEMENT*G
W_AUTHORITY = Decimal("0.35")
W_FRESHNESS = Decimal("0.25")
W_REPORTS = Decimal("0.20")
W_AGREEMENT = Decimal("0.20")

AUTHORITY: dict[SourceType, Decimal] = {
    SourceType.OFFICIAL: Decimal("1.0"),
    SourceType.VERIFIED_OPERATOR: Decimal("0.8"),
    SourceType.COMMUNITY_REPORT: Decimal("0.6"),
}
FRESHNESS_FRESH = Decimal("1.0")
FRESHNESS_STALE = Decimal("0.5")
REPORTS_FOR_FULL_SCORE = 3  # R = min(k / 3, 1); official records are not report-based and score 1

# Overall labels: >= HIGH_THRESHOLD is High, >= MEDIUM_THRESHOLD is Medium, otherwise Low.
HIGH_THRESHOLD = Decimal("0.80")
MEDIUM_THRESHOLD = Decimal("0.50")

# Refresh intervals in calendar months (record older than this is stale).
REFRESH_MONTHS_OFFICIAL = 12
REFRESH_MONTHS_OTHER = 3

# Display rounding: nearest BDT 10, halves up, applied only to displayed values.
DISPLAY_STEP = Decimal("10")
DISPLAY_ROUNDING = ROUND_HALF_UP

# Input limits (Cost-Planner.md 3).
MIN_PARTY, MAX_PARTY = 1, 30
MIN_DAYS, MAX_DAYS = 1, 14
MIN_MEALS_PER_DAY, MAX_MEALS_PER_DAY = 0, 3
DEFAULT_MEALS_PER_DAY = 3
