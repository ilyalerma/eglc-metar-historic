#!/usr/bin/env python3
"""Download EGLC METAR history from Iowa Environmental Mesonet into ./data/."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

STATION = "EGLC"
NETWORK = "GB__ASOS"
BASE_HOURLY = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
BASE_DAILY = "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CHUNK_DAYS = 180
OVERLAP_DAYS = 2


def fetch_hourly(station: str, start: date, end: date) -> pd.DataFrame:
    params = {
        "station": station,
        "data": "tmpf,dwpf,relh,drct,sknt,alti,mslp,vsby,gust,metar",
        "year1": start.year,
        "month1": start.month,
        "day1": start.day,
        "year2": end.year,
        "month2": end.month,
        "day2": end.day,
        "tz": "Etc/UTC",
        "format": "comma",
        "latlon": "no",
        "elev": "no",
        "missing": "M",
        "trace": "T",
        "direct": "no",
        "report_type": "3",
    }
    resp = requests.get(BASE_HOURLY, params=params, timeout=120)
    resp.raise_for_status()
    lines = resp.text.strip().split("\n")
    header_idx = next((i for i, line in enumerate(lines) if line.startswith("station")), 0)
    df = pd.read_csv(StringIO("\n".join(lines[header_idx:])), na_values=["M"])
    if not df.empty and "valid" in df.columns:
        df["valid"] = pd.to_datetime(df["valid"], utc=True, errors="coerce")
        if "tmpf" in df.columns:
            df["tmp_c"] = (df["tmpf"].astype(float) - 32) * 5 / 9
        if "dwpf" in df.columns:
            df["dwp_c"] = (df["dwpf"].astype(float) - 32) * 5 / 9
    return df


def fetch_daily(station: str, start: date, end: date) -> pd.DataFrame:
    params = {
        "network": NETWORK,
        "stations": station,
        "year1": start.year,
        "month1": start.month,
        "day1": start.day,
        "year2": end.year,
        "month2": end.month,
        "day2": end.day,
        "var": "max_temp_f,min_temp_f",
        "format": "csv",
    }
    resp = requests.get(BASE_DAILY, params=params, timeout=120)
    resp.raise_for_status()
    df = pd.read_csv(StringIO(resp.text.strip()))
    if df.empty:
        return df
    df["day"] = pd.to_datetime(df["day"])
    df["max_temp_c"] = ((df["max_temp_f"].astype(float) - 32) * 5 / 9).round().astype("Int64")
    df["min_temp_c"] = ((df["min_temp_f"].astype(float) - 32) * 5 / 9).round().astype("Int64")
    return df[["station", "day", "max_temp_c", "min_temp_c"]]


def chunk_ranges(start: date, end: date) -> list[tuple[date, date]]:
    ranges: list[tuple[date, date]] = []
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
        ranges.append((cur, chunk_end))
        cur = chunk_end + timedelta(days=1)
    return ranges


def merge_frames(existing: pd.DataFrame, new: pd.DataFrame, key: list[str]) -> pd.DataFrame:
    if existing.empty:
        return new
    if new.empty:
        return existing
    combined = pd.concat([existing, new], ignore_index=True)
    return combined.drop_duplicates(subset=key).sort_values(key[-1]).reset_index(drop=True)


def write_reports_txt(df: pd.DataFrame, path: Path) -> None:
    lines = []
    for _, row in df.iterrows():
        ts = row.get("valid")
        metar = row.get("metar")
        if pd.notna(ts) and pd.notna(metar):
            ts_str = pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"{ts_str}\t{metar}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--full-refresh", action="store_true")
    parser.add_argument("--skip-daily", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log = logging.getLogger(__name__)

    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else date.today()
    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    hourly_path = DATA_DIR / f"{STATION}_metar_hourly.csv"
    txt_path = DATA_DIR / f"{STATION}_metar_reports.txt"
    daily_path = DATA_DIR / f"{STATION}_daily.csv"

    existing = pd.DataFrame()
    fetch_start = start
    if hourly_path.exists() and not args.full_refresh:
        existing = pd.read_csv(hourly_path, parse_dates=["valid"])
        if not existing.empty:
            last = pd.Timestamp(existing["valid"].max()).date()
            fetch_start = max(start, last - timedelta(days=OVERLAP_DAYS))
            log.info("Cache through %s; fetching from %s", last, fetch_start)

    frames = []
    for s, e in chunk_ranges(fetch_start, end):
        log.info("Hourly %s → %s", s, e)
        part = fetch_hourly(STATION, s, e)
        if not part.empty:
            frames.append(part)
    new = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    hourly = merge_frames(existing, new, ["station", "valid"])
    hourly.to_csv(hourly_path, index=False)
    write_reports_txt(hourly, txt_path)
    log.info("Hourly: %d rows → %s", len(hourly), hourly_path.name)

    if not args.skip_daily:
        daily = fetch_daily(STATION, start, end)
        daily.to_csv(daily_path, index=False)
        log.info("Daily: %d rows → %s", len(daily), daily_path.name)


if __name__ == "__main__":
    main()
