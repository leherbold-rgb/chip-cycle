"""Stage 2: turn raw levels into series that can be compared honestly.

Why not just correlate the raw numbers?
---------------------------------------
Chip exports, industrial production and stock prices all trend upward over
decades. Any two upward-trending series correlate strongly even when they
have nothing to do with each other (a "spurious regression"). The fix is to
compare *changes*, not levels.

We use the 12-month log difference (approximately year-over-year percent
growth). It also removes seasonality: Korea's customs data are not
seasonally adjusted, and December always beats January. Comparing each month
with the same month a year earlier cancels that pattern.

Spreads are already in percent, so they get a 12-month change in level
instead of a growth rate.

Stationarity tests
------------------
A series is "stationary" if its average and variability don't drift over
time. Most statistical tools assume it. Two standard tests disagree in a
useful way:

- ADF: the null hypothesis is "this series has a unit root" (it wanders).
  A small p-value rejects that, which is evidence of stationarity.
- KPSS: the null is the opposite, "this series is stationary". A small
  p-value is evidence *against* stationarity.

Passing both (ADF p < 0.05 and KPSS p > 0.05) is strong evidence.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

GROWTH = "growth"  # 12-month log difference x 100
CHANGE = "change"  # 12-month difference in level

# How each analysis series is built from the reference panel.
TRANSFORMS: dict[str, str] = {
    "kr_semi_exports": GROWTH,
    "kr_memory_exports": GROWTH,
    "kr_exports_total": GROWTH,
    "us_indpro": GROWTH,
    "us_baa_spread": CHANGE,
    "liquidity": GROWTH,
    "acwi": GROWTH,
    "sox": GROWTH,
    "mu": GROWTH,
}


def growth(s: pd.Series, periods: int = 12) -> pd.Series:
    """Log growth over `periods` months, in percent."""
    if (s.dropna() <= 0).any():
        raise ValueError(f"{s.name}: log growth needs strictly positive values")
    return 100 * np.log(s).diff(periods)


def change(s: pd.Series, periods: int = 12) -> pd.Series:
    return s.diff(periods)


def add_liquidity(panel: pd.DataFrame) -> pd.DataFrame:
    """Net Fed liquidity in USD billions: balance sheet minus TGA minus reverse repo.

    The Fed's balance sheet adds money to the financial system. Cash the
    Treasury parks at the Fed (TGA) and money funds park in the reverse repo
    facility (RRP) take it back out. What's left is the part actually
    circulating in markets.
    """
    out = panel.copy()
    needed = {"fed_assets", "tga", "rrp"}
    if needed <= set(out.columns):
        # WALCL and WTREGEN are in millions, RRPONTSYD in billions.
        # RRP was near zero and sparsely reported before 2013; treat gaps as zero.
        out["liquidity"] = out["fed_assets"] / 1000 - out["tga"] / 1000 - out["rrp"].fillna(0)
        out.loc[out["fed_assets"].isna() | out["tga"].isna(), "liquidity"] = np.nan
    return out


def analysis_panel(reference: pd.DataFrame) -> pd.DataFrame:
    """Transformed, stationary-ish monthly panel used by every later stage."""
    ref = add_liquidity(reference)
    cols = {}
    for key, how in TRANSFORMS.items():
        if key not in ref.columns:
            continue
        cols[key] = growth(ref[key]) if how == GROWTH else change(ref[key])
    out = pd.DataFrame(cols, index=ref.index)
    out.index.name = "month"
    return out


def stationarity_table(panel: pd.DataFrame) -> pd.DataFrame:
    from statsmodels.tsa.stattools import adfuller, kpss

    rows = []
    for col in panel.columns:
        s = panel[col].dropna()
        if len(s) < 36:
            continue
        adf_p = adfuller(s, autolag="AIC")[1]
        with warnings.catch_warnings():
            # KPSS warns when its p-value is outside its lookup table (<0.01 or >0.1).
            warnings.simplefilter("ignore")
            kpss_p = kpss(s, regression="c", nlags="auto")[1]
        rows.append(
            {
                "series": col,
                "start": s.index.min().strftime("%Y-%m"),
                "end": s.index.max().strftime("%Y-%m"),
                "n": len(s),
                "adf_p": adf_p,
                "kpss_p": kpss_p,
                "stationary": bool(adf_p < 0.05 and kpss_p > 0.05),
            }
        )
    return pd.DataFrame(rows).set_index("series")
