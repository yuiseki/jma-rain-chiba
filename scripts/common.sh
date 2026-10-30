# Shared by the fetch scripts of jma-rain-kanto. Source it; it sets UA and the cookie jar.
JMA=https://www.data.jma.go.jp/risk/obsdl
UA="Mozilla/5.0 (research; yuiseki)"
COOKIES=${COOKIES:-cookies.txt}

jma_session() {  # a session cookie from the index page, as a browser does
  curl -sS --fail -A "$UA" -c "$COOKIES" -o /dev/null "$JMA/index.php"
}

# jma_table AGGRG ELEMENTS STATION Y0 Y1 M0 M1 OUT: POST /show/table, the same form the page sends
jma_table() {
  local aggrg=$1 elements=$2 st=$3 y0=$4 y1=$5 m0=$6 m1=$7 out=$8
  local last
  last=$(python3 -c "import calendar;print(calendar.monthrange($y1,$m1)[1])")
  curl -sS --fail -A "$UA" -b "$COOKIES" -c "$COOKIES" -o "$out" -X POST "$JMA/show/table" \
    -H 'Origin: https://www.data.jma.go.jp' -H "Referer: $JMA/index.php" -H 'Accept: text/html,application/xhtml+xml' \
    --data-urlencode "stationNumList=[\"$st\"]" --data-urlencode "aggrgPeriod=$aggrg" \
    --data-urlencode "elementNumList=$elements" --data-urlencode 'interAnnualType=1' \
    --data-urlencode "ymdList=[\"$y0\",\"$y1\",\"$m0\",\"$m1\",\"1\",\"$last\"]" \
    --data-urlencode 'option={"list":["obs"],"nyear":0}' --data-urlencode 'downloadFlag=true' \
    --data-urlencode 'rmkFlag=1' --data-urlencode 'disconnectFlag=1' --data-urlencode 'youbiFlag=0' \
    --data-urlencode 'fukenFlag=0' --data-urlencode 'kijiFlag=0' --data-urlencode 'csvFlag=1' \
    --data-urlencode 'jikantaiFlag=0' --data-urlencode 'jikantaiList=[]' --data-urlencode 'ymdLiteral=1'
  head -c 30 "$out" | iconv -f cp932 -t utf-8 | grep -q 'ダウンロードした時刻' || {
    echo "not a csv: $out" >&2; head -c 300 "$out" | iconv -f cp932 -t utf-8 -c >&2; return 1; }
}
