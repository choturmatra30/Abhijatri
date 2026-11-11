# Abhijatri Cost Planner

**Status:** Frozen rule specification v1 (Gantt task E01), frozen 11 November 2026. **Pending approval by Shahriar Islam** (section 17).  
**Rule-set version:** `planner-rules-1.0.0`  
**Requirements and traces:** FR08, FR09, O3, US2; E01 (this document); consumed by E02 to E08, E11 and E12  
**Scope:** the deterministic rules by which an itemised, source-dated BDT estimate is calculated. It does not cover price research (E02 to E05), the catalogue tables and admin screens (E06, E10), the API and screens (E07, E08) or the saved brief (E09).  
**Machine-checked constants:** the JSON block in section 11 is compared with `backend/app/planner/rules.py` by `tests/test_planner_rules.py`. The two cannot disagree without a failing test.  
**Source:** the proposal, section "Abhijatri Cost Planner". Where the proposal was silent or inconsistent, this document decides and records the decision (section 1.2).

## 1. Purpose and boundary

The planner answers three questions before a trip: can this group afford it, how are shared costs divided fairly, and which choices (dates, comfort tier, transport) change the total most. It is **decision support, not a vendor quotation or a price guarantee**, and the interface says so.

It is a deterministic rule engine. **There is no machine learning and no probabilistic simulation.** Every result can be reproduced by hand from the inputs, the catalogue records and the constants in section 11. The same inputs and the same catalogue always give the same estimate.

### 1.1 Out of scope (frozen)

No itinerary or day-by-day plan; no live prices, availability or booking; no taxes, service-charge modelling or currency conversion (all amounts are whole BDT); no personal data inside an estimate; no price prediction. A saved estimate with notes and contacts is the Saved Trip Brief (E09). Vendor prices from the bookings extension are not planner inputs.

### 1.2 Decisions taken in this specification

| # | Proposal text | Decision | Why |
|---|---|---|---|
| D1 | Worked example gave meals a season sum of 9.00 while rooms and vehicles used 1.15 on weekend periods | Meals are season-scaled like every other variable item: sum over meal-days with `s(date)`. Thu 1.00, Fri 1.15, Sat 1.15, 3 meals a day gives 9.90 | One rule for all variable items. Total of the proposal case changes from 35,660 to 36,560 (the printed proposal is not edited; amend it deliberately) |
| D2 | `n_e` "eligible travellers" undefined | In v1 `n_e = n`. Traveller type (adult, student, child) is recorded and shown but does not change a price. Discounts need typed price records and are out of scope | The catalogue has no per-type prices |
| D3 | Rounding order not stated | Calculate unrounded in `Decimal`; the per-person value is the unrounded total divided by `n`; display rounds to the nearest BDT 10, halves up. Displayed lines need not add to the displayed total and the screen says so | Avoids compounding rounding error |
| D4 | `G_i` when `p^E = 0` | `G = 1` if low = high, else `0` | Avoids division by zero |
| D5 | `R_i` for official sources | Official records are not report-based: `R = 1` | Fixed charges are authoritative |
| D6 | Overall confidence when `ΣK^E = 0` | `0` and label Low | Nothing was priced |
| D7 | A requested item with no usable record | Left out of every total, listed under `no_data`, warning `incomplete`; the overall label is capped at Medium | Never price at 0 silently; an incomplete estimate cannot be "High" |
| D8 | Tier with no record | No fallback to another tier; the item is `no_data` | A premium trip must not use economy prices unseen |
| D9 | Several records for one item | Choose by section 7 step 3 (not expired, fresh before stale, higher authority, newer `verified_on`, lower id) | Deterministic |
| D10 | `per_group` "each day or one trip", `per_day_night` day or night | The record states `basis` (`day`, `night` or `trip`) | Removes the ambiguity from the engine |
| D11 | Several season bands on one date | The highest factor applies; factors never stack | Predictable and explainable |
| D12 | Peak and public-holiday factors not given | Peak 1.30, public holiday 1.25 (initial values, frozen here) | Needed to test precedence |
| D13 | Which date's season applies to a night | The check-in date (the night that begins on that date) | A Thursday night is a regular night |
| D14 | When is a record expired or stale | Against the estimate date `as_of` (today), not the trip date. Separately, a warning is shown when `valid_until` falls before the trip starts | Matches "excluded" and "visible warning" |

