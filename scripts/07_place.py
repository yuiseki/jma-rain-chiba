#!/usr/bin/env python3
"""usage: 07_place.py PREF STAGINGDIR   copy the verified Parquet of one prefecture into data/parquet/ under its
final names, check the copy byte by byte, and rebuild parquet/stations.parquet from the stations of every prefecture
placed so far (one row per station, with the prefecture code)."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).parents[1]
PQ = ROOT / "data" / "parquet"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    pref, stage = int(sys.argv[1]), Path(sys.argv[2])
    moves = {
        "daily.parquet": f"daily/pref={pref}.parquet",
        "hourly.parquet": f"hourly/pref={pref}.parquet",
        "daily_files.parquet": f"daily_files/pref={pref}.parquet",
        "hourly_files.parquet": f"hourly_files/pref={pref}.parquet",
        "stations.parquet": f"stations/pref={pref}.parquet",
    }
    for src, dst in moves.items():
        (PQ / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(stage / src, PQ / dst)
        assert sha(stage / src) == sha(PQ / dst), dst
    parts = sorted((PQ / "stations").glob("pref=*.parquet"))
    pq.write_table(pa.concat_tables([pq.read_table(p) for p in parts]), PQ / "stations.parquet", compression="zstd")
    tables = {}
    for kind in ("daily", "hourly"):
        for p in sorted((PQ / kind).glob("pref=*.parquet")):
            tables.setdefault(kind, {})[p.stem] = pq.ParquetFile(p).metadata.num_rows
    tables["stations"] = pq.ParquetFile(PQ / "stations.parquet").metadata.num_rows
    (PQ / "tables.json").write_text(json.dumps(tables, indent=1) + "\n")
    print(json.dumps(tables))
    return 0


if __name__ == "__main__":
    sys.exit(main())
