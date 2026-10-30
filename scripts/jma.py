"""Helpers for jma-rain-kanto: station lists, the hourly plan and the CSV to Parquet conversion.

The CSVs of 過去の気象データ・ダウンロード are cp932. The header rows give the layout (weather stations have four
columns per element, AMeDAS three, without 現象なし情報). Values are read as numbers and blanks become null (never 0).
"""

import csv
import datetime as dt
import io
import json
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

PREFS = {40: ("茨城県", "ibaraki"), 41: ("栃木県", "tochigi"), 42: ("群馬県", "gunma"), 43: ("埼玉県", "saitama"),
         44: ("東京都", "tokyo"), 45: ("千葉県", "chiba"), 46: ("神奈川県", "kanagawa")}  # fmt: skip
DAILY = {"降水量の合計(mm)": "precip", "1時間降水量の最大(mm)": "max1h", "10分間降水量の最大(mm)": "max10m"}
HOURLY = {"降水量(mm)": "precip"}
SUBS = {"": "_mm", "現象なし情報": "_nophen", "品質情報": "_quality", "均質番号": "_homog"}


def dm_to_deg(s: str) -> float:
    m = re.match(r"(\d+)度([\d.]+)分", s)
    return int(m.group(1)) + float(m.group(2)) / 60


def stations(path, pref: int) -> list[dict]:
    """One row per station of a station list (the JSON answer of top/station). The list repeats each station."""
    seen: dict[str, dict] = {}
    for m in json.loads(Path(path).read_text(encoding="utf-8"))["markers"]:
        if m["kind"] != "station" or m["stid"] in seen:
            continue
        assert m["prid"] == str(pref), (m["stid"], m["prid"], pref)
        f = dict(p.split("：", 1) for p in m["title"].split("\n") if "：" in p)
        end = re.search(r"(\d{4})年(\d{2})月(\d{2})日に観測終了", m["title"])
        seen[m["stid"]] = {
            "station_id": m["stid"], "station_name": m["stname"], "pref": pref,
            "kind": "synop" if m["stid"].startswith("s") else "amedas",
            "lat": dm_to_deg(f["北緯"]), "lon": dm_to_deg(f["東経"]),
            "elevation_m": float(f["標高"].rstrip("m")),
            "ended": dt.date(*map(int, end.groups())) if end else None,
            "kansoku": m["kansoku"],
        }  # fmt: skip
    return list(seen.values())


def read(path: Path, station_name: str, elements: dict, header_rows: tuple):
    rows = list(csv.reader(io.StringIO(Path(path).read_bytes().decode("cp932"))))
    assert rows[0][0].startswith("ダウンロードした時刻"), path
    names, heads, subs = (rows[i] for i in header_rows)
    assert set(names[1:]) == {station_name}, (path, set(names[1:]))
    pos = [elements[h] + SUBS[s] for h, s in zip(heads[1:], subs[1:])]
    assert len(pos) == len(set(pos)), (path, pos)
    for k in elements.values():
        assert {k + "_mm", k + "_quality", k + "_homog"} <= set(pos), (path, pos)
    data = [r for r in rows[header_rows[2] + 1 :] if r]
    for r in data:
        assert len(r) == len(heads), (path, r)
    return rows[0][0].split("：", 1)[1], pos, data


def plan_hourly(daily_dir, sts: list[dict]) -> list[tuple[str, int, int]]:
    """Hourly requests are made for the years from the first to the last year with a daily precipitation value."""
    plan = []
    for s in sts:
        _, pos, data = read(Path(daily_dir) / f"{s['station_id']}.csv", s["station_name"], DAILY, (2, 3, 5))
        i = pos.index("precip_mm") + 1
        years = [int(r[0].split("/")[0]) for r in data if r[i] != ""]
        if years:
            plan.append((s["station_id"], min(years), max(years)))
    return plan


def _num(v: str, cast):
    return None if v == "" else cast(v)


def convert(mode: str, pref: int, stations_json, raw_dir, out_dir) -> dict:
    """mode daily: raw_dir/<station>.csv; mode hourly: raw_dir/<station>/<year>.csv. Writes <mode>.parquet,
    <mode>_files.parquet (and stations.parquet for daily). Stops if a CSV row is missing or a key is duplicated."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    st = stations(stations_json, pref)
    elements = DAILY if mode == "daily" else HOURLY
    header_rows = (2, 3, 5) if mode == "daily" else (2, 3, 4)
    key = "date" if mode == "daily" else "time_end"
    cols = ["station_id", key] + [k + s for k in elements.values() for s in SUBS.values()]
    acc: dict[str, list] = {c: [] for c in cols}
    files, total = [], 0
    for s in st:
        sid = s["station_id"]
        if mode == "daily":
            paths = [Path(raw_dir) / f"{sid}.csv"]
        else:
            paths = sorted((Path(raw_dir) / sid).glob("*.csv"))
        for p in paths:
            stamp, pos, data = read(p, s["station_name"], elements, header_rows)
            files.append({"station_id": sid, "file": p.name if mode == "daily" else f"{sid}/{p.name}",
                          "downloaded": stamp, "rows": len(data)})  # fmt: skip
            total += len(data)
            for r in data:
                acc["station_id"].append(sid)
                if mode == "daily":
                    y, m, d = map(int, r[0].split("/"))
                    acc[key].append(dt.date(y, m, d))
                else:
                    day, hms = r[0].split(" ")
                    y, m, d = map(int, day.split("/"))
                    acc[key].append(dt.datetime(y, m, d, int(hms.split(":")[0])))
                got = dict(zip(pos, r[1:]))
                for k in elements.values():
                    for s_, cast in [("_mm", float), ("_nophen", int), ("_quality", int), ("_homog", int)]:
                        acc[k + s_].append(_num(got.get(k + s_, ""), cast))
    types = {"station_id": pa.string(), "date": pa.date32(), "time_end": pa.timestamp("s")}
    for c in cols[2:]:
        types[c] = pa.float64() if c.endswith("_mm") else pa.int8()
    table = pa.table({c: pa.array(acc[c], type=types[c]) for c in cols})
    assert table.num_rows == total, (table.num_rows, total)
    assert len(set(zip(acc["station_id"], acc[key]))) == total, "duplicated (station, time)"
    table = table.append_column("pref", pa.array([pref] * total, type=pa.int8())).sort_by(
        [("station_id", "ascending"), (key, "ascending")]
    )
    if mode == "hourly":
        # one request per year: the homogeneity number restarts from 1 in each CSV and cannot be compared across years
        table = table.rename_columns([c.replace("_homog", "_homog_in_file") for c in table.column_names])
    pq.write_table(table, out / f"{mode}.parquet", compression="zstd")
    pq.write_table(pa.Table.from_pylist(files), out / f"{mode}_files.parquet")
    if mode == "daily":
        pq.write_table(pa.Table.from_pylist(st), out / "stations.parquet")
    return {"mode": mode, "stations": len(st), "files": len(files), "rows": total}
