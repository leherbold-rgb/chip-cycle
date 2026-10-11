"""Fetchers. Every fetcher returns a float pd.Series with a sorted DatetimeIndex
holding the date the source uses for each observation, named by registry key."""

from __future__ import annotations

import pandas as pd

from chipcycle.registry import Series


def fetch(spec: Series, **kwargs) -> pd.Series:
    if spec.source == "fred":
        from chipcycle.ingest.fred import fetch_fred

        out = fetch_fred(spec.source_id, **kwargs)
    elif spec.source == "yahoo":
        from chipcycle.ingest.yahoo import fetch_yahoo

        out = fetch_yahoo(spec.source_id, **kwargs)
    elif spec.source == "csv":
        from chipcycle.ingest.manual import load_manual

        out = load_manual(spec.source_id, **kwargs)
    else:
        raise ValueError(f"unknown source {spec.source!r}")
    return out.rename(spec.key)