## 2. Terminology

- **Comfort tier** (economy, standard, premium): chosen by the user; selects which catalogue records apply.
- **Price range** (low, expected, high): the realistic spread of a record's price within its tier.
- **Period**: one chargeable day, night, meal or occurrence. **Season factor** `s`: multiplier of a period.
- **Shared cost**: charged to the group (rooms, vehicles, groups, per-day/night services, per-trip items). **Individual cost**: charged per traveller (person, entry, meal).

## 3. Inputs and limits

| Input | Rule |
|---|---|
| Destination | A published destination that has catalogue records |
| Start date, days `d`, nights `m` | `1 <= d <= 14`; `m` defaults to `d - 1` and must satisfy `0 <= m <= d` |
| Party size `n` | `1 <= n <= 30`; traveller types listed for display only (D2) |
| Comfort tier | economy, standard or premium |
| Choices | Transport mode, accommodation type, meal plan (`meals_per_day`, `0` to `3`, default 3), selected activities, `vehicle_days` (`1` to `d`, default `d`) |
| `as_of` | The server date at calculation |

Anything outside these limits is rejected with a `422` and the standard bilingual error contract (`Docs/api/API.md` section 2). The limits are in the section 11 block.

## 4. Price record contract

Each record carries: destination, category, item, tier, `unit`, `capacity`, `low`, `expected`, `high` (whole BDT), `source_type`, source reference, `verified_on`, `valid_until` (optional), `reports` (count of independent moderated reports `k`), and for `per_group` and `per_day_night` a `basis`. Categories: `intercity_transport`, `accommodation`, `food`, `local_transport`, `entry_fee`, `guide_permit`, `activity`, `other`.

Rules a record must satisfy (checked by the catalogue in E06, and by the oracle in the tests): `low <= expected <= high`; `capacity >= 1` for `per_room`, `per_vehicle`, `per_group`; amounts are whole BDT and not negative; `verified_on` is not in the future; `source_type` is `official`, `verified_operator` or `community_report`. Official sources take priority for fixed charges (entry fees, permits); moderated community reports serve variable categories.

## 5. Pricing units

`q` is the quantity, `T` the chargeable periods, `s` the season factor of a period. `Σs` is the sum of `s` over `T`.

| Unit | `q` | `T` | Season-scaled | Cost kind |
|---|---|---|---|---|
| `per_person` | `n_e` | One occurrence | No (`Σs = 1`) | Individual |
| `per_entry` | `n_e` | One per visit | No (`Σs = 1`) | Individual |
| `per_room` | `ceil(n / c)` | Each night `m` | Yes | Shared |
| `per_vehicle` | `ceil(n / c)` | Each day used (`vehicle_days`) | Yes | Shared |
| `per_group` | `ceil(n / c)` | By `basis`: each day, each night, or one trip | Yes (`trip` is 1) | Shared |
| `per_meal` | `n_e` | `meals_per_day` for each of the `d` days | Yes | Individual |
| `per_day_night` | `1` | By `basis`: each day, each night, or one trip | Yes (`trip` is 1) | Shared |
| `per_trip` | `1` | One occurrence | No (`Σs = 1`) | Shared |

`c` is the capacity of one room, vehicle or group. **Official records are never season-scaled**: for an official record every period uses `s = 1`, whatever the unit. Zero nights makes a room cost 0 (`Σs = 0`). A requested item that costs 0 because its periods are 0 is still listed.

## 6. Season factors

`s(date)` is the **highest** factor among the bands that apply to the date; bands never multiply. A date is `weekend` when it is a Friday or Saturday. `peak` and `public_holiday` dates come from catalogue data (E06, E10) for the destination, not from this module. Factors are in section 11.

## 7. Calculation order

