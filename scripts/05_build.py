#!/usr/bin/env python3
"""usage: 05_build.py PREF RAWDIR OUTDIR   -> OUTDIR/{daily,hourly}{,_files}.parquet and stations.parquet (a staging dir
that 06_verify.py checks against the CSVs before 07_place.py copies the files into data/parquet/)."""

import json
import sys
from pathlib import Path

import jma

pref, raw, out = int(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
res = [
    jma.convert("daily", pref, raw / f"stations_{pref}.json", raw / "daily", out),
    jma.convert("hourly", pref, raw / f"stations_{pref}.json", raw / "hourly", out),
]
print(json.dumps(res, ensure_ascii=False))
