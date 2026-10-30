#!/usr/bin/env bash
# usage: 02_fetch_daily.sh PREF RAWDIR   one request per station, 1974-01-01 to END_Y-END_M (default 2025-12), one at a time.
# Daily: 降水量の合計, 1時間降水量の最大, 10分間降水量の最大. A file that exists is skipped. A refused request is
# retried once after 60 s; a second refusal stops the run (never circumvent a block).
set -uo pipefail
. "$(dirname "$0")/common.sh"
pref=$1; raw=$(realpath "$2"); END_Y=${END_Y:-2025}; END_M=${END_M:-12}
here=$(dirname "$(realpath "$0")")
mkdir -p "$raw/daily"
cd "$raw"
jma_session
for st in $(python3 - <<P
import sys; sys.path.insert(0, "$here")
import jma
print(" ".join(s["station_id"] for s in jma.stations("stations_$pref.json", $pref)))
P
); do
  f=daily/$st.csv
  [ -s "$f" ] && continue
  if ! jma_table 1 '[["101",""],["105","1"],["105","10"]]' "$st" 1974 "$END_Y" 1 "$END_M" "$f.part"; then
    echo "refused $st, waiting 60 s"; sleep 60; jma_session
    jma_table 1 '[["101",""],["105","1"],["105","10"]]' "$st" 1974 "$END_Y" 1 "$END_M" "$f.part" || { echo "STOP $st"; exit 1; }
  fi
  mv "$f.part" "$f"; echo "ok $st"; sleep 5
done
echo "DAILY DONE"
