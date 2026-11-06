"""Rebuild every data flow diagram used by the Abhijatri Word documents.   Usage: python make_diagrams.py [key ...]

Draws each sheet and runs four kinds of check, exiting non-zero if any fails:
  1. structure (Gane-Sarson rules) on every logical diagram (the sheets of one diagram merged);
  2. content balancing: each child boundary flow realises a named parent flow, and every parent flow is realised;
  3. rule 9: every data store is written and read somewhere;
  4. layout: no arrow passes under a box it does not join, no label touches a box or another label or sits on an arrow,
     and the legend overlaps nothing.
"""

import sys
from pathlib import Path

from diagram_lib import check_balance, check_dfd, check_stores, draw_dfd, merge_sheets

OUT = Path(__file__).resolve().parent


def run_checks(sheets, draw=True, only=()):
    logical = merge_sheets(sheets)
    rule, layout = [], []
    for d in logical:
        rule += check_dfd(d)
    rule += check_balance(logical)
    rule += check_stores(logical)
    if draw:
        for d in sheets:
            if only and d.key not in only:
                continue
            layout += draw_dfd(d, str(OUT / f"{d.key}.png"))
            print("drew", d.key)
    return logical, rule, layout


def main(only):
    import dfd_levels

    _, rule, layout = run_checks(dfd_levels.ALL, True, only)
    for p in rule:
        print("RULE VIOLATION:", p)
    for p in layout:
        print("LAYOUT PROBLEM:", p)
    print("rule violations:", len(rule), " layout problems:", len(layout))
    return 1 if rule or layout else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
