"""Stage 3: does the chip series move first, and by how many months?

Cross-correlation
-----------------
ccf(k) = corr(x_t, y_{t+k}). If chip exports (x) lead industrial production
(y) by 3 months, ccf peaks at k = +3. Negative k means y moves first.

Why prewhiten
-------------
Year-over-year growth rates are very smooth: this month looks a lot like last
month. When both series are that persistent, their cross-correlations are
large at almost every lag, and the peak looks sharper and more significant
than it really is. Prewhitening fixes this:

1. Fit an autoregressive model to x, which captures how x depends on its own
   past.
2. Keep only x's residuals, the genuinely new information each month.
3. Run y through the *same* filter, so both are transformed identically.
4. Cross-correlate the two filtered series.

What's left measures whether *surprises* in chip exports line up with later
movements in y, which is the honest version of the question.

Granger causality
-----------------
Fit a small vector autoregression (VAR) with y and x, then ask: do past
values of x improve the prediction of y beyond what y's own past already
gives? An F-test answers it. This is "predictive precedence", not proof that
x causes y. Testing the reverse direction too guards against reading a
two-way relationship as one-way.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ccf(x: pd.Series, y: pd.Series, max_lag: int = 12) -> pd.Series:
    """corr(x_t, y_{t+k}) for k in [-max_lag, max_lag], on overlapping data."""
    df = pd.concat([x.rename("x"), y.rename("y")], axis=1)
    out = {}
    for k in range(-max_lag, max_lag + 1):
        pair = pd.concat([df["x"], df["y"].shift(-k)], axis=1).dropna()
        out[k] = pair.iloc[:, 0].corr(pair.iloc[:, 1]) if len(pair) > 10 else np.nan
    return pd.Series(out, name="ccf").rename_axis("lag")


def ar_filter(x: pd.Series, max_order: int = 12) -> np.ndarray:
    """AR coefficients for x, order picked by AIC (at least 1)."""
    from statsmodels.tsa.ar_model import AutoReg, ar_select_order

    x = x.dropna()
    sel = ar_select_order(x.to_numpy(), maxlag=min(max_order, len(x) // 5), ic="aic")
    order = max(sel.ar_lags[-1] if sel.ar_lags else 1, 1)
    fit = AutoReg(x.to_numpy(), lags=order).fit()
    return np.asarray(fit.params[1:])  # drop the constant


def apply_filter(s: pd.Series, phi: np.ndarray) -> pd.Series:
    """s_t - sum(phi_i * s_{t-i}). The constant doesn't affect correlations."""
    out = s.copy()
    for i, p in enumerate(phi, start=1):
        out = out - p * s.shift(i)
    return out


def prewhitened_ccf(x: pd.Series, y: pd.Series, max_lag: int = 12) -> pd.Series:
    df = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    phi = ar_filter(df["x"])
    return ccf(apply_filter(df["x"], phi), apply_filter(df["y"], phi), max_lag)


def granger_p(x: pd.Series, y: pd.Series, max_lag: int = 12) -> tuple[float, int]:
    """p-value that past x helps predict y, and the VAR lag order used."""
    from statsmodels.tsa.api import VAR

    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    model = VAR(df)
    order = model.select_order(maxlags=min(max_lag, len(df) // 8)).aic
    order = max(int(order), 1)
    res = model.fit(order)
    return float(res.test_causality("y", ["x"], kind="f").pvalue), order


def lead_lag_summary(panel: pd.DataFrame, signals: list[str], targets: list[str], max_lag: int = 12) -> pd.DataFrame:
    rows = []
    for x in signals:
        for y in targets:
            if x not in panel or y not in panel:
                continue
            pair = panel[[x, y]].dropna()
            if len(pair) < 48:
                continue
            raw = ccf(pair[x], pair[y], max_lag)
            pw = prewhitened_ccf(pair[x], pair[y], max_lag)
            leads = pw.loc[0:max_lag]
            peak = int(leads.abs().idxmax())
            p_xy, order = granger_p(pair[x], pair[y], max_lag)
            p_yx, _ = granger_p(pair[y], pair[x], max_lag)
            rows.append(
                {
                    "signal": x,
                    "target": y,
                    "n": len(pair),
                    "raw_peak_lag": int(raw.abs().idxmax()),
                    "raw_peak_corr": raw.loc[raw.abs().idxmax()],
                    "pw_lead_lag": peak,
                    "pw_lead_corr": leads.loc[peak],
                    "pw_band": 1.96 / np.sqrt(len(pair)),
                    "granger_p_signal_to_target": p_xy,
                    "granger_p_target_to_signal": p_yx,
                    "var_order": order,
                }
            )
    return pd.DataFrame(rows)
