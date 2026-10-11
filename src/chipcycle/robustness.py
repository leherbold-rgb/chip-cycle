"""Stress tests: try to break the model's own conclusions.

Every test here asks "would this result survive if one of my choices or
assumptions were different, or if the data were noise?" A result that only
holds under one specific setup is not a result.

1. Surrogate test for the lead. The usual 95% band assumes independent data,
   and Stage 3 also picks the best of 13 lags, which inflates significance.
   Phase-randomized surrogates keep each series' autocorrelation but destroy
   any real link between them. The share of surrogates whose best lag beats
   the real one is an honest p-value for "there is a lead at all".
2. Multiple testing. Benjamini-Hochberg adjusts the Granger p-values for the
   number of pairs tested.
3. Effective sample size. Year-over-year growth overlaps: consecutive values
   share 11 of 12 months. The real amount of independent information is
   much smaller than the row count.
4. Specification grid. Re-run the forecast test across lag counts, training
   minimums, two growth transforms and three start dates, and report how often chips
   help, not just in the one setup chosen.
5. Release-lag sensitivity. How much of the market result depends on the
   assumed publication date?
6. Bootstrap interval for out-of-sample R^2, using blocks so serial
   correlation is preserved.
7. Lunar New Year. Korea's data are not seasonally adjusted and the holiday
   moves between January and February, which distorts year-over-year growth
   in exactly those months.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from chipcycle import forecast, leadlag


# ------------------------------------------------------------- 1. surrogates


def phase_surrogate(x: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Same power spectrum (so same autocorrelation), random phases."""
    n = len(x)
    f = np.fft.rfft(x - x.mean())
    phases = rng.uniform(0, 2 * np.pi, len(f))
    phases[0] = 0
    if n % 2 == 0:
        phases[-1] = 0
    return np.fft.irfft(np.abs(f) * np.exp(1j * phases), n) + x.mean()


def surrogate_lead_test(x: pd.Series, y: pd.Series, max_lag: int = 12, n_sur: int = 500, seed: int = 0) -> dict:
    pair = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    real = leadlag.ccf(pair["x"], pair["y"], max_lag).loc[1:max_lag].abs().max()
    rng = np.random.default_rng(seed)
    null = []
    for _ in range(n_sur):
        xs = pd.Series(phase_surrogate(pair["x"].to_numpy(), rng), index=pair.index)
        null.append(leadlag.ccf(xs, pair["y"], max_lag).loc[1:max_lag].abs().max())
    null = np.asarray(null)
    return {
        "best_lead_corr": float(real),
        "null_95pct": float(np.quantile(null, 0.95)),
        "naive_band": 1.96 / np.sqrt(len(pair)),
        "p_value": float((null >= real).mean()),
    }


# ------------------------------------------------------- 2. multiple testing


def benjamini_hochberg(p: pd.Series) -> pd.Series:
    """False-discovery-rate adjusted p-values."""
    p = p.dropna()
    order = p.sort_values()
    m = len(order)
    adj = (order * m / np.arange(1, m + 1)).iloc[::-1].cummin().iloc[::-1].clip(upper=1)
    return adj.reindex(p.index)


# --------------------------------------------------- 3. effective sample size


