"""Local parquet cache so analysis never depends on a live network call."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from chipcycle.ingest import fetch
from chipcycle.registry import Series

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def cache_path(spec: Series, directory: Path | None = None) -> Path:
    return (directory or RAW_DIR) / f"{spec.key}.parquet"


def save(s: pd.Series, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    s.to_frame("value").to_parquet(path)


def load(path: Path) -> pd.Series:
    return pd.read_parquet(path)["value"].rename(path.stem)


def load_or_fetch(spec: Series, refresh: bool = False, directory: Path | None = None) -> pd.Series:
    path = cache_path(spec, directory)
    # Manual CSVs are already local; always re-read them so edits show up.
    if spec.source != "csv" and path.exists() and not refresh:
        return load(path)
    s = fetch(spec)
    save(s, path)
    return s
