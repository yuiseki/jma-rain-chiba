#!/usr/bin/env python3
"""usage: 03_plan_hourly.py PREF RAWDIR  -> RAWDIR/hourly_plan_PREF.tsv (station, first year, last year) and the count."""

import sys
from pathlib import Path

import jma

pref, raw = int(sys.argv[1]), Path(sys.argv[2])
sts = jma.stations(raw / f"stations_{pref}.json", pref)
plan = jma.plan_hourly(raw / "daily", sts)
(raw / f"hourly_plan_{pref}.tsv").write_text("".join(f"{s}\t{a}\t{b}\n" for s, a, b in plan))
n = sum(b - a + 1 for _, a, b in plan)
print(f"{len(plan)} of {len(sts)} stations have daily values; {n} hourly requests")
