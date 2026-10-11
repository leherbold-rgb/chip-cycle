"""Accuracy backtests: how often is the model right, and would it have made money?

Rules are fixed before looking at results. Each is evaluated and every
result is reported. Picking the best of many rules after the fact is the
fastest way to fool yourself, so the report also shows how each rule compares
with random timing.

Economy: direction calls
------------------------
From Stage 5's out-of-sample forecasts: does the model correctly call whether
industrial production growth will be higher or lower in h months than it is
today? A coin flip gets 50%. The comparison that matters is the baseline
model's hit rate, which uses only industrial production's own history.

Markets: timing rules
---------------------
On the 16th of each month (after Korea's customs release) decide to hold the
index or hold cash until the next decision date.

  level     hold when chip export growth (YoY) is above zero
  momentum  hold when chip export growth is higher than 3 months earlier
            (the "second derivative": the cycle is improving)
  model     hold when Stage 5's out-of-sample regression predicts an
            above-average 3-month return

Cash earns 0 (conservative: it understates the rules slightly when rates
are positive). Each switch costs 10 basis points.

Random-timing placebo
---------------------
A rule that is in the market 70% of the time will look good in a rising
market for that reason alone. So each rule is compared with 1,000 random
strategies that hold for the same share of months, with the same average
holding streak. The percentile tells you whether the timing added anything.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from chipcycle import forecast

COST = 0.001  # 10 bp per switch


def direction_hits(fc: pd.DataFrame, current: pd.Series) -> dict:
    """Hit rate on the direction of change from the origin to the target month."""
    now = current.reindex(fc["origin"]).to_numpy()
    actual = np.sign(fc["actual"].to_numpy() - now)
    out = {"n": int(len(fc))}
    for col in ("baseline", "augmented"):
        out[f"hit_{col}_pct"] = 100 * float((np.sign(fc[col].to_numpy() - now) == actual).mean())
    return out


def decision_frame(prices: pd.Series, signal: pd.Series, release_lag_days: int, day: int = 16) -> pd.DataFrame:
    """One row per decision date: latest published signal and the log return to the next date."""
    prices = prices.dropna().sort_index()
    sig = pd.DataFrame({"signal": signal.to_numpy(),
                        "momentum": signal.diff(3).to_numpy(),
                        "available": signal.index + pd.Timedelta(days=release_lag_days)}).sort_values("available")
    months = pd.period_range(sig["available"].min(), prices.index.max(), freq="M")
    dates = pd.DatetimeIndex([m.to_timestamp() + pd.Timedelta(days=day - 1) for m in months])
    dates = dates[dates <= prices.index.max()]
    df = pd.merge_asof(pd.DataFrame({"date": dates}), sig, left_on="date", right_on="available", direction="backward")
    px = prices.reindex(prices.index.union(dates)).ffill().loc[dates].to_numpy()
    df["ret"] = np.r_[np.diff(np.log(px)), np.nan]  # return earned by holding from this date to the next
    return df.set_index("date").dropna(subset=["ret"])


def run_rule(ret: pd.Series, hold: pd.Series) -> pd.Series:
    """Monthly log returns of a long/cash rule after switching costs."""
    hold = hold.astype(float)
    switches = hold.diff().abs().fillna(hold.iloc[0])
    return hold * ret + np.log(1 - COST) * switches


def stats(r: pd.Series) -> dict:
    """Annualized stats from monthly log returns."""
    eq = np.exp(r.cumsum())
    years = len(r) / 12
    dd = eq / eq.cummax() - 1
    vol = r.std() * np.sqrt(12)
    return {
        "cagr_pct": 100 * (eq.iloc[-1] ** (1 / years) - 1),
        "vol_pct": 100 * vol,
        "sharpe": float(r.mean() * 12 / vol) if vol > 0 else np.nan,
        "max_drawdown_pct": 100 * float(dd.min()),
    }


def random_timing_percentile(ret: pd.Series, hold: pd.Series, n: int = 1000, seed: int = 0) -> float:
    """Percentile of the rule's Sharpe among random rules with the same
    time in market and similar streak lengths (circularly shifted blocks)."""
    rng = np.random.default_rng(seed)
    h = hold.to_numpy().astype(float)
    real = stats(run_rule(ret, hold))["sharpe"]
    sharpes = []
    for _ in range(n):
        # Cut the holding pattern at a random point and swap the halves, then
        # shuffle 12-month blocks: keeps time in market and streak structure,
        # breaks the link to the dates.
        rolled = np.roll(h, rng.integers(len(h)))
        blocks = [rolled[i : i + 12] for i in range(0, len(rolled), 12)]
        rng.shuffle(blocks)
        fake = pd.Series(np.concatenate(blocks)[: len(h)], index=hold.index)
        sharpes.append(stats(run_rule(ret, fake))["sharpe"])
    return 100 * float((np.asarray(sharpes) < real).mean())


def market_backtest(prices: pd.Series, signal: pd.Series, release_lag_days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = decision_frame(prices, signal, release_lag_days)
    fc, _ = forecast.market_test(prices, signal, release_lag_days, h=3)
    df = df.join(fc[["augmented", "baseline"]], how="left")
    # Evaluate every rule over the same months: where all signals exist.
    df = df.dropna(subset=["signal", "momentum", "augmented"])
    rules = {
        "buy and hold": pd.Series(1, index=df.index),
        "level": (df["signal"] > 0).astype(int),
        "momentum": (df["momentum"] > 0).astype(int),
        "model": (df["augmented"] > df["baseline"]).astype(int),
    }
    rows, curves = [], {}
    for name, hold in rules.items():
        r = run_rule(df["ret"], hold)
        curves[name] = np.exp(r.cumsum())
        row = {"rule": name, "months": len(r), "in_market_pct": 100 * float(hold.mean()), **stats(r)}
        row["switches"] = int(hold.diff().abs().sum())
        row["random_timing_pctile"] = np.nan if name == "buy and hold" else random_timing_percentile(df["ret"], hold)
        # Was the rule right? A month is "right" if it held during a gain or sat out a loss.
        row["months_right_pct"] = 100 * float(((hold == 1) == (df["ret"] > 0)).mean())
        rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(curves)