1. **Validate** the inputs (section 3). Build the date list: day `i` is `start + i`; night `i` begins on `start + i` (D13).
2. **Collect** the records for each requested item and tier. Exclude every record with `valid_until < as_of` (listed under `expired`).
3. **Choose one record per item** from the rest: not stale before stale; then higher authority (`official`, `verified_operator`, `community_report`); then newer `verified_on`; then lower id. If none remains the item is `no_data` (D7).
4. **Quantity and periods** from section 5. A record is **stale** when `verified_on` plus its refresh interval is earlier than `as_of`; the interval is 12 calendar months for official records and 3 months for all others. A stale record is used with `F = 0.5` and a warning `stale:<id>`.
5. **Cost** for each `v` in low, expected, high: `K^v = p^v × q × Σs` (unrounded).
6. **Split** expected cost into shared and individual by unit kind (section 5).
7. **Totals**: `T^v = Σ K^v`; per person `P^v = T^v / n`, both unrounded.
8. **Confidence** (section 9) per line and overall.
9. **Round for display** (section 8) and assemble the result (section 12).

## 8. Rounding

All arithmetic is exact `Decimal`. Nothing is rounded before step 9. Display value = nearest multiple of BDT 10, **halves round up** (6,939.5 → 6,940; 15 → 20; 1,275 → 1,280). The per-person display is the rounded unrounded per-person value, never the total divided after rounding.

## 9. Confidence and freshness

Per line: `C = 0.35·A + 0.25·F + 0.20·R + 0.20·G`.

- `A`: official 1.0, verified operator 0.8, moderated community report 0.6.
- `F`: 1.0 when fresh, 0.5 when stale.
- `R = min(k / 3, 1)`; official records use `R = 1` (D5).
- `G = max(0, 1 − (high − low) / (2 × expected))`; if `expected = 0`, `G = 1` when low = high, otherwise `0` (D4).

Overall: `C_overall = Σ(K^E × C) / Σ K^E` (0 when `Σ K^E = 0`, D6). Labels: **High** at 0.80 or more, **Medium** from 0.50 to below 0.80, **Low** below 0.50. A Low result carries warning `low_confidence` and an explicit verification message. If any requested item is `no_data` and the label would be High it becomes Medium (D7). The proposal's per-category `C_i` values were illustrative; the planner always derives them from the components.

## 10. Rule-set versioning

`RULES_VERSION` is `planner-rules-1.0.0`. It is returned and shown with every estimate. Changing any constant in section 11 is a rule change: bump the version, amend this document and the examples in the same commit.

## 11. Frozen constants (machine-checked)

```json planner-rules
{
  "rules_version": "planner-rules-1.0.0",
  "season_factors": {
    "regular": "1.00",
    "weekend": "1.15",
    "peak": "1.30",
    "public_holiday": "1.25"
  },
  "weekend": [
    "Friday",
    "Saturday"
  ],
  "confidence_weights": {
    "authority": "0.35",
    "freshness": "0.25",
    "reports": "0.20",
    "agreement": "0.20"
  },
  "authority": {
    "official": "1.0",
    "verified_operator": "0.8",
    "community_report": "0.6"
  },
  "freshness": {
    "fresh": "1.0",
    "stale": "0.5"
  },
  "reports_for_full_score": 3,
  "thresholds": {
    "high": "0.80",
    "medium": "0.50"
  },
  "refresh_months": {
    "official": 12,
    "other": 3
  },
  "display_step": "10",
  "limits": {
    "party": [
      1,
      30
    ],
    "days": [
      1,
      14
    ],
    "meals_per_day": [
      0,
      3
    ],
    "default_meals_per_day": 3
  },
  "capacity_units": [
    "per_group",
    "per_room",
    "per_vehicle"
  ],
  "units": {
    "per_person": {
      "quantity": "eligible",
      "period": "once",
      "shared": false,
      "season_scaled": false
    },
    "per_entry": {
      "quantity": "eligible",
      "period": "once",
      "shared": false,
      "season_scaled": false
    },
    "per_room": {
      "quantity": "ceiling",
      "period": "nights",
      "shared": true,
      "season_scaled": true
    },
    "per_vehicle": {
      "quantity": "ceiling",
      "period": "days",
      "shared": true,
      "season_scaled": true
    },
    "per_group": {
      "quantity": "ceiling",
      "period": "chosen",
      "shared": true,
      "season_scaled": true
    },
    "per_meal": {
      "quantity": "eligible",
      "period": "meals",
      "shared": false,
      "season_scaled": true
    },
    "per_day_night": {
      "quantity": "one",
      "period": "chosen",
      "shared": true,
      "season_scaled": true
    },
    "per_trip": {
      "quantity": "one",
      "period": "once",
      "shared": true,
      "season_scaled": false
    }
  }
}
```

