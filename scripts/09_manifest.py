#!/usr/bin/env python3
"""usage: 09_manifest.py DATE PREF   -> data/raw/DATE/pref=PREF/MANIFEST.json: path, bytes and sha256 of every raw file
of the fetch (station list, the hourly plan, the daily and hourly CSVs), and of the terms pages of data/raw/DATE/evidence."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def main() -> int:
    date, pref = sys.argv[1], int(sys.argv[2])
    base = ROOT / "data" / "raw" / date
    d = base / f"pref={pref}"
    files = sorted(
        p for p in d.rglob("*") if p.is_file() and p.name != "MANIFEST.json" and not p.name.endswith(".part")
    )
    ev = sorted((base / "evidence").glob("*"))
    rec = lambda root, ps: [
        {
            "path": str(p.relative_to(root)),
            "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
        for p in ps
    ]
    out = {
        "retrieved": date,
        "source": "https://www.data.jma.go.jp/risk/obsdl/",
        "pref": pref,
        "files": rec(d, files),
        "terms_pages": rec(base, ev),
    }
    (d / "MANIFEST.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(out['files'])} files, {sum(f['bytes'] for f in out['files']):,} bytes, {len(ev)} terms pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
