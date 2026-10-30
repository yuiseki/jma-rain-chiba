#!/usr/bin/env python3
"""usage: 08_profile.py PREF   -> docs/profile_PREF.json and docs/profile_PREF.md, measured on data/parquet/.

Everything the card says as a count is read from this file. The day of an hour is the date of time_end - 1 hour."""

import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).parents[1]
PQ = ROOT / "data" / "parquet"


def main() -> int:
    pref = int(sys.argv[1])
    d, h, s = f"{PQ}/daily/pref={pref}.parquet", f"{PQ}/hourly/pref={pref}.parquet", f"{PQ}/stations.parquet"
    con = duckdb.connect()
    q = lambda sql: con.execute(sql).fetchall()
    out: dict = {"pref": pref}
    out["rows"] = {
        "stations": q(f"select count(*) from read_parquet('{s}') where pref = {pref}")[0][0],
        "daily": q(f"select count(*) from read_parquet('{d}')")[0][0],
        "hourly": q(f"select count(*) from read_parquet('{h}')")[0][0],
    }
    out["stations"] = [
        dict(zip(["station_id", "station_name", "kind", "ended", "kansoku"], r))
        for r in q(
            f"select station_id, station_name, kind, ended, kansoku from read_parquet('{s}') "
            f"where pref = {pref} order by station_id"
        )
    ]
    per = {}
    for r in q(f"""select station_id,
        min(date) filter (where precip_mm is not null), max(date) filter (where precip_mm is not null),
        count(*) filter (where precip_mm is not null),
        min(date) filter (where max1h_mm is not null), min(date) filter (where max10m_mm is not null),
        count(*) filter (where max10m_mm is not null)
        from read_parquet('{d}') group by 1 order by 1"""):
        per[r[0]] = dict(zip(["first", "last", "days_with_value", "max1h_first", "max10m_first", "max10m_days"], r[1:]))
    for p in per.values():
        span = (p["last"] - p["first"]).days + 1
        p["missing_days_in_span"] = span - p["days_with_value"]
    for r in q(f"""select station_id, precip_homog, min(date), max(date), count(*) from read_parquet('{d}')
        where precip_homog is not null group by 1, 2 order by 1, 3"""):
        per[r[0]].setdefault("homog", []).append({"number": r[1], "from": r[2], "to": r[3], "days": r[4]})
    out["per_station_daily"] = per
    out["synop_zero_days"] = {
        "nophen_1_no_rain": q(f"select count(*) from read_parquet('{d}') where precip_nophen = 1")[0][0],
        "nophen_0_with_0_mm": q(f"select count(*) from read_parquet('{d}') where precip_nophen = 0 and precip_mm = 0")[
            0
        ][0],
    }
    # hourly against daily
    con.execute(f"""create table hd as select station_id, cast(time_end - interval 1 hour as date) as date,
        count(*) n, count(precip_mm) n_val, sum(precip_mm) s, max(precip_mm) mx
        from read_parquet('{h}') group by 1, 2""")
    con.execute(f"create table dd as select * from read_parquet('{d}')")
    out["hourly"] = {
        "station_years": q(
            f"select count(*) from (select station_id, year(time_end - interval 1 hour) from "
            f"read_parquet('{h}') group by 1, 2)"
        )[0][0],
        "first": str(q(f"select min(time_end) from read_parquet('{h}')")[0][0]),
        "last": str(q(f"select max(time_end) from read_parquet('{h}')")[0][0]),
        "null_values": q(f"select count(*) from read_parquet('{h}') where precip_mm is null")[0][0],
        "days_with_1_to_23_hours": q("select count(*) from hd where n between 1 and 23")[0][0],
        "days_with_24_hours": q("select count(*) from hd where n = 24")[0][0],
        "days_24_hours_daily_null": q(
            "select count(*) from hd join dd using (station_id, date) where hd.n = 24 and dd.precip_mm is null"
        )[0][0],
        "compared_days": q(
            "select count(*) from hd join dd using (station_id, date) where hd.n = 24 "
            "and hd.n_val = 24 and dd.precip_mm is not null"
        )[0][0],
        "sum_differs": q(
            "select count(*) from hd join dd using (station_id, date) where hd.n = 24 "
            "and hd.n_val = 24 and dd.precip_mm is not null and abs(hd.s - dd.precip_mm) > 0.05"
        )[0][0],
        "max1h_daily_larger": q(
            "select count(*) from hd join dd using (station_id, date) where hd.n_val > 0 "
            "and dd.max1h_mm is not null and dd.max1h_mm > hd.mx + 0.05"
        )[0][0],
        "max1h_daily_smaller": q(
            "select count(*) from hd join dd using (station_id, date) where hd.n_val > 0 "
            "and dd.max1h_mm is not null and dd.max1h_mm < hd.mx - 0.05"
        )[0][0],
    }
    out["hourly"]["sum_differs_by_station"] = {
        r[0]: [r[1], r[2], r[3]]
        for r in q(
            "select station_id, count(*), min(abs(hd.s - dd.precip_mm)), max(abs(hd.s - dd.precip_mm)) "
            "from hd join dd using (station_id, date) where hd.n = 24 and hd.n_val = 24 "
            "and dd.precip_mm is not null and abs(hd.s - dd.precip_mm) > 0.05 group by 1 order by 1"
        )
    }
    names = q(
        f"select station_name, list(station_id) from read_parquet('{s}') where pref = {pref} group by 1 "
        f"having count(*) > 1"
    )
    out["shared_names"] = {n: ids for n, ids in names}
    (ROOT / "docs" / f"profile_{pref}.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False, default=str) + "\n"
    )
    print(
        json.dumps(
            {k: out[k] for k in ("rows", "synop_zero_days", "hourly", "shared_names")}, ensure_ascii=False, default=str
        )[:1500]
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
