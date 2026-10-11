"""UN Comtrade monthly trade by HS code.

Korea reports its customs trade to the UN by HS commodity code, which gives a
free, consistent monthly history:

    8542    electronic integrated circuits (all chips)
    854232  memories (DRAM, NAND), the Micron-relevant slice

Without a key we use the public preview endpoint, which caps each response at
500 rows. One year of one code is 12 rows, so we ask a year at a time. Set
COMTRADE_KEY to a free registered key to use the full endpoint instead.

Comtrade itself posts data a month or more after Korea publishes it. For the
newest months, Korea Customs Service is the timelier source.
"""

from __future__ import annotations

import os
import time

import pandas as pd
import requests

PREVIEW_URL = "https://comtradeapi.un.org/public/v1/preview/C/M/HS"
KEYED_URL = "https://comtradeapi.un.org/data/v1/get/C/M/HS"

# Rows that represent the national total rather than a breakdown.
TOTAL_FILTERS = {"partnerCode": 0, "partner2Code": 0, "motCode": 0, "customsCode": "C00"}


def parse_comtrade(payload: dict) -> pd.Series:
    rows = payload.get("data") or []
    if not rows:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([], name="date"))
    df = pd.DataFrame(rows)
    for col, total in TOTAL_FILTERS.items():
        if col in df.columns:
            df = df[df[col].astype(str) == str(total)]
    dates = pd.to_datetime(df["period"].astype(str), format="%Y%m")
    if dates.duplicated().any():
        raise ValueError("Comtrade returned more than one total row for a month")
    s = pd.Series(
        pd.to_numeric(df["primaryValue"], errors="coerce").to_numpy(dtype=float),
        index=pd.DatetimeIndex(dates, name="date"),
    )
    return s.dropna().sort_index()


def _get(params: dict, key: str | None, timeout: float) -> dict:
    url, headers = (KEYED_URL, {"Ocp-Apim-Subscription-Key": key}) if key else (PREVIEW_URL, {})
    for attempt in range(3):
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 429:  # rate limited: back off and retry
            time.sleep(5 * (attempt + 1))
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return resp.json()


def fetch_comtrade(
    source_id: str,
    start_year: int = 2010,
    end_year: int | None = None,
    timeout: float = 60,
    pause: float = 1.5,
) -> pd.Series:
    """source_id is "reporter:hs_code:flow", e.g. "410:8542:X" (Korea chip exports)."""
    reporter, cmd, flow = source_id.split(":")
    key = os.environ.get("COMTRADE_KEY")
    end_year = end_year or pd.Timestamp.today().year
    parts = []
    for year in range(start_year, end_year + 1):
        params = {
            "reporterCode": reporter,
            "cmdCode": cmd,
            "flowCode": flow,
            "partnerCode": 0,  # world
            "period": ",".join(f"{year}{m:02d}" for m in range(1, 13)),
        }
        parts.append(parse_comtrade(_get(params, key, timeout)))
        time.sleep(pause)  # the preview endpoint is shared; be polite
    parts = [p for p in parts if not p.empty]
    if not parts:
        raise RuntimeError(f"Comtrade returned no data for {source_id}")
    return pd.concat(parts).sort_index()
