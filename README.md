# London City Airport (EGLC) historic METAR

Raw and parsed METAR observations for **EGLC** (London City Airport), the station Polymarket uses to resolve London daily high-temperature markets.

## Files

| File | Description |
|------|-------------|
| `data/EGLC_metar_hourly.csv` | Parsed observations (UTC time, temperature, wind, pressure, dewpoint, visibility, raw `metar` text) |
| `data/EGLC_metar_reports.txt` | Raw METAR strings, one report per line (`timestamp TAB report`) |
| `data/EGLC_daily.csv` | Daily max/min temperature (°C) derived from METAR |

## Coverage

- **Station:** EGLC (London City Airport, ICAO)
- **Source:** [Iowa Environmental Mesonet](https://mesonet.agron.iastate.edu/) ASOS archive (free, no API key)
- **Hourly METAR:** 2020-01-01 → 2026-10-04 UTC (58,910 reports in current bundle)
- **Daily max/min:** 2020-01-01 → latest day in `EGLC_daily.csv` (IEM daily summary)
- **Cadence:** roughly hourly AUTO METAR

Temperature in METAR text is whole-degree °C (e.g. `15/10` → 15 °C). Polymarket resolution uses `floor(daily_max_temp_c)` from the official daily summary; `EGLC_daily.csv` aligns with IEM daily extracts.

## Refresh data

```bash
pip install -r requirements.txt
python scripts/fetch_eglc_metar.py
python scripts/fetch_eglc_metar.py --start 2020-01-01 --full-refresh
```

Incremental runs merge into existing CSV files under `data/`.

## License

Observation data is provided by third-party government and academic sources (IEM / UK Met Office network). This repository is a curated mirror for research and forecasting; verify critical use cases against primary sources.
