"""Stage 5: is the signal useful, or just correlated?

A correlation computed on the whole sample uses hindsight: the model "knows"
the future when it is fitted. The honest test is out-of-sample. Walk forward
through time, and at each month:

1. Fit the model using only data that existed at that point.
2. Forecast h months ahead.
3. Record the error once the actual value arrives.

Do that twice, once with a baseline model and once with the chip signal
added, and compare errors. If chip exports don't reduce the error, the lead
is not useful for prediction, however good the correlation looked.

Models
------
Baseline (autoregressive):  y_{t+h} = a + b1*y_t + ... + bp*y_{t-p+1}
Augmented:                  same + c1*x_t + ... + cq*x_{t-q+1}

These are "direct" forecasts: a separate regression for each horizon h. Lag
counts are fixed in advance (p = q = 3) rather than tuned, because tuning on
the same data you evaluate on is another form of hindsight.

Diebold-Mariano test
--------------------
Is the error reduction bigger than luck? DM compares the two error series
month by month. Forecasts h months ahead overlap, so their errors are
correlated; the test uses a Newey-West variance to account for that, plus the
Harvey-Leybourne-Newbold small-sample correction.

Timing
------
Korea's HS-based customs data come out about 15 days after the month ends, US
industrial production about 16 days after. So when month t of both is
known, forecasting y_{t+h} from x_t and y_t uses nothing from the future.

For stock prices the test is stricter. On the 16th of each month, after
Korea's release, take the latest published chip growth figure and predict the
return from that day forward. Prices are the price on that day, so there is
no overlap with the past.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def _lagged(s: pd.Series, n: int, prefix: str) -> pd.DataFrame:
    return pd.concat({f"{prefix}{i}": s.shift(i) for i in range(n)}, axis=1)


def oos_forecast(
    y: pd.Series,
    x: pd.Series,
    h: int,
    p: int = 3,
    q: int = 3,
    min_train: int = 48,
    window: int | None = None,
) -> pd.DataFrame:
    """Direct forecasts of y_{t+h}. Rows are indexed by target month.

    Expanding window by default. With `window`, each fit uses only the most
    recent `window` usable rows, which adapts faster to structural breaks at
    the cost of noisier estimates.
    """
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    Xb = _lagged(df["y"], p, "y")
    Xa = pd.concat([Xb, _lagged(df["x"], q, "x")], axis=1)
    target = df["y"].shift(-h)
    rows = []
    for t in range(len(df)):
        # Training rows s need their target y_{s+h} observed by origin t: s + h <= t.
        # Guard the slice end: a negative end would silently mean "almost all
        # the data", future included.
        if t - h + 1 <= 0:
            continue
        train = slice(0 if window is None else max(0, t - h + 1 - window), t - h + 1)
        Xb_tr, Xa_tr, y_tr = Xb.iloc[train], Xa.iloc[train], target.iloc[train]
        ok = Xa_tr.notna().all(axis=1) & y_tr.notna()
        if ok.sum() < min_train or Xa.iloc[t].isna().any() or t + h >= len(df):
            continue
        preds = []
        for X_tr, X_now in ((Xb_tr[ok], Xb.iloc[t]), (Xa_tr[ok], Xa.iloc[t])):
            A = np.column_stack([np.ones(len(X_tr)), X_tr.to_numpy()])
            beta, *_ = np.linalg.lstsq(A, y_tr[ok].to_numpy(), rcond=None)
            preds.append(beta[0] + X_now.to_numpy() @ beta[1:])
        rows.append(
            {"origin": df.index[t], "target": df.index[t + h], "actual": df["y"].iloc[t + h],
             "baseline": preds[0], "augmented": preds[1]}
        )
    return pd.DataFrame(rows).set_index("target")


def diebold_mariano(e_base: np.ndarray, e_alt: np.ndarray, h: int) -> tuple[float, float]:
    """DM statistic and one-sided p-value that the alternative has lower squared error."""
    d = np.asarray(e_base) ** 2 - np.asarray(e_alt) ** 2
    n = len(d)
    d_bar = d.mean()
    # Newey-West long-run variance with h-1 lags (forecast errors overlap).
    gamma = [np.mean((d[k:] - d_bar) * (d[: n - k] - d_bar)) for k in range(h)]
    lrv = gamma[0] + 2 * sum((1 - k / h) * gamma[k] for k in range(1, h))
    if lrv <= 0:
        return np.nan, np.nan
    dm = d_bar / np.sqrt(lrv / n)
    # Harvey, Leybourne and Newbold (1997) small-sample correction.
    hln = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    stat = dm * hln
    return float(stat), float(1 - stats.t.cdf(stat, df=n - 1))


def evaluate(fc: pd.DataFrame, h: int) -> dict:
    e_b = fc["actual"] - fc["baseline"]
    e_a = fc["actual"] - fc["augmented"]
    rmse_b, rmse_a = np.sqrt((e_b**2).mean()), np.sqrt((e_a**2).mean())
    dm, p = diebold_mariano(e_b.to_numpy(), e_a.to_numpy(), h)
    return {
        "h": h,
        "n_forecasts": len(fc),
        "first": fc.index.min().strftime("%Y-%m"),
        "rmse_baseline": rmse_b,
        "rmse_with_chips": rmse_a,
        "rmse_change_pct": 100 * (rmse_a / rmse_b - 1),
        "dm_stat": dm,
        "dm_p": p,
    }


def forecast_table(panel: pd.DataFrame, signal: str, target: str, horizons=(1, 3, 6)) -> tuple[pd.DataFrame, dict]:
    rows, paths = [], {}
    for h in horizons:
        fc = oos_forecast(panel[target], panel[signal], h)
        if len(fc) < 12:
            continue
        paths[h] = fc
        rows.append({"signal": signal, "target": target, **evaluate(fc, h)})
    return pd.DataFrame(rows), paths


# ---------------------------------------------------------------- markets


def market_test(
    prices: pd.Series,
    signal: pd.Series,
    release_lag_days: int,
    h: int = 3,
    decision_day: int = 16,
    min_train: int = 36,
) -> tuple[pd.DataFrame, dict]:
    """Predict h-month forward log returns from the latest published signal.

    prices: daily closes. signal: monthly values indexed by month end.
    """
    prices = prices.dropna().sort_index()
    sig = pd.DataFrame(
        {"signal": signal.to_numpy(), "available": signal.index + pd.Timedelta(days=release_lag_days)}
    ).dropna().sort_values("available")
    months = pd.period_range(sig["available"].min(), prices.index.max(), freq="M")
    dates = pd.DatetimeIndex([m.to_timestamp() + pd.Timedelta(days=decision_day - 1) for m in months])
    dates = dates[dates <= prices.index.max()]
    left = pd.DataFrame({"date": dates})
    df = pd.merge_asof(left, sig, left_on="date", right_on="available", direction="backward")
    px = prices.reindex(prices.index.union(dates)).ffill().loc[dates]
    df["logp"] = np.log(px.to_numpy())
    df["fwd"] = df["logp"].shift(-h) - df["logp"]  # return from this date to h dates later
    df = df.set_index("date")

    rows = []
    for t in range(len(df)):
        # Only training rows whose forward return was fully realized by date t.
        train = df.iloc[: max(t - h + 1, 0)].dropna(subset=["signal", "fwd"])
        now = df.iloc[t]
        if len(train) < min_train or pd.isna(now["signal"]) or pd.isna(now["fwd"]):
            continue
        A = np.column_stack([np.ones(len(train)), train["signal"].to_numpy()])
        beta, *_ = np.linalg.lstsq(A, train["fwd"].to_numpy(), rcond=None)
        rows.append(
            {"date": df.index[t], "actual": now["fwd"], "baseline": train["fwd"].mean(),
             "augmented": beta[0] + beta[1] * now["signal"]}
        )
    fc = pd.DataFrame(rows).set_index("date")
    if fc.empty:
        return fc, {}
    e_b, e_a = fc["actual"] - fc["baseline"], fc["actual"] - fc["augmented"]
    dm, p = diebold_mariano(e_b.to_numpy(), e_a.to_numpy(), h)
    # Out-of-sample R^2 (Campbell-Thompson): above 0 means beating the
    # historical average return, the standard bar in return prediction.
    r2 = 1 - (e_a**2).sum() / (e_b**2).sum()
    # A fixed, untuned rule: hold when the model predicts above-average returns.
    long = fc["augmented"] > fc["baseline"]
    return fc, {
        "h_months": h,
        "n_forecasts": len(fc),
        "first": fc.index.min().strftime("%Y-%m"),
        "oos_r2_pct": 100 * r2,
        "dm_stat": dm,
        "dm_p": p,
        "hit_rate_pct": 100 * float((np.sign(fc["augmented"] - fc["baseline"]) == np.sign(fc["actual"] - fc["baseline"])).mean()),
        "avg_fwd_when_long_pct": 100 * float(fc.loc[long, "actual"].mean()) if long.any() else np.nan,
        "avg_fwd_when_out_pct": 100 * float(fc.loc[~long, "actual"].mean()) if (~long).any() else np.nan,
        "share_long_pct": 100 * float(long.mean()),
    }
