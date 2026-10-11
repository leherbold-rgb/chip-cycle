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
        ax.set_xlabel(f"lag k (months). Positive k: {NAMES[x]} lead", color=INK2, fontsize=8)
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


def build_stress(raw: dict[str, pd.Series]) -> Path:
    """Run the robustness checks and write results/stress.md."""
    from chipcycle import robustness

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    specs = {k: REGISTRY[k] for k in raw}
    ref = transforms.add_liquidity(timing.reference_panel(raw, specs))
    panel = transforms.analysis_panel(timing.reference_panel(raw, specs))
    alt = pd.DataFrame(
        {k: (robustness.yoy_of_3m_sum(ref[k]) if how == transforms.GROWTH else ref[k].rolling(3).mean().diff(12))
         for k, how in transforms.TRANSFORMS.items() if k in ref}
    )
    md = ["# Stress tests", "", "Generated by `chipcycle stress`. Each section tries to break a result in "
          "results.md.", ""]

    signals = [s for s in SIGNALS if s in panel]
    targets = [t for t in TARGETS if t in panel]

    # 1 + 3: surrogate test and effective sample size
    rows = []
    for x in signals:
        for y in targets:
            pair = panel[[x, y]].dropna()
            if len(pair) < 48:
                continue
            r = robustness.surrogate_lead_test(pair[x], pair[y])
            rows.append({"signal": x, "target": y, "n_rows": len(pair),
                         "effective_n": robustness.effective_n(pair[x], pair[y]), **r})
    sur = pd.DataFrame(rows)
    sur.to_csv(RESULTS_DIR / "stress_surrogates.csv", index=False)
    md += ["## 1. Is there a lead at all? (surrogate test)", "",
           "`best_lead_corr`: the largest |correlation| at leads of 1-12 months. `naive_band`: the usual "
           "1.96/sqrt(n) cutoff. `null_95pct`: the cutoff from 500 phase-randomized surrogates, which keep "
           "each series' persistence and account for picking the best of 12 lags. `effective_n`: how many "
           "independent observations the overlapping growth rates are really worth.", "",
           _md(sur, "{:.3f}"), ""]

    # 2: multiple testing
    ll_path = RESULTS_DIR / "lead_lag.csv"
    if ll_path.exists():
        ll = pd.read_csv(ll_path)
        ll["granger_p_bh"] = robustness.benjamini_hochberg(ll["granger_p_signal_to_target"])
        md += ["## 2. Granger tests after correcting for multiple comparisons", "",
               "Benjamini-Hochberg false-discovery-rate adjustment across all pairs.", "",
               _md(ll[["signal", "target", "granger_p_signal_to_target", "granger_p_bh",
                       "granger_p_target_to_signal"]], "{:.4f}"), ""]

    # 4: specification grid
    md += ["## 3. Does the forecast result depend on my choices? (specification grid)", "",
           "Every combination of lag counts p, q in {1, 3, 6}, training minimum in {36, 48, 72} months, "
           "start in {2014, 2016, 2018} and two growth transforms (monthly YoY, YoY of a 3-month sum).", ""]
    for x in [s for s in ("kr_semi_exports", "kr_memory_exports") if s in panel]:
        if "us_indpro" not in panel:
            break
        grid = robustness.spec_grid({"yoy": panel, "yoy_3m_sum": alt}, x, "us_indpro")
        if grid.empty:
            continue
        grid.to_csv(RESULTS_DIR / f"stress_grid_{x}.csv", index=False)
        md += [f"**{NAMES[x]} → US industrial production**", "", _md(robustness.summarize_grid(grid), "{:.1f}"), ""]

    # Where does the forecast gain come from? Year by year, and without COVID.
    md += ["## 3b. Is the forecast gain just COVID?", "",
           "Squared-error saving by year (baseline minus chip model; positive = chips helped), and the RMSE "
           "change with the COVID shock (target months 2020-03 to 2021-06) removed.", ""]
    covid = (pd.Timestamp("2020-03-01"), pd.Timestamp("2021-06-30"))
    yearly, covid_rows = {}, []
    for x in [s for s in ("kr_semi_exports", "kr_memory_exports") if s in panel]:
        if "us_indpro" not in panel:
            break
        for h in (3, 6):
            fc = forecast.oos_forecast(panel["us_indpro"], panel[x], h)
            gain = (fc["actual"] - fc["baseline"]) ** 2 - (fc["actual"] - fc["augmented"]) ** 2
            yearly[f"{x} h={h}"] = gain.groupby(gain.index.year).sum()
            keep = ~((fc.index >= covid[0]) & (fc.index <= covid[1]))
            for label, sub in (("all", fc), ("ex-COVID", fc[keep])):
                e_b, e_a = sub["actual"] - sub["baseline"], sub["actual"] - sub["augmented"]
                _, dm_p = forecast.diebold_mariano(e_b.to_numpy(), e_a.to_numpy(), h)
                covid_rows.append({"signal": x, "h": h, "sample": label, "n": len(sub),
                                   "rmse_change_pct": 100 * (np.sqrt((e_a**2).mean()) / np.sqrt((e_b**2).mean()) - 1),
                                   "dm_p": dm_p})
    if yearly:
        yt = pd.DataFrame(yearly)
        yt.index.name = "year"
        md += [_md(yt, "{:.1f}"), "", _md(pd.DataFrame(covid_rows), "{:.3f}"), ""]

    # Direction vs. size, forecast combination, rolling window
    from chipcycle import backtest

    md += ["## 3c. Direction vs. size, and two attempted fixes", "",
           "`dir_*`: share of correct calls on whether industrial production growth will be higher or lower in "
           "h months. `rmse_*`: forecast error versus the baseline, in percent. `combo` averages the baseline "
           "and chip forecasts (no tuning). `rolling` refits on only the last 48 months (exploratory: tried "
           "once after seeing the 2023 break).", ""]
    rows = []
    for x in [s for s in ("kr_semi_exports", "kr_memory_exports") if s in panel]:
        if "us_indpro" not in panel:
            break
        for h in (3, 6):
            fc = forecast.oos_forecast(panel["us_indpro"], panel[x], h)
            fc["combo"] = (fc["baseline"] + fc["augmented"]) / 2
            roll = forecast.oos_forecast(panel["us_indpro"], panel[x], h, window=48)
            for label, keep in (("all", slice(None)), ("ex-COVID", None), ("2023 on", "2023-01-01")):
                if label == "ex-COVID":
                    sub = fc[~((fc.index >= covid[0]) & (fc.index <= covid[1]))]
                    rsub = roll[~((roll.index >= covid[0]) & (roll.index <= covid[1]))]
                elif label == "2023 on":
                    sub, rsub = fc.loc[keep:], roll.loc[keep:]
                else:
                    sub, rsub = fc, roll
                rmse = lambda f, c: float(np.sqrt(((f["actual"] - f[c]) ** 2).mean()))  # noqa: E731
                combo = sub.assign(augmented=sub["combo"])
                rows.append({
                    "signal": x, "h": h, "sample": label, "n": len(sub),
                    "dir_baseline": backtest.direction_hits(sub, panel["us_indpro"])["hit_baseline_pct"],
                    "dir_chips": backtest.direction_hits(sub, panel["us_indpro"])["hit_augmented_pct"],
                    "dir_combo": backtest.direction_hits(combo, panel["us_indpro"])["hit_augmented_pct"],
                    "rmse_chips": 100 * (rmse(sub, "augmented") / rmse(sub, "baseline") - 1),
                    "rmse_combo": 100 * (rmse(sub, "combo") / rmse(sub, "baseline") - 1),
                    "rmse_rolling": 100 * (rmse(rsub, "augmented") / rmse(rsub, "baseline") - 1),
                })
    if rows:
        dc = pd.DataFrame(rows)
        dc.to_csv(RESULTS_DIR / "stress_direction_fixes.csv", index=False)
        md += [_md(dc, "{:.1f}"), ""]

    # 5 + 6: market robustness
    md += ["## 4. Market results: release-lag sensitivity and bootstrap intervals", ""]
    for x in [s for s in ("kr_semi_exports", "kr_memory_exports") if s in panel]:
        for m in [t for t in ("sox", "mu") if t in raw]:
            sens = robustness.release_lag_sensitivity(raw[m], panel[x].dropna())
            fc, res = forecast.market_test(raw[m], panel[x].dropna(), REGISTRY[x].release_lag_days, h=3)
            if fc.empty:
                continue
            lo, hi = robustness.block_bootstrap_r2(fc)
            md += [f"**{NAMES[x]} → {NAMES[m]}**: OOS R² {res['oos_r2_pct']:.2f}%, "
                   f"90% block-bootstrap interval [{lo:.2f}%, {hi:.2f}%]", "", _md(sens, "{:.2f}"), ""]

    # Micron nowcast stress
    try:
        mq = micron.fetch_micron_quarters()
    except Exception:
        mq = None
    if mq is not None and mq[1] == "SEC EDGAR" and "kr_memory_exports" in raw:
        km = timing.to_monthly(raw["kr_memory_exports"], "M")
        rows = []
        for label, kw in (("full quarter (baseline spec)", {}),
                          ("first 2 months only (earlier, realistic)", {"n_months": 2}),
                          ("before the AI boom (to 2022-12)", {"end": "2022-12-31"})):
            _, s = micron.micron_analysis(mq[0], km, **kw)
            if "rmse_korea_pp" in s:
                rows.append({"version": label, "quarters": s["nowcast_quarters"], "corr": s["corr_same_quarter"],
                             "rmse_naive_pp": s["rmse_naive_pp"], "rmse_korea_pp": s["rmse_korea_pp"],
                             "direction_right_pct": s["direction_right_pct"], "dm_p": s["dm_p"]})
        if rows:
            md += ["## 5. Micron nowcast under stress", "",
                   "Same out-of-sample nowcast, three ways. The naive baseline assumes last quarter's growth "
                   "repeats. Note what it is *not* compared with: Micron's own guidance and analyst consensus, "
                   "which are much harder baselines (not available for free).", "",
                   _md(pd.DataFrame(rows), "{:.2f}"), ""]

    # 7: Lunar New Year
    if "kr_semi_exports" in raw:
        lvl = timing.to_monthly(raw["kr_semi_exports"], "M")
        lny = robustness.lunar_new_year_check(lvl)
        md += ["## 6. Lunar New Year distortion", "",
               "Standard deviation of YoY growth by calendar month. Korea's data aren't seasonally adjusted, "
               "and the holiday moves between January and February.", "",
               _md(lny.T, "{:.1f}"), "",
               f"January and February combined: {lny.attrs['jan_feb_combined_std']:.1f}.", ""]

    out = RESULTS_DIR / "stress.md"
    out.write_text("\n".join(md))
    return out