## 12. Result shape (contract for E07 and E08)

An estimate returns `rules_version`, `as_of`, the inputs echoed, and:

- one **line** per priced item: item, category, unit, `q`, `Σs`, `low`, `expected`, `high`, source type and reference, `verified_on`, record id, `stale` flag, line confidence;
- `total` and `per_person` for low, expected and high (display rounded; exact values available to tests);
- `shared_expected` and `individual_expected`;
- `overall_confidence` (number) and `label`;
- `assumptions` (tier, `n_e = n`, meals per day, vehicle days, bands used, rounding note), `expired` (ids), `no_data` (items), `warnings` (`stale:<id>`, `incomplete`, `low_confidence`, validity-before-trip).

All text is available in Bangla and English. Estimates carry no personal data.

## 13. Worked examples (illustrative prices, not researched data)

The twelve examples live in `backend/tests/planner_examples.json`; their expected values were derived by hand for this document and are reproduced by the test oracle. The prices are placeholders; E02 to E05 supply real ones. Dates: as_of 10 Nov 2026; Thursday 12 Nov, Friday 13, Saturday 14, Sunday 15.

### 13.1 EX01: four students, Cox's Bazar, Thursday to Saturday, standard tier

3 days, 2 nights, 3 meals a day, vehicle 3 days. Weekend is Friday and Saturday, so the nights sum to 1.00 + 1.15 = 2.15, the days to 1.00 + 1.15 + 1.15 = 3.30 and the meals to 3 × 3.30 = 9.90.

| Category | Unit and source | `q` | `Σs` | Low | Expected | High | `C` |
|---|---|---:|---:|---:|---:|---:|---:|
| Intercity bus (2,000 / 2,400 / 3,000) | per person, verified operator, 3 reports | 4 | 1.00 | 8,000 | 9,600 | 12,000 | 0.888 |
| Hotel room, capacity 2 (2,200 / 3,000 / 4,000) | per room, community, 3 reports | 2 | 2.15 | 9,460 | 12,900 | 17,200 | 0.800 |
| Meals (180 / 250 / 350) | per meal, community, 2 reports | 4 | 9.90 | 7,128 | 9,900 | 13,860 | 0.725 |
| Local vehicle, capacity 4 (900 / 1,200 / 1,600) | per vehicle, community, 1 report | 1 | 3.30 | 2,970 | 3,960 | 5,280 | 0.668 |
| Park entry (50) | per entry, official | 4 | 1.00 | 200 | 200 | 200 | 1.000 |
| **Group total** | | | | **27,758** | **36,560** | **48,540** | |
| **Per person** (unrounded) | | | | 6,939.5 | 9,140 | 12,135 | |
| **Displayed** total / per person | | | | 27,760 / 6,940 | 36,560 / 9,140 | 48,540 / 12,140 | |

Shared (room and vehicle, expected) 16,860; individual 19,700. Overall confidence `(8,528 + 10,320 + 7,180.8 + 2,646.6 + 200) / 36,560 = 28,875.4 / 36,560 = 0.7898`, **Medium**. Compared with the proposal's printed table (35,660; 27,110; 47,280) only the meals line and what depends on it changed (D1); the proposal's other lines were re-derived and are correct.

### 13.2 The other examples

