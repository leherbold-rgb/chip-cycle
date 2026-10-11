"""Hand-collected series that have no clean free API, read from data/manual/.

Expected format: a CSV with columns `date,value`, one row per month, `date`
being any day inside the reference month (e.g. 2024-03-01 for March 2024).
See data/manual/README.md for where each file comes from.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

MANUAL_DIR = Path(__file__).resolve().parents[3] / "data" / "manual"


def load_manual(filename: str, directory: Path | None = None) -> pd.Series:
    path = (directory or MANUAL_DIR) / filename
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. See data/manual/README.md for how to build it."
        )
    df = pd.read_csv(path)
    missing = {"date", "value"} - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
    s = pd.Series(
        pd.to_numeric(df["value"], errors="coerce").to_numpy(dtype=float),
        index=pd.DatetimeIndex(pd.to_datetime(df["date"]), name="date"),
    )
    s = s.dropna().sort_index()
    if s.index.duplicated().any():
        raise ValueError(f"{path.name} has duplicate dates")
    return s
