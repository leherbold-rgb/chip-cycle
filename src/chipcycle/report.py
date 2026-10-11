"""Stage 7: run every stage and write results/ (tables, charts, results.md).

Nothing in results.md is typed by hand. Every number comes from this run,
so rerunning after a data refresh updates the whole write-up.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from chipcycle import forecast, leadlag, micron, stability, timing, transforms  # noqa: E402
from chipcycle.registry import REGISTRY  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"

# Two validated categorical slots (blue, orange) plus neutral inks.
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

NAMES = {
    "kr_semi_exports": "Korea chip exports",
    "kr_memory_exports": "Korea memory exports",
    "kr_exports_total": "Korea total exports",
    "us_indpro": "US industrial production",
    "us_baa_spread": "Baa credit spread (12m change)",
    "liquidity": "Net Fed liquidity",
    "acwi": "Global equities (ACWI)",
    "sox": "Semiconductor index (SOX)",
    "mu": "Micron share price",
}
SIGNALS = ["kr_semi_exports", "kr_memory_exports", "kr_exports_total"]
TARGETS = ["us_indpro", "us_baa_spread", "liquidity", "acwi", "sox", "mu"]


def _style(ax, title: str, ylabel: str = "") -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=INK, fontsize=11)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)
    ax.tick_params(colors=INK2, labelsize=8, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


def _save(fig, name: str) -> str:
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / name, dpi=160)
    plt.close(fig)
    return name


def _md(df: pd.DataFrame, floatfmt: str = "{:.2f}") -> str:
    """A pipe table without needing the tabulate package."""
    df = df.reset_index() if df.index.name else df
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = [floatfmt.format(v) if isinstance(v, (float, np.floating)) and not pd.isna(v) else
                 ("" if pd.isna(v) else str(v)) for v in r]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def chart_series(panel: pd.DataFrame, x: str, y: str) -> str:
    fig, axes = plt.subplots(2, 1, figsize=(9, 5.5), sharex=True)
    for ax, key, color in ((axes[0], x, BLUE), (axes[1], y, ORANGE)):
        s = panel[key].dropna()
        ax.plot(s.index, s, color=color, linewidth=2)
        ax.axhline(0, color=INK2, linewidth=0.8)
        _style(ax, NAMES[key], "% vs. a year earlier")
    return _save(fig, f"series_{x}_{y}.png")


def chart_ccf(raw: pd.Series, pw: pd.Series, band: float, x: str, y: str) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    for ax, c, title in ((axes[0], raw, "Raw growth rates"), (axes[1], pw, "Prewhitened (the honest version)")):
        ax.bar(c.index, c.to_numpy(), color=BLUE, width=0.6)
        ax.axhline(0, color=INK2, linewidth=0.8)
        if ax is axes[1]:
            for b in (band, -band):
                ax.axhline(b, color=INK2, linewidth=1, linestyle="--")
            ax.text(c.index.max(), band, " 95% band", color=INK2, fontsize=8, va="bottom", ha="right")
        _style(ax, title, "correlation" if ax is axes[0] else "")
        ax.set_xlabel(f"lag k (months). k > 0: {NAMES[x]} moves first", color=INK2, fontsize=8)
    fig.suptitle(f"{NAMES[x]} vs. {NAMES[y]}", x=0.01, ha="left", color=INK, fontsize=12)
    return _save(fig, f"ccf_{x}_{y}.png")


def chart_rolling(roll: pd.DataFrame, x: str, y: str) -> str:
    fig, axes = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    axes[0].plot(roll.index, roll["peak_lag"], color=BLUE, linewidth=2, drawstyle="steps-post")
    _style(axes[0], "Lead at which correlation peaks (5-year rolling window)", "months")
    axes[1].plot(roll.index, roll["peak_corr"], color=BLUE, linewidth=2)
    axes[1].axhline(0, color=INK2, linewidth=0.8)
    _style(axes[1], "Correlation at that peak", "correlation")
    return _save(fig, f"rolling_{x}_{y}.png")


def chart_cumulative(fc: pd.DataFrame, title: str, name: str) -> str:
    """Cumulative squared-error advantage. Rising = the chip model is winning."""
    d = ((fc["actual"] - fc["baseline"]) ** 2 - (fc["actual"] - fc["augmented"]) ** 2).cumsum()
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(d.index, d, color=BLUE, linewidth=2)
    ax.axhline(0, color=INK2, linewidth=0.8)
    _style(ax, title, "cumulative squared error saved")
    return _save(fig, name)


def chart_micron(df: pd.DataFrame) -> str:
    d = df.dropna(subset=["mu_yoy", "korea_yoy"])
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(d.index, d["korea_yoy"], color=BLUE, linewidth=2, label="Korea memory exports")
    ax.plot(d.index, d["mu_yoy"], color=ORANGE, linewidth=2, label="Micron revenue")
    ax.axhline(0, color=INK2, linewidth=0.8)
    _style(ax, "Growth vs. a year earlier, by Micron fiscal quarter", "log growth, %")
    ax.legend(frameon=False, fontsize=9, labelcolor=INK)
    return _save(fig, "micron.png")


def build(raw: dict[str, pd.Series], micron_quarters: tuple[pd.DataFrame, str] | None) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    specs = {k: REGISTRY[k] for k in raw}
    ref = timing.reference_panel(raw, specs)
    panel = transforms.analysis_panel(ref)
    panel.to_csv(RESULTS_DIR / "analysis_panel.csv")
    md = ["# Results", "", "Generated by `chipcycle analyze`. Every number below comes from that run.", ""]

    # Stage 2
    st = transforms.stationarity_table(panel)
    st.to_csv(RESULTS_DIR / "stationarity.csv")
    md += ["## Stage 2: stationarity of the growth rates", "",
           "ADF p < 0.05 rejects a unit root; KPSS p > 0.05 fails to reject stationarity. "
           "KPSS p-values are capped at 0.01 and 0.10 by its lookup table.", "", _md(st, "{:.3f}"), ""]

    # Stage 3
    signals = [s for s in SIGNALS if s in panel]
    targets = [t for t in TARGETS if t in panel]
    ll = leadlag.lead_lag_summary(panel, signals, targets)
    ll.to_csv(RESULTS_DIR / "lead_lag.csv", index=False)
    md += ["## Stage 3: lead-lag", "",
           "`pw_lead_lag`: the lead (0 to 12 months) where the prewhitened cross-correlation is largest. "
           "`pw_band`: the 95% significance band; correlations inside it are noise. "
           f"With {len(ll)} pairs tested, about {len(ll) * 0.05:.1f} would pass at 5% by chance alone.", "",
           _md(ll.set_index(["signal", "target"]).reset_index(), "{:.3f}"), ""]

    head_x = "kr_semi_exports" if "kr_semi_exports" in panel else "kr_exports_total"
    if head_x in panel and "us_indpro" in panel:
        pair = panel[[head_x, "us_indpro"]].dropna()
        md += [f"![]({chart_series(panel.loc[pair.index.min():], head_x, 'us_indpro')})", ""]
        raw_c = leadlag.ccf(pair[head_x], pair["us_indpro"])
        pw_c = leadlag.prewhitened_ccf(pair[head_x], pair["us_indpro"])
        md += [f"![]({chart_ccf(raw_c, pw_c, 1.96 / np.sqrt(len(pair)), head_x, 'us_indpro')})", ""]

    # Stage 4
    md += ["## Stage 4: stability", ""]
    for x in [s for s in ("kr_semi_exports", "kr_exports_total") if s in panel]:
        if "us_indpro" not in panel:
            break
        row = ll[(ll["signal"] == x) & (ll["target"] == "us_indpro")]
        lag = int(row["pw_lead_lag"].iloc[0]) if len(row) else 3
        rt = stability.regime_table(panel[x], panel["us_indpro"], lag)
        rt.to_csv(RESULTS_DIR / f"regimes_{x}.csv")
        md += [f"**{NAMES[x]} vs. US industrial production at a {lag}-month lead, by regime**", "", _md(rt, "{:.2f}"), ""]
        roll = stability.rolling_peak(panel[x], panel["us_indpro"])
        if len(roll):
            roll.to_csv(RESULTS_DIR / f"rolling_{x}.csv")
            md += [f"![]({chart_rolling(roll, x, 'us_indpro')})", ""]

    # Stage 5
    md += ["## Stage 5: out-of-sample forecasts", "",
           "Expanding window, direct forecasts, p = q = 3 lags fixed in advance. "
           "`rmse_change_pct` below 0 means chip data reduced forecast error. "
           "`dm_p` is the one-sided Diebold-Mariano p-value.", ""]
    fts = []
    for x in signals:
        for y in [t for t in ("us_indpro", "us_baa_spread", "liquidity") if t in panel]:
            t, paths = forecast.forecast_table(panel, x, y)
            if len(t):
                fts.append(t)
            if x == head_x and y == "us_indpro" and 3 in paths:
                name = chart_cumulative(paths[3], f"{NAMES[x]} → US industrial production, 3 months ahead. "
                                        "Rising line = chips help", "oos_indpro_h3.png")
                md_chart = f"![]({name})"
    if fts:
        ft = pd.concat(fts, ignore_index=True)
        ft.to_csv(RESULTS_DIR / "forecasts.csv", index=False)
        md += [_md(ft, "{:.3f}"), ""]
        if "md_chart" in locals():
            md += [md_chart, ""]

    md += ["### Markets", "",
           "On the 16th of each month, after Korea's customs release, predict the next 3 months' log return "
           "from the latest published chip growth figure. Baseline: the historical average return. "
           "`oos_r2_pct` above 0 means beating that baseline out of sample.", ""]
    mrows = []
    for x in [s for s in ("kr_semi_exports", "kr_memory_exports") if s in panel]:
        for m in [t for t in ("acwi", "sox", "mu") if t in raw]:
            fc, res = forecast.market_test(raw[m], panel[x].dropna(), REGISTRY[x].release_lag_days, h=3)
            if res:
                mrows.append({"signal": x, "market": m, **res})
    if mrows:
        mt = pd.DataFrame(mrows)
        mt.to_csv(RESULTS_DIR / "markets.csv", index=False)
        md += [_md(mt, "{:.2f}"), ""]

    # Stage 6
    md += ["## Stage 6: Micron", ""]
    if micron_quarters is not None and "kr_memory_exports" in ref:
        quarters, source = micron_quarters
        mdf, mstats = micron.micron_analysis(quarters, ref["kr_memory_exports"].dropna())
        mdf.to_csv(RESULTS_DIR / "micron.csv")
        md += [f"Revenue source: {source}.", ""]
        if "corr_same_quarter" in mstats:
            md += [_md(pd.DataFrame([mstats]), "{:.2f}"), "", f"![]({chart_micron(mdf)})", ""]
        else:
            md += [f"Only {mstats['quarters']} overlapping quarters, too few to fit. "
                   "Allow data.sec.gov for the full revenue history.", ""]
    else:
        md += ["Not run: no Micron revenue data or no Korea memory export series.", ""]

    out = RESULTS_DIR / "results.md"
    out.write_text("\n".join(md))
    return out
