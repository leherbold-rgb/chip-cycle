"""Recent months that the automated sources don't have yet.

UN Comtrade posts Korean customs data several months late, so the HS 8542
series stops at December 2025. Korea's trade ministry publishes the previous
month's semiconductor exports and the year-over-year change on the 1st of
each month. Those figures were transcribed from press reports into
data/manual/kr_semi_motr.csv with a source and a confidence for each row.

The ministry counts a broader chip category than HS 8542, so its dollar
levels run about 22% higher. Its growth rates agree with the HS series
closely (December 2025: 43.2% reported vs. 43.3% from HS 8542). So the two
are joined on growth, not on levels: each new month is the HS level from a
year earlier times the reported growth.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from chipcycle.ingest.manual import MANUAL_DIR


def load_reported(filename: str = "kr_semi_motr.csv", directory=None) -> pd.DataFrame:
    """Reported monthly level (USD) and YoY change (%), indexed by month end."""
    df = pd.read_csv((directory or MANUAL_DIR) / filename)
    df["date"] = pd.to_datetime(df["date"]) + pd.offsets.MonthEnd(0)
    return df.set_index("date").sort_index()


def extend_by_growth(base: pd.Series, reported: pd.DataFrame) -> pd.Series:
    """Append months after the end of `base` by chaining reported YoY growth.

    Each new month = level of the same month a year earlier x (1 + growth).
    The year-earlier level comes from `base` or from months added earlier in
    this loop, so the chain can run more than a year.
    """
    out = base.sort_index().copy()
    for date, row in reported.sort_index().iterrows():
        if date <= out.index.max():
            continue
        prior = date - pd.DateOffset(years=1) + pd.offsets.MonthEnd(0)
        if prior not in out.index:
            raise ValueError(f"no level a year before {date:%Y-%m} to apply growth to")
        out[date] = out[prior] * (1 + row["yoy_pct"] / 100)
    return out.sort_index()


def to_percent(log_points):
    """Convert log growth (the model's unit) to ordinary percent growth."""
    return 100 * np.expm1(log_points / 100)
