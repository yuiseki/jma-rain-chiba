#!/usr/bin/env bash
# usage: 01_stations.sh PREF RAWDIR   -> RAWDIR/stations_PREF.json (POST top/station, as the page does)
set -euo pipefail
. "$(dirname "$0")/common.sh"
pref=$1; raw=$2
mkdir -p "$raw"
cd "$raw"
jma_session
sleep 2
curl -sS --fail -A "$UA" -b "$COOKIES" -c "$COOKIES" -X POST "$JMA/top/station" \
  -H 'Origin: https://www.data.jma.go.jp' -H "Referer: $JMA/index.php" --data-urlencode "pd=$pref" -o "stations_$pref.json"
python3 -c "import json,sys;d=json.load(open('stations_$pref.json'));print(len({m['stid'] for m in d['markers'] if m['kind']=='station'}),'stations')"
