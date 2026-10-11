"""FRED via the public graph CSV endpoint. No API key needed."""

from __future__ import annotations

import io

import pandas as pd
import requests

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def parse_fred_csv(text: str) -> pd.Series:
    # FRED has used both "DATE" and "observation_date" as the first header,
    # and writes missing values as ".".
    df = pd.read_csv(io.StringIO(text), na_values=["."])
    date_col, value_col = df.columns[0], df.columns[1]
    s = pd.Series(
        pd.to_numeric(df[value_col], errors="coerce").to_numpy(dtype=float),
        index=pd.DatetimeIndex(pd.to_datetime(df[date_col]), name="date"),
    )
    return s.dropna().sort_index()


def fetch_fred(series_id: str, timeout: float = 30) -> pd.Series:
    resp = requests.get(FRED_CSV, params={"id": series_id}, timeout=timeout)
    resp.raise_for_status()
    return parse_fred_csv(resp.text)
