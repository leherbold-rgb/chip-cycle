"""Reference periods, release dates, and the two panels built from them.

There are two different questions you can ask of the same data, and they need
two different tables:

1. "Does chip activity in month m move ahead of industrial production in
   month m+k?" This is about the economy itself. Use `reference_panel`: one
   row per month, each value filed under the month it describes.

2. "On a given day, what could an investor actually have known?" This is
   about forecasting and trading. Use `realtime_panel`: one row per decision
   date, each value being the latest one published by that date.

Mixing them up is how look-ahead bias gets in.
"""

from __future__ import annotations

from typing import NamedTuple

import pandas as pd

from chipcycle.registry import Series


def to_monthly(s: pd.Series, freq: str, how: str = "mean") -> pd.Series:
    """Collapse a series to one value per calendar month, indexed by month end.

    Daily and weekly data are averaged by default, which smooths noise and
    matches how monthly economic data describe a whole month. Use how="last"
    for a month-end snapshot instead.
    """
    if freq == "M":
        out = s.copy()
        out.index = out.index.to_period("M").to_timestamp(how="end").normalize()
        if out.index.duplicated().any():
            raise ValueError(f"{s.name}: more than one value per month")
        return out
    if freq == "Q":
        raise ValueError("quarterly series are not resampled to monthly")
    grouped = s.groupby(s.index.to_period("M"))
    out = grouped.mean() if how == "mean" else grouped.last()
    out.index = out.index.to_timestamp(how="end").normalize()
    return out.rename(s.name)


def release_dates(monthly: pd.Series, spec: Series) -> pd.DataFrame:
    """Attach the approximate public release date to each monthly value."""
    return pd.DataFrame(
        {
            "value": monthly.to_numpy(),
            "reference_month": monthly.index,
            "available": monthly.index + pd.Timedelta(days=spec.release_lag_days),
        }
    )


def reference_panel(raw: dict[str, pd.Series], specs: dict[str, Series]) -> pd.DataFrame:
    """One row per month, every series filed under the month it describes."""
    cols = {k: to_monthly(s, specs[k].freq) for k, s in raw.items()}
    panel = pd.DataFrame(cols).sort_index()
    panel.index.name = "month"
    return panel


def monthly_decision_dates(start: str, end: str, day: int = 2) -> pd.DatetimeIndex:
    """The `day`-th calendar day of every month between start and end.

    The default of day 2 is deliberate: Korea's trade ministry publishes the
    previous month's exports on the 1st, while US industrial production for
    that month is not out until around the 16th. Day 2 is when the chip signal
    has its largest head start. At month end both are a month stale and the
    edge disappears.
    """
    months = pd.period_range(start, end, freq="M")
    return pd.DatetimeIndex([m.to_timestamp() + pd.Timedelta(days=day - 1) for m in months])


class RealtimePanel(NamedTuple):
    values: pd.DataFrame  # latest published value per series at each decision date
    reference_month: pd.DataFrame  # which month that value describes
    months_stale: pd.DataFrame  # whole months between the decision date and that month


def realtime_panel(
    raw: dict[str, pd.Series],
    specs: dict[str, Series],
    decision_dates: pd.DatetimeIndex,
) -> RealtimePanel:
    """For each decision date, take only values already published by then."""
    left = pd.DataFrame({"decision_date": pd.DatetimeIndex(decision_dates).sort_values()})
    values, refs = {}, {}
    for key, s in raw.items():
        rel = release_dates(to_monthly(s, specs[key].freq), specs[key]).sort_values("available")
        # Backward as-of join: the most recent row whose release date is on or
        # before the decision date. Strictly nothing from the future.
        merged = pd.merge_asof(
            left, rel, left_on="decision_date", right_on="available", direction="backward"
        )
        values[key] = merged["value"].to_numpy()
        refs[key] = merged["reference_month"].to_numpy()
    idx = pd.DatetimeIndex(left["decision_date"], name="decision_date")
    v = pd.DataFrame(values, index=idx)
    r = pd.DataFrame(refs, index=idx)
    dec_p = idx.to_period("M")
    stale = pd.DataFrame(
        {
            k: [
                (d - pd.Timestamp(m).to_period("M")).n if pd.notna(m) else pd.NA
                for d, m in zip(dec_p, r[k])
            ]
            for k in r.columns
        },
        index=idx,
    )
    return RealtimePanel(v, r, stale)