| ID | What it proves | Result (low / expected / high total) | Label |
|---|---|---|---|
| EX02 | Party 5, capacity 2: `ceil(5/2) = 3` rooms; 1 night | 5,500 / 6,600 / 8,000 | High |
| EX03 | Party 1, zero nights (room costs 0), capacity 1, one day | 1,100 / 1,450 / 1,800 | High |
| EX04 | `per_group`, 7 people, capacity 6: 2 groups; `day` and `trip` basis; official permit | 6,600 / 8,600 / 10,600 | High |
| EX05 | `per_day_night` on nights and on days, and `per_trip` | 1,700 / 2,000 / 2,400 | High |
| EX06 | Holiday (1.25) and peak (1.30 beats weekend 1.15) on two nights: `Σs = 2.55`, no stacking; per-person halves round up | 2,550 / 3,060 / 3,570 | High |
| EX07 | Stale community record: used, `F = 0.5`, warning `stale:bus` | 1,200 / 1,400 / 1,600 | Medium (0.7064) |
| EX08 | Expired record excluded and listed; missing items `no_data`; High capped to Medium; warning `incomplete` | 2,000 / 2,200 / 2,400 | Medium (0.9118 capped) |
| EX09 | Official vehicle fee ignores the Friday weekend (`Σs = 2.00`); low = expected = high gives `G = 1` | 1,150 / 1,150 / 1,150 | High (1.0000) |
| EX10 | Record choice among four records for one item: fresh before stale, authority, date, id | 1,000 / 1,200 / 1,400 | High |
| EX11 | Stale, uncorroborated, wide range: confidence 0.3850, warnings `low_confidence` | 2,000 / 4,000 / 8,000 | Low |
| EX12 | Display rounding of a half: per person 15 shows 20 | 30 / 30 / 30 | High |

## 14. Validation protocol (hand-over to E11 and E12)

- E11 writes its own hand-calculated scenarios from the rules above and keeps the **seed data and the held-out data separate**. The twelve examples here are rule examples, not accuracy data.
- Ten independent trips are collected and sealed outside the seed catalogue; they are not opened until the catalogue is frozen.
- After the freeze: for each trip compare expected estimate `E` with actual in-scope cost `A`: `|E − A| / A` per category and in total; mean absolute percentage error (MAPE); **coverage** = share of trips with `A` inside `[T^L, T^H]`.
- Baseline: one average per-person per-day cost × `n × d`, built **without** the held-out trips.
- Acceptance target: planner MAPE below the baseline MAPE and coverage of at least 7 of 10.
- Every pricing unit, odd party sizes, capacity one, stale, expired and official-fixed cases are executed against the engine (E12) using the same fixtures.

## 15. Security and privacy

No personal data enters an estimate. The calculation endpoint (E07) is public read-only, rate-limited like other public endpoints, and its responses may be cached publicly only when they contain no user identity. Admin price maintenance (E10) records actor and timestamp. Seed content carries source, date, language and licence (F05). No scraped images.

## 16. Traceability and tests

| Test ID | Test | Proves |
|---|---|---|
| PLN-E01-01 | `test_rule_constants_are_internally_valid` | Weights sum to 1, thresholds ordered, all eight units have rules, capacity units use ceiling |
| PLN-E01-02 | `test_specification_and_code_state_the_same_constants` | Section 11 equals `app/planner/rules.py` |
| PLN-E01-03 | `test_worked_example_matches_the_hand_calculation` (12 cases) | Oracle reproduces every hand value (lines, totals, per person, display, confidence, label, warnings) |
| PLN-E01-04 | `test_proposal_example_with_meals_seasoned` | EX01 totals 27,758 / 36,560 / 48,540 |
| PLN-E01-05 | `test_invariants_hold_for_every_example` (12 cases) | Order low ≤ expected ≤ high, shared + individual = total, per person × n = total, display multiples of 10 |
| PLN-E01-06 | `test_changing_a_frozen_constant_is_detected` | A changed constant fails the doc guard and a hand example |
| PLN-E01-07 | `test_the_planner_package_stays_pure` | No database, web or network import |

Requirement mapping: FR08 (inputs and itemised result: sections 3, 7, 12), FR09 (pricing units: section 5), O3 (explainable estimate: sections 7 to 9), US2 (shared and individual cost: sections 5 and 12). Downstream: E02 to E05 use section 4; E06 section 4 and 5; E07 sections 7 to 12 and the examples; E08 section 12; E11 and E12 section 14.

## 17. Approval record

| Role | Name | Check | Date |
|---|---|---|---|
| Specification and implementation (backend) | Syed Muhtasim Alam | Constants, rules, examples and tests | 11 Nov 2026 |
| Quality review | Md. Irfan Iqbal | Examples and traceability | Pending |
| Approver (Gantt owner of E01) | Shahriar Islam | Units, confidence constants, season factors, D1 to D14 | Pending |

E01 is complete in the Gantt only when the approver signs. Until then this document is frozen for implementation but not approved.