def effective_n(x: pd.Series, y: pd.Series, max_lag: int = 24) -> float:
    """Bartlett-style effective sample size for a correlation between two
    autocorrelated series: n / (1 + 2 * sum rho_x(k) * rho_y(k))."""
    pair = pd.concat([x, y], axis=1).dropna()
    n = len(pair)
    a, b = pair.iloc[:, 0], pair.iloc[:, 1]
    s = sum(a.autocorr(k) * b.autocorr(k) for k in range(1, min(max_lag, n // 4)))
    return float(n / max(1 + 2 * s, 1))


# ------------------------------------------------------ 4. specification grid


def yoy_of_3m_sum(level: pd.Series) -> pd.Series:
    """YoY growth of a rolling 3-month sum. Smoother than monthly YoY and
    still valid for data that aren't seasonally adjusted (a 3-month sum is
    compared with the same three months a year earlier)."""
    return 100 * np.log(level.rolling(3).sum()).diff(12)


def spec_grid(panels: dict[str, pd.DataFrame], signal: str, target: str, starts=("2014-01", "2016-01", "2018-01")) -> pd.DataFrame:
    rows = []
    for transform, panel in panels.items():
        rows += _grid_one(panel, signal, target, starts, transform)
    return pd.DataFrame(rows)


def _grid_one(panel, signal, target, starts, transform) -> list[dict]:
    rows = []
    for p in (1, 3, 6):
        for q in (1, 3, 6):
            for min_train in (36, 48, 72):
                for start in starts:
                    sub = panel.loc[start:]
                    for h in (1, 3, 6):
                        fc = forecast.oos_forecast(sub[target], sub[signal], h, p=p, q=q, min_train=min_train)
                        if len(fc) < 12:
                            continue
                        e_b = fc["actual"] - fc["baseline"]
                        e_a = fc["actual"] - fc["augmented"]
                        _, dm_p = forecast.diebold_mariano(e_b.to_numpy(), e_a.to_numpy(), h)
                        rows.append({"transform": transform, "p": p, "q": q, "min_train": min_train,
                                     "start": start, "h": h,
                                     "n": len(fc),
                                     "rmse_change_pct": 100 * (np.sqrt((e_a**2).mean()) / np.sqrt((e_b**2).mean()) - 1),
                                     "dm_p": dm_p})
    return rows


def summarize_grid(grid: pd.DataFrame) -> pd.DataFrame:
    return grid.groupby("h").agg(
        specs=("rmse_change_pct", "size"),
        share_chips_help=("rmse_change_pct", lambda s: 100 * (s < 0).mean()),
        share_significant=("dm_p", lambda s: 100 * (s < 0.05).mean()),
        median_rmse_change=("rmse_change_pct", "median"),
        best=("rmse_change_pct", "min"),
        worst=("rmse_change_pct", "max"),
    )


# ------------------------------------------------- 5. release-lag sensitivity


def release_lag_sensitivity(prices: pd.Series, signal: pd.Series, lags=(1, 15, 30, 45), h: int = 3) -> pd.DataFrame:
    rows = []
    for lag in lags:
        # Decide the day after the assumed release so the lag actually binds.
        day = min(lag + 1, 28) if lag < 28 else 16
        fc, res = forecast.market_test(prices, signal, lag, h=h, decision_day=day)
        if res:
            rows.append({"assumed_lag_days": lag, "decision_day": day, "oos_r2_pct": res["oos_r2_pct"],
                         "dm_p": res["dm_p"], "n": res["n_forecasts"]})
    return pd.DataFrame(rows)


# ------------------------------------------------- 6. bootstrap OOS R^2


def block_bootstrap_r2(fc: pd.DataFrame, block: int = 6, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    e_b2 = ((fc["actual"] - fc["baseline"]) ** 2).to_numpy()
    e_a2 = ((fc["actual"] - fc["augmented"]) ** 2).to_numpy()
    n = len(e_b2)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_boot):
        starts = rng.integers(0, n - block + 1, size=int(np.ceil(n / block)))
        idx = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
        out.append(1 - e_a2[idx].sum() / e_b2[idx].sum())
    return float(np.quantile(out, 0.05) * 100), float(np.quantile(out, 0.95) * 100)


# ------------------------------------------------------- 7. Lunar New Year


def lunar_new_year_check(level: pd.Series) -> pd.DataFrame:
    """Volatility of YoY growth by calendar month. If Jan/Feb stand out, the
    holiday shift is adding noise; summing Jan+Feb removes it."""
    g = 100 * np.log(level).diff(12)
    by_month = g.groupby(g.index.month).std().rename("yoy_std")
    jf = level[level.index.month.isin([1, 2])]
    jf_sum = jf.groupby(jf.index.year).sum()
    jf_growth = 100 * np.log(jf_sum).diff()
    out = by_month.to_frame()
    out.index.name = "month"
    out.attrs["jan_feb_combined_std"] = float(jf_growth.std())
    return out
