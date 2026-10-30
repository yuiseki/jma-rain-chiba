#!/usr/bin/env python3
"""Push the card, licence, provenance, raw CSVs, Parquet, scripts and the profile of the prefectures built so far.

uv run python src/publish.py             # dry run: list the files and their sizes
uv run python src/publish.py --push      # one commit; prints the sha and writes docs/revision.json

The Hub repository grows by prefecture: nothing is deleted, a file of another prefecture already on the Hub stays.
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPO = "yuiseki/jma-rain-kanto"


def collect() -> dict[str, Path]:
    card = (DATA / "README.md").read_text(encoding="utf-8")
    if "license: cc-by-4.0" not in card:
        raise SystemExit("the card does not declare license: cc-by-4.0")
    tables = json.loads((DATA / "parquet" / "tables.json").read_text())
    for kind in ("daily", "hourly"):
        for part, n in tables[kind].items():
            if f"{n:,}" not in card:
                raise SystemExit(f"the card does not give {n:,} rows of {kind} {part}")
    files: dict[str, Path] = {"README.md": DATA / "README.md", "LICENSE": DATA / "LICENSE",
                              "provenance.yaml": DATA / "provenance.yaml"}  # fmt: skip
    for p in sorted(DATA.glob("raw/*/**/*")):
        if p.is_file() and not p.name.endswith(".part"):
            files[p.relative_to(DATA).as_posix()] = p
    for p in sorted((DATA / "parquet").rglob("*")):
        if p.is_file():
            files[p.relative_to(DATA).as_posix()] = p
    for p in sorted((ROOT / "scripts").glob("*")):
        if p.is_file() and p.suffix in (".py", ".sh"):
            files[f"scripts/{p.name}"] = p
    for p in sorted((ROOT / "docs").glob("*.json")):
        if p.name != "revision.json":
            files[f"docs/{p.name}"] = p
    for m in sorted(DATA.glob("raw/*/pref=*/MANIFEST.json")):
        if not m.is_file():
            raise SystemExit(f"missing {m}")
    if not re.search(r"pref=\d+", " ".join(files)):
        raise SystemExit("no prefecture in the file list")
    return files


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    files = collect()
    total = sum(p.stat().st_size for p in files.values())
    print(f"{a.repo}\n  {len(files)} files, {total:,} bytes")
    if not a.push:
        print("\ndry run. pass --push to upload")
        return 0
    from huggingface_hub import CommitOperationAdd, HfApi

    api = HfApi()
    api.create_repo(a.repo, repo_type="dataset", exist_ok=True, private=False)
    ops = [CommitOperationAdd(path_in_repo=k, path_or_fileobj=str(v)) for k, v in files.items()]
    c = api.create_commit(
        a.repo, ops, repo_type="dataset", commit_message="Add Chiba (45): daily and hourly rainfall, 1974 to 2025"
    )
    rev = {"repo": a.repo, "revision": c.oid, "pushed": datetime.now(UTC).isoformat(timespec="seconds"),
           "sha256": {k: sha256(v) for k, v in files.items() if k.startswith("parquet/") or k in ("README.md", "LICENSE")}}  # fmt: skip
    (ROOT / "docs" / "revision.json").write_text(json.dumps(rev, indent=1) + "\n")
    print(f"pushed {a.repo} revision {c.oid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
