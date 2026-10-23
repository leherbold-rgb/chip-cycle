"""Where is the memory cycle now, and how does it compare with past ones?

Nothing here forecasts how long the cycle lasts. It lines up what the data say
about the current upswing against the four earlier ones, and checks whether
the Micron nowcast held up on quarters it was never fitted on.

Units: the model's growth rates are log points. At the sizes seen since 2024
they differ a lot from ordinary percent (150 log points is +348%), so every
table here is shown in ordinary percent.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from chipcycle import micron
from chipcycle.recent import extend_by_growth, load_reported, to_percent

QUARTER_DAYS = 91.3


# ------------------------------------------------------------ Korea, monthly


def korea_monthly(reported: pd.DataFrame) -> pd.DataFrame:
    """Ministry-basis level, reported YoY, month-on-month and 3-month change."""
    df = pd.DataFrame({"level_billion": reported["value"] / 1e9, "yoy_pct": reported["yoy_pct"]})
    df["mom_pct"] = 100 * df["level_billion"].pct_change()
    three = df["level_billion"].rolling(3).sum()
    df["three_month_vs_prior_three_pct"] = 100 * (three / three.shift(3) - 1)
    return df


# -------------------------------------------------------------- Micron table


def micron_table(quarters: pd.DataFrame, guidance: pd.DataFrame | None) -> pd.DataFrame:
    """Revenue, quarter-on-quarter and year-on-year in ordinary percent.

    A guided quarter is appended using the midpoint, flagged as guidance.
    """
    rev = quarters.set_index("end")["revenue"].sort_index() / 1e9
    guided = pd.Series(False, index=rev.index)
    if guidance is not None and len(guidance):
        g = guidance.copy()
        g["quarter_end"] = pd.to_datetime(g["quarter_end"])
        for _, row in g.iterrows():
            if row["quarter_end"] > rev.index.max():
                rev[row["quarter_end"]] = row["mid_billion"]
                guided[row["quarter_end"]] = True
    rev = rev.sort_index()
    guided = guided.reindex(rev.index).fillna(False)
    out = pd.DataFrame({"revenue_billion": rev, "guided": guided})
    out["qoq_pct"] = 100 * rev.pct_change()
    out["yoy_pct"] = to_percent(micron.yoy_quarterly(rev))
    # YoY (log) change from one quarter to the next equals this quarter's QoQ
    # minus the QoQ of the same quarter a year earlier. Show that base.
    out["year_ago_qoq_pct"] = out["qoq_pct"].shift(4)
    return out


# ------------------------------------------------------------ cycle history


def cycle_turns(rev: pd.Series, window: int = 3) -> pd.DataFrame:
    """Upswings from revenue trough to revenue peak, with the YoY peak inside each.

    A peak (trough) is a quarter whose revenue is the highest (lowest) within
    `window` quarters either side. The ongoing upswing is the last trough with
    no later peak. Lengths are in quarters, from the dates.
    """
    rev = rev.sort_index()
    yoy = micron.yoy_quarterly(rev)
    n = len(rev)
    idx = range(window, n - window)
    peaks = [i for i in idx if rev.iloc[i] == rev.iloc[i - window : i + window + 1].max()]
    troughs = [i for i in idx if rev.iloc[i] == rev.iloc[i - window : i + window + 1].min()]
    q = lambda a, b: int(round((b - a).days / QUARTER_DAYS))  # noqa: E731
    rows = []
    for p in peaks:
        before = [t for t in troughs if t < p]
        if not before:
            continue
        t = max(before)
        seg = yoy.iloc[t : p + 1].dropna()
        after = [x for x in troughs if x > p]
        rows.append({
            "trough": rev.index[t].date(), "peak": rev.index[p].date(), "ongoing": False,
            "up_quarters": q(rev.index[t], rev.index[p]),
            "yoy_peak": seg.idxmax().date() if len(seg) else None,
            "yoy_peak_lead_quarters": q(seg.idxmax(), rev.index[p]) if len(seg) else None,
            "down_quarters": q(rev.index[p], rev.index[min(after)]) if after else None,
        })
    last_t = max(troughs) if troughs else None
    if last_t is not None and (not peaks or last_t > max(peaks)):
        seg = yoy.iloc[last_t:].dropna()
        rows.append({
            "trough": rev.index[last_t].date(), "peak": None, "ongoing": True,
            "up_quarters": q(rev.index[last_t], rev.index[-1]),
            "yoy_peak": seg.idxmax().date() if len(seg) else None,
            "yoy_peak_lead_quarters": q(seg.idxmax(), rev.index[-1]) if len(seg) else None,
            "down_quarters": None,
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------- out-of-sample check


def nowcast_check(quarters: pd.DataFrame, korea_semis: pd.Series, reported: pd.DataFrame, first: str) -> tuple[pd.DataFrame, dict]:
    """The Micron nowcast on quarters after `first`, using Korea chip exports
    extended with reported growth. Each quarter's fit uses only earlier quarters."""
    ext = extend_by_growth(korea_semis, reported)
    df, stats = micron.micron_analysis(quarters, ext)
    new = df.loc[first:].dropna(subset=["nowcast", "mu_yoy"])
    if new.empty:
        return new, {}
    e_naive, e_korea = new["mu_yoy"] - new["naive"], new["mu_yoy"] - new["nowcast"]
    table = pd.DataFrame({
        "actual_yoy_pct": to_percent(new["mu_yoy"]),
        "nowcast_yoy_pct": to_percent(new["nowcast"]),
        "naive_yoy_pct": to_percent(new["naive"]),
    })
    return table, {
        "quarters": len(new),
        "rmse_naive_log_points": float(np.sqrt((e_naive**2).mean())),
        "rmse_korea_log_points": float(np.sqrt((e_korea**2).mean())),
        "direction_right": int((np.sign(new["nowcast"]) == np.sign(new["mu_yoy"])).sum()),
        "full_sample_corr": float(stats.get("corr_same_quarter", np.nan)),
    }
