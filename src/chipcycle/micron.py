"""Stage 6: Micron revenue from Korean memory exports.

Samsung and SK Hynix make roughly two thirds of the world's DRAM, and they
ship it from Korea. When Korea's memory exports jump, it is mostly because
memory prices and volumes jumped, and Micron sells the same products into
the same market. So Korea's memory export figures are close to a monthly
reading of Micron's industry, while Micron itself reports once a quarter.

Mapping months to Micron's quarters
-----------------------------------
Micron's fiscal year ends around the start of September, so its quarters run
roughly Sep-Nov, Dec-Feb, Mar-May and Jun-Aug, not calendar quarters. Each
reported quarter has exact start and end dates; we sum Korea's exports over
the calendar months that mostly fall inside them.

Data
----
Micron's quarterly revenue comes from SEC EDGAR's XBRL API (data.sec.gov),
which has every filing since 2009. The fourth fiscal quarter is usually only
reported inside the annual total, so it is derived as the annual figure minus
the first three quarters. If SEC is unreachable we fall back to Yahoo, which
only has the last few quarters, too few to fit anything.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
import requests

MICRON_CIK = "0000723125"
CONCEPTS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]
SEC_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"


def _sec_facts(concept: str, timeout: float = 30) -> list[dict]:
    # SEC asks automated clients to identify themselves in the User-Agent.
    agent = os.environ.get("SEC_USER_AGENT", "chip-cycle research project")
    resp = requests.get(
        SEC_URL.format(cik=MICRON_CIK, concept=concept), headers={"User-Agent": agent}, timeout=timeout
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json().get("units", {}).get("USD", [])


def quarters_from_facts(facts: list[dict]) -> pd.DataFrame:
    """Quarterly revenue (start, end, revenue) from raw XBRL facts, deriving Q4."""
    if not facts:
        return pd.DataFrame(columns=["start", "end", "revenue"])
    df = pd.DataFrame(facts)
    df = df[df["form"].isin(["10-Q", "10-K", "10-Q/A", "10-K/A"]) & df["start"].notna()]
    df["start"], df["end"] = pd.to_datetime(df["start"]), pd.to_datetime(df["end"])
    df["filed"] = pd.to_datetime(df["filed"])
    df["days"] = (df["end"] - df["start"]).dt.days
    # The latest filing of each period wins (restatements).
    df = df.sort_values("filed").drop_duplicates(["start", "end"], keep="last")
    q = df[df["days"].between(80, 100)][["start", "end", "val"]]
    years = df[df["days"].between(350, 380)][["start", "end", "val"]]
    derived = []
    for _, fy in years.iterrows():
        inside = q[(q["start"] >= fy["start"] - pd.Timedelta(days=3)) & (q["end"] <= fy["end"] + pd.Timedelta(days=3))]
        if len(inside) == 3 and not (q["end"].sub(fy["end"]).abs() <= pd.Timedelta(days=3)).any():
            derived.append({"start": inside["end"].max() + pd.Timedelta(days=1), "end": fy["end"],
                            "val": fy["val"] - inside["val"].sum()})
    out = pd.concat([q, pd.DataFrame(derived)], ignore_index=True)
    out = out.rename(columns={"val": "revenue"}).sort_values("end").drop_duplicates("end", keep="last")
    return out.reset_index(drop=True)


def fetch_micron_quarters() -> tuple[pd.DataFrame, str]:
    """Micron quarterly revenue and the source it came from."""
    try:
        facts = [f for c in CONCEPTS for f in _sec_facts(c)]
        q = quarters_from_facts(facts)
        if len(q) >= 20:
            return q, "SEC EDGAR"
    except requests.RequestException:
        pass
    import yfinance as yf

    inc = yf.Ticker("MU").quarterly_income_stmt
    rev = inc.loc["Total Revenue"].dropna().sort_index()
    q = pd.DataFrame({"end": pd.to_datetime(rev.index), "revenue": rev.to_numpy(dtype=float)})
    q["start"] = q["end"] - pd.Timedelta(days=90)
    return q[["start", "end", "revenue"]], "Yahoo (last few quarters only)"


def korea_by_quarter(monthly: pd.Series, quarters: pd.DataFrame) -> pd.Series:
    """Sum monthly Korean exports over each Micron quarter's calendar months."""
    vals = []
    for _, row in quarters.iterrows():
        months = pd.period_range(row["start"] + pd.Timedelta(days=15), row["end"] - pd.Timedelta(days=15), freq="M")
        idx = months.to_timestamp(how="end").normalize()
        got = monthly.reindex(idx)
        vals.append(got.sum() if got.notna().all() and len(got) == 3 else np.nan)
    return pd.Series(vals, index=pd.DatetimeIndex(quarters["end"]), name="korea_memory")


def yoy_quarterly(s: pd.Series) -> pd.Series:
    """Log growth versus four quarters earlier, in percent."""
    return 100 * np.log(s).diff(4)


def micron_analysis(quarters: pd.DataFrame, korea_memory_monthly: pd.Series, min_train: int = 12) -> tuple[pd.DataFrame, dict]:
    korea = korea_by_quarter(korea_memory_monthly, quarters)
    df = pd.DataFrame({"mu_revenue": quarters["revenue"].to_numpy(), "korea_memory": korea.to_numpy()},
                      index=pd.DatetimeIndex(quarters["end"], name="quarter_end"))
    df["mu_yoy"] = yoy_quarterly(df["mu_revenue"])
    df["korea_yoy"] = yoy_quarterly(df["korea_memory"])
    both = df.dropna(subset=["mu_yoy", "korea_yoy"])
    stats = {"quarters": len(both)}
    if len(both) < min_train + 4:
        return df, stats

    stats["first_quarter"] = both.index.min().strftime("%Y-%m")
    stats["corr_same_quarter"] = both["mu_yoy"].corr(both["korea_yoy"])
    stats["corr_korea_leads_1q"] = df["korea_yoy"].corr(df["mu_yoy"].shift(-1))
    beta = np.polyfit(both["korea_yoy"], both["mu_yoy"], 1)
    stats["beta"] = beta[0]

    # Nowcast, out of sample. When a quarter ends, Korea's three months are
    # published before Micron reports. Predict this quarter's revenue growth
    # from Korea's, fitted only on earlier quarters. Baseline: last quarter's
    # growth carries on (what a naive analyst would assume).
    rows = []
    for i in range(min_train, len(both)):
        tr, now = both.iloc[:i], both.iloc[i]
        b = np.polyfit(tr["korea_yoy"], tr["mu_yoy"], 1)
        rows.append({"quarter_end": both.index[i], "actual": now["mu_yoy"],
                     "nowcast": b[0] * now["korea_yoy"] + b[1], "naive": both["mu_yoy"].iloc[i - 1]})
    nc = pd.DataFrame(rows).set_index("quarter_end")
    from chipcycle.forecast import diebold_mariano

    e_n, e_k = nc["actual"] - nc["naive"], nc["actual"] - nc["nowcast"]
    dm, p = diebold_mariano(e_n.to_numpy(), e_k.to_numpy(), 1)
    stats.update(
        {
            "nowcast_quarters": len(nc),
            "rmse_naive_pp": float(np.sqrt((e_n**2).mean())),
            "rmse_korea_pp": float(np.sqrt((e_k**2).mean())),
            "direction_right_pct": 100 * float((np.sign(nc["nowcast"]) == np.sign(nc["actual"])).mean()),
            "dm_stat": dm,
            "dm_p": p,
        }
    )
    df = df.join(nc[["nowcast", "naive"]])
    return df, stats