def chart_equity(curves: pd.DataFrame, title: str, name: str) -> str:
    fig, ax = plt.subplots(figsize=(9, 4))
    colors = {"buy and hold": INK2, "level": BLUE, "momentum": ORANGE, "model": "#1baf7a"}
    for col in curves.columns:
        ax.plot(curves.index, curves[col], color=colors.get(col, INK), linewidth=2 if col != "buy and hold" else 1.5,
                label=col)
    ax.set_yscale("log")
    _style(ax, title, "growth of $1 (log scale)")
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, ncols=4)
    return _save(fig, name)


def build_backtest(raw: dict[str, pd.Series]) -> Path:
    from chipcycle import backtest

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    specs = {k: REGISTRY[k] for k in raw}
    panel = transforms.analysis_panel(timing.reference_panel(raw, specs))
    md = ["# Backtest", "", "Generated by `chipcycle backtest`. Rules were fixed before any result was seen "
          "(see `src/chipcycle/backtest.py`) and every one is reported.", ""]

    # Economy: direction calls
    rows = []
    for x in [s for s in SIGNALS if s in panel]:
        for y in [t for t in ("us_indpro", "us_baa_spread", "liquidity") if t in panel]:
            for h in (1, 3, 6):
                fc = forecast.oos_forecast(panel[y], panel[x], h)
                if len(fc) < 24:
                    continue
                rows.append({"signal": x, "target": y, "h": h, **backtest.direction_hits(fc, panel[y])})
    if rows:
        dh = pd.DataFrame(rows)
        dh["chips_add_pp"] = dh["hit_augmented_pct"] - dh["hit_baseline_pct"]
        dh.to_csv(RESULTS_DIR / "backtest_direction.csv", index=False)
        md += ["## Economy: does it call the direction right?", "",
               "Will the target's growth be higher or lower in h months than today? `hit_baseline_pct` uses "
               "only the target's own history; `hit_augmented_pct` adds chip exports. `chips_add_pp` is the "
               "difference in percentage points.", "", _md(dh, "{:.1f}"), ""]

    # Markets
    md += ["## Markets: timing rules", "",
           "`random_timing_pctile`: the rule's Sharpe ratio versus 1,000 random strategies with the same time in "
           "market. Above 95 means the timing very likely added something; around 50 means it did not. "
           "`months_right_pct`: share of months the rule held during a gain or sat out a loss.", ""]
    for x in [s for s in ("kr_semi_exports", "kr_memory_exports") if s in panel]:
        for m in [t for t in ("acwi", "sox", "mu") if t in raw]:
            table, curves = backtest.market_backtest(raw[m], panel[x].dropna(), REGISTRY[x].release_lag_days)
            if table.empty:
                continue
            table.to_csv(RESULTS_DIR / f"backtest_{x}_{m}.csv", index=False)
            md += [f"### {NAMES[x]} → {NAMES[m]}", "", _md(table, "{:.2f}"), ""]
            if m in ("sox", "mu"):
                md += [f"![]({chart_equity(curves, f'{NAMES[x]} rules on {NAMES[m]}', f'equity_{x}_{m}.png')})", ""]

    out = RESULTS_DIR / "backtest.md"
    out.write_text("\n".join(md))
    return out
