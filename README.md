# jma-rain-chiba

Scripts that fetch, build and verify the rainfall of the 18 stations of the Japan Meteorological Agency in Chiba
(daily and hourly, 1974 to September 2026) from the JMA's 過去の気象データ・ダウンロード, and publish it.

The data and its card are on Hugging Face: <https://huggingface.co/datasets/yuiseki/jma-rain-chiba>
(published at revision `7a23cd0b738c016c243863903b6bdafc7963ab06`; `docs/revision.json`).

- `scripts/02_fetch_daily.sh`, `04_fetch_hourly.sh`: fetch, one request at a time, taking a JMA prefecture number (45 is Chiba).
- `scripts/05_build.py`, `06_verify.py`: build the Parquet and check it against the CSVs with a second reader.
- `scripts/10_verify_hub.py`: read the Hub copy back at the recorded revision and compare it with the local one.

The code is offered as is; the data is CC BY 4.0 with the credit to the JMA (see the card).
