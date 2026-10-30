#!/usr/bin/env python3
"""Read the repository back from the Hub at the recorded revision and compare it with the local copy: the checksums of
the card, the licence and every Parquet, the schemas, the row counts, the non-null counts of every column and the cells.

    uv run python scripts/10_verify_hub.py   # needs docs/revision.json from src/publish.py --push
"""

import json
import sys
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import HfApi, hf_hub_download

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
from publish import sha256


def main() -> int:
    rev = json.loads((ROOT / "docs" / "revision.json").read_text())
    repo, sha = rev["repo"], rev["revision"]
    cache = ROOT / "data" / "hub_readback"
    out, bad = {"repo": repo, "revision": sha}, []
    for name, want in rev["sha256"].items():
        p = Path(hf_hub_download(repo, name, repo_type="dataset", revision=sha, local_dir=cache))
        if sha256(p) != want:
            bad.append(f"checksum {name}")
    out["files_checked"] = len(rev["sha256"])
    listed = set(HfApi().list_repo_files(repo, repo_type="dataset", revision=sha))
    out["files_on_hub"] = len(listed)
    for name in rev["sha256"]:
        if name not in listed:
            bad.append(f"not on the Hub: {name}")
    tables = {}
    for name in rev["sha256"]:
        if not name.endswith(".parquet"):
            continue
        hub, mine = pq.read_table(cache / name), pq.read_table(ROOT / "data" / name)
        if not hub.schema.equals(mine.schema, check_metadata=True):
            bad.append(f"schema {name}")
        if not hub.equals(mine):
            bad.append(f"cells {name}")
        nn = {c: hub.num_rows - hub[c].null_count for c in hub.column_names}
        if nn != {c: mine.num_rows - mine[c].null_count for c in mine.column_names}:
            bad.append(f"non-null counts {name}")
        tables[name] = {"rows": hub.num_rows, "non_null": nn}
    out["tables"] = tables
    out["problems"] = bad
    (ROOT / "docs" / "verify_hub.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(bad) if bad else f"OK: the repository at {sha} equals the local copy")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
