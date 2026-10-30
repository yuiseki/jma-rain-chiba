#!/usr/bin/env bash
# usage: 04_fetch_hourly.sh PREF RAWDIR   hourly 降水量, one request per station and year (a ten year request is refused
# with HTTP 500), one at a time, 5 s apart. Existing files are skipped. A refused request is retried once after 60 s;
# a second refusal stops the run.
set -uo pipefail
. "$(dirname "$0")/common.sh"
pref=$1; raw=$(realpath "$2"); END_Y=${END_Y:-}; END_M=${END_M:-12}
cd "$raw"
jma_session
while IFS=$'\t' read -r st y0 y1; do
  mkdir -p "hourly/$st"
  for y in $(seq "$y0" "$y1"); do
    f=hourly/$st/$y.csv
    [ -s "$f" ] && continue
    if ! jma_table 9 '[["101",""]]' "$st" "$y" "$y" 1 "$([ "$y" = "$END_Y" ] && echo $END_M || echo 12)" "$f.part"; then
      echo "refused $st $y, waiting 60 s"; sleep 60; jma_session
      jma_table 9 '[["101",""]]' "$st" "$y" "$y" 1 "$([ "$y" = "$END_Y" ] && echo $END_M || echo 12)" "$f.part" || { echo "STOP $st $y"; exit 1; }
    fi
    mv "$f.part" "$f"; echo "ok $st $y"; sleep 5
  done
done < "hourly_plan_$pref.tsv"
echo "HOURLY DONE"
