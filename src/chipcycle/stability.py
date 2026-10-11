"""Stage 4: is the lead stable, or does it change with the cycle?

A single full-sample number hides a lot. The memory cycle of 2017-2019, the
COVID shock, the 2022-23 chip glut and the AI build-out since 2023 are very
different economies. If the lead only exists in one of them, that matters
more than the average.

Two views:
- Rolling windows: re-estimate the cross-correlation over a moving five-year
  window and track where it peaks.
- Regimes: split the sample at known breaks and compare the correlation at a
  fixed lag across them.

The AI break
------------
From 2023, Korean chip exports were driven increasingly by high-bandwidth
memory for AI data centers, while factory output elsewhere stayed weak. If
the signal is about the broad industrial cycle, that should show up as the
relationship weakening after 2023. That is a result worth reporting, not a
failure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from chipcycle.leadlag import ccf

REGIMES = {
    "2014-2019": ("2014-01", "2019-12"),
    "2020-2022": ("2020-01", "2022-12"),
    "2023-present (AI cycle)": ("2023-01", None),
}


def rolling_peak(x: pd.Series, y: pd.Series, window: int = 60, max_lag: int = 12, step: int = 1) -> pd.DataFrame:
    """For each window ending at month t: the lead (0..max_lag) with the largest |corr|."""
    df = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    rows = []
    # The window has to contain both x_t and y_{t+max_lag}.
    for end in range(window + max_lag, len(df) + 1, step):
        sub = df.iloc[end - window - max_lag : end]
        c = ccf(sub["x"], sub["y"], max_lag).loc[0:max_lag]
        if c.isna().all():
            continue
        k = int(c.abs().idxmax())
        rows.append({"end": df.index[end - 1], "peak_lag": k, "peak_corr": c.loc[k]})
    return pd.DataFrame(rows).set_index("end") if rows else pd.DataFrame(columns=["peak_lag", "peak_corr"])


def regime_table(x: pd.Series, y: pd.Series, lag: int, regimes: dict = REGIMES) -> pd.DataFrame:
    """corr(x_t, y_{t+lag}) inside each regime, with a 95% interval (Fisher z)."""
    pair = pd.concat([x.rename("x"), y.shift(-lag).rename("y")], axis=1).dropna()
    rows = []
    for name, (start, end) in regimes.items():
        sub = pair.loc[start:end]
        n = len(sub)
        if n < 12:
            continue
        r = sub["x"].corr(sub["y"])
        z, se = np.arctanh(r), 1 / np.sqrt(n - 3)
        rows.append(
            {
                "regime": name,
                "n": n,
                "corr": r,
                "ci_low": np.tanh(z - 1.96 * se),
                "ci_high": np.tanh(z + 1.96 * se),
            }
        )
    return pd.DataFrame(rows).set_index("regime")
