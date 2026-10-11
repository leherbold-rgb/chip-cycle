"""UN Comtrade monthly trade by HS code.

Korea reports its customs trade to the UN by HS commodity code, which gives a
free, consistent monthly history from 2013:

    8542    electronic integrated circuits (all chips)
    854232  memories (DRAM, NAND), the Micron-relevant slice

Without a key we use the public preview endpoint, which accepts only one month
per request but several HS codes. So we fetch every Comtrade series for the
same reporter in one pass, one request per month, and keep the result in
memory so the second series costs nothing. Set COMTRADE_KEY to a free
registered key to use the full endpoint instead.

Comtrade itself posts data a few months after Korea publishes it. For the
newest months, Korea Customs Service is the timelier source.
"""

from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests

PREVIEW_URL = "https://comtradeapi.un.org/public/v1/preview/C/M/HS"
KEYED_URL = "https://comtradeapi.un.org/data/v1/get/C/M/HS"
FIRST_MONTH = "2013-01"
CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "comtrade"

# Rows that represent the national total rather than a breakdown.
TOTAL_FILTERS = {"partnerCode": 0, "partner2Code": 0, "motCode": 0, "customsCode": "C00"}


def parse_comtrade(payload: dict) -> pd.DataFrame:
    """Return one row per (month, HS code) national total: columns date, cmd, value."""
    rows = payload.get("data") or []
    if not rows:
        return pd.DataFrame(columns=["date", "cmd", "value"])
    df = pd.DataFrame(rows)
    for col, total in TOTAL_FILTERS.items():
        if col in df.columns:
            df = df[df[col].astype(str) == str(total)]
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["period"].astype(str), format="%Y%m"),
            "cmd": df["cmdCode"].astype(str),
            "value": pd.to_numeric(df["primaryValue"], errors="coerce"),
        }
    ).dropna()
    if out.duplicated(["date", "cmd"]).any():
        raise ValueError("Comtrade returned more than one total row for a month")
    return out


def _get(params: dict, timeout: float) -> dict:
    key = os.environ.get("COMTRADE_KEY")
    url, headers = (KEYED_URL, {"Ocp-Apim-Subscription-Key": key}) if key else (PREVIEW_URL, {})
    for attempt in range(10):
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 429:  # rate limited: wait as told, or back off
            wait = float(resp.headers.get("Retry-After", 10 * (attempt + 1)))
            time.sleep(min(wait, 120))
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return resp.json()


@lru_cache(maxsize=8)
def _fetch_panel(reporter: str, flow: str, cmds: tuple[str, ...], start: str, end: str) -> pd.DataFrame:
    frames = []
    months = pd.period_range(start, end, freq="M")
    # One small file per month, so an interrupted download resumes where it
    # stopped. Recent months are refetched because Comtrade fills them in late.
    month_dir = CACHE_DIR / f"{reporter}_{flow}_{'-'.join(cmds)}"
    month_dir.mkdir(parents=True, exist_ok=True)
    fresh_after = pd.Period(pd.Timestamp.today(), "M") - 12
    for i, month in enumerate(months):
        path = month_dir / f"{month.strftime('%Y%m')}.json"
        if path.exists() and month < fresh_after:
            payload = json.loads(path.read_text())
        else:
            params = {
                "reporterCode": reporter,
                "cmdCode": ",".join(cmds),
                "flowCode": flow,
                "partnerCode": 0,  # world
                "period": month.strftime("%Y%m"),
            }
            payload = _get(params, timeout=60)
            path.write_text(json.dumps({"data": payload.get("data") or []}))
            time.sleep(1.2)  # the preview endpoint is shared; be polite
        frames.append(parse_comtrade(payload))
        if (i + 1) % 24 == 0:
            print(f"    comtrade: {i + 1}/{len(months)} months", flush=True)
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["date", "cmd", "value"])
    return pd.concat(frames, ignore_index=True)


def fetch_comtrade(source_id: str, start: str = FIRST_MONTH, end: str | None = None) -> pd.Series:
    """source_id is "reporter:hs_code:flow", e.g. "410:8542:X" (Korea chip exports)."""
    from chipcycle.registry import REGISTRY

    reporter, cmd, flow = source_id.split(":")
    # Every Comtrade code for this reporter and flow, so one pass serves them all.
    siblings = sorted(
        {
            s.source_id.split(":")[1]
            for s in REGISTRY.values()
            if s.source == "comtrade" and s.source_id.split(":")[::2] == [reporter, flow]
        }
        | {cmd}
    )
    end = end or pd.Timestamp.today().strftime("%Y-%m")
    panel = _fetch_panel(reporter, flow, tuple(siblings), start, end)
    rows = panel[panel["cmd"] == cmd]
    if rows.empty:
        raise RuntimeError(f"Comtrade returned no data for {source_id}")
    s = pd.Series(rows["value"].to_numpy(dtype=float), index=pd.DatetimeIndex(rows["date"], name="date"))
    return s.sort_index()
