"""Tests of the planning and conversion helpers with small synthetic CSVs in the JMA's cp932 layout."""

import datetime as dt
import json

import jma
import pyarrow.parquet as pq
import pytest

DAILY_AMEDAS = (
    "ダウンロードした時刻：2026/10/30 10:00:00\n\n"
    ",{n},{n},{n},{n},{n},{n},{n},{n},{n}\n"
    "年月日,降水量の合計(mm),降水量の合計(mm),降水量の合計(mm),1時間降水量の最大(mm),1時間降水量の最大(mm),"
    "1時間降水量の最大(mm),10分間降水量の最大(mm),10分間降水量の最大(mm),10分間降水量の最大(mm)\n"
    ",,,,,,,,,\n"
    ",,品質情報,均質番号,,品質情報,均質番号,,品質情報,均質番号\n"
)
HOURLY_AMEDAS = (
    "ダウンロードした時刻：2026/10/30 11:00:00\n\n,{n},{n},{n}\n年月日時,降水量(mm),降水量(mm),降水量(mm)\n"
    ",,品質情報,均質番号\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("cp932"))


def station_json(path, stations):
    markers = []
    for stid, name, kansoku, ended in stations:
        title = f"地点名：{name}\nカナ:ア\n北緯：35度30.0分\n東経：140度6.0分\n標高：10m"
        if ended:
            title += f"\n{ended}に観測終了"
        markers.append(
            {
                "kind": "station",
                "stid": stid,
                "stname": name,
                "prid": "45",
                "kansoku": kansoku,
                "ended": bool(ended),
                "title": title,
            }
        )
    # the list repeats every station (a map marker and a table entry)
    path.write_text(json.dumps({"markers": markers + markers}), encoding="utf-8")


def test_stations_are_unique_and_carry_the_prefecture(tmp_path):
    p = tmp_path / "s.json"
    station_json(p, [("a0001", "銚子", "111201", None), ("s47682", "千葉", "111211", "2001年03月04日")])
    st = jma.stations(p, 45)
    assert [s["station_id"] for s in st] == ["a0001", "s47682"]
    assert st[0]["pref"] == 45 and st[0]["kind"] == "amedas" and st[1]["kind"] == "synop"
    assert st[1]["ended"] == dt.date(2001, 3, 4) and st[0]["ended"] is None
    assert st[0]["lat"] == pytest.approx(35.5) and st[0]["lon"] == pytest.approx(140.1)


def test_station_of_another_prefecture_is_refused(tmp_path):
    p = tmp_path / "s.json"
    station_json(p, [("a0001", "銚子", "111201", None)])
    with pytest.raises(AssertionError):
        jma.stations(p, 44)


def test_plan_runs_from_first_to_last_year_with_a_daily_precip_value(tmp_path):
    n = "銚子"
    rows = [
        "1974/12/31,,0,1,,0,1,,0,1",
        "1975/1/1,0,8,1,0,8,1,,0,1",
        "1975/6/1,,0,1,,0,1,,0,1",
        "1977/3/3,1.5,8,1,1.0,8,1,,0,1",
        "1978/1/1,,0,1,,0,1,,0,1",
    ]
    write(tmp_path / "daily" / "a0001.csv", DAILY_AMEDAS.format(n=n) + "\n".join(rows) + "\n")
    plan = jma.plan_hourly(tmp_path / "daily", [{"station_id": "a0001", "station_name": n}])
    assert plan == [("a0001", 1975, 1977)]


def test_plan_of_a_station_without_any_value_is_empty(tmp_path):
    write(tmp_path / "daily" / "a0002.csv", DAILY_AMEDAS.format(n="X") + "1974/1/1,,0,1,,0,1,,0,1\n")
    assert jma.plan_hourly(tmp_path / "daily", [{"station_id": "a0002", "station_name": "X"}]) == []


def test_hourly_convert_counts_rows_and_keeps_blank_as_null(tmp_path):
    n = "銚子"
    st = tmp_path / "s.json"
    station_json(st, [("a0001", n, "111201", None)])
    rows = "1976/1/1 1:00:00,0,8,1\n1976/1/1 2:00:00,,1,1\n1977/1/1 00:00:00,2.5,8,1\n"
    write(tmp_path / "raw" / "a0001" / "1976.csv", HOURLY_AMEDAS.format(n=n) + rows)
    out = tmp_path / "out"
    jma.convert("hourly", 45, st, tmp_path / "raw", out)
    t = pq.read_table(out / "hourly.parquet").to_pylist()
    assert [r["time_end"] for r in t] == [
        dt.datetime(1976, 1, 1, 1),
        dt.datetime(1976, 1, 1, 2),
        dt.datetime(1977, 1, 1, 0),
    ]
    assert [r["precip_mm"] for r in t] == [0.0, None, 2.5]
    assert all(r["pref"] == 45 for r in t) and "precip_homog_in_file" in t[0]


def test_daily_convert_reads_amedas_without_nophen_and_synop_with_it(tmp_path):
    st = tmp_path / "s.json"
    station_json(st, [("a0001", "銚子", "111201", None), ("s47682", "千葉", "111211", None)])
    write(tmp_path / "raw" / "a0001.csv", DAILY_AMEDAS.format(n="銚子") + "1974/1/1,3.0,8,1,1.0,8,1,0.5,8,1\n")
    head = ["年月日"] + ["降水量の合計(mm)"] * 4 + ["1時間降水量の最大(mm)"] * 4 + ["10分間降水量の最大(mm)"] * 4
    sub = [""] + ["", "現象なし情報", "品質情報", "均質番号"] * 3
    text = (
        "ダウンロードした時刻：2026/10/30 10:00:00\n\n,"
        + ",".join(["千葉"] * 12)
        + "\n"
        + ",".join(head)
        + "\n"
        + "," * 12
        + "\n"
        + ",".join(sub)
        + "\n"
        + "1974/1/1,0,1,8,1,0,1,8,1,0,1,8,1\n"
    )
    write(tmp_path / "raw" / "s47682.csv", text)
    out = tmp_path / "out"
    jma.convert("daily", 45, st, tmp_path / "raw", out)
    t = {r["station_id"]: r for r in pq.read_table(out / "daily.parquet").to_pylist()}
    assert t["a0001"]["precip_nophen"] is None and t["a0001"]["precip_mm"] == 3.0
    assert t["s47682"]["precip_nophen"] == 1 and t["s47682"]["max10m_quality"] == 8
    assert pq.read_table(out / "stations.parquet").num_rows == 2


def test_duplicate_keys_stop_the_conversion(tmp_path):
    n = "銚子"
    st = tmp_path / "s.json"
    station_json(st, [("a0001", n, "111201", None)])
    rows = "1976/1/1 1:00:00,0,8,1\n1976/1/1 1:00:00,0,8,1\n"
    write(tmp_path / "raw" / "a0001" / "1976.csv", HOURLY_AMEDAS.format(n=n) + rows)
    with pytest.raises(AssertionError):
        jma.convert("hourly", 45, st, tmp_path / "raw", tmp_path / "out")
