"""Command line entry point.

    chipcycle fetch [--refresh]   download everything into data/raw/
    chipcycle panel               build both panels into data/processed/
    chipcycle status              show what is cached and how far it reaches
    chipcycle analyze             run stages 2-6 and write results/
    chipcycle stress              run robustness checks into results/stress.md
    chipcycle backtest            accuracy and trading backtests into results/backtest.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from chipcycle import cache, timing
from chipcycle.registry import REGISTRY

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"


def _fetch(refresh: bool) -> dict[str, pd.Series]:
    raw, failures = {}, []
    for spec in REGISTRY.values():
        try:
            raw[spec.key] = cache.load_or_fetch(spec, refresh=refresh)
            s = raw[spec.key]
            print(f"  ok    {spec.key:<18} {len(s):>6} obs  {s.index.min():%Y-%m} to {s.index.max():%Y-%m}")
        except Exception as e:  # keep going so one dead source doesn't block the rest
            failures.append(spec.key)
            print(f"  FAIL  {spec.key:<18} {type(e).__name__}: {e}")
    if failures:
        print(f"\n{len(failures)} series failed: {', '.join(failures)}")
    return raw


def cmd_fetch(args: argparse.Namespace) -> int:
    print("Fetching series")
    raw = _fetch(args.refresh)
    return 0 if raw else 1


def cmd_panel(args: argparse.Namespace) -> int:
    raw = _fetch(refresh=False)
    if not raw:
        print("Nothing to build from.")
        return 1
    specs = {k: REGISTRY[k] for k in raw}
    ref = timing.reference_panel(raw, specs)
    start = ref.index.min().strftime("%Y-%m")
    end = pd.Timestamp.today().strftime("%Y-%m")
    rt = timing.realtime_panel(raw, specs, timing.monthly_decision_dates(start, end))

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ref.to_parquet(PROCESSED_DIR / "panel_reference.parquet")
    rt.values.to_parquet(PROCESSED_DIR / "panel_realtime_values.parquet")
    rt.reference_month.to_parquet(PROCESSED_DIR / "panel_realtime_refmonth.parquet")
    print(f"\nWrote panels to {PROCESSED_DIR}")

    latest = rt.months_stale.iloc[-1].sort_values()
    print(f"\nAs of {rt.values.index[-1]:%Y-%m-%d}, months between today and the latest published value:")
    for key, n in latest.items():
        print(f"  {key:<18} {n}")
    return 0


def _cached() -> dict[str, pd.Series]:
    raw = {}
    for spec in REGISTRY.values():
        path = cache.cache_path(spec)
        if path.exists():
            raw[spec.key] = cache.load(path).rename(spec.key)
    return raw


def cmd_analyze(args: argparse.Namespace) -> int:
    from chipcycle import micron, report

    raw = _cached()
    if not raw:
        print("No cached data. Run `chipcycle fetch` first.")
        return 1
    missing = [k for k in REGISTRY if k not in raw]
    if missing:
        print(f"Not cached, skipped: {', '.join(missing)}")
    try:
        mq = micron.fetch_micron_quarters()
        print(f"Micron revenue: {len(mq[0])} quarters from {mq[1]}")
    except Exception as e:
        print(f"Micron revenue unavailable: {type(e).__name__}: {e}")
        mq = None
    out = report.build(raw, mq)
    print(f"Wrote {out}")
    return 0


def cmd_stress(args: argparse.Namespace) -> int:
    from chipcycle import report

    print(f"Wrote {report.build_stress(_cached())}")
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    from chipcycle import report

    print(f"Wrote {report.build_backtest(_cached())}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    for spec in REGISTRY.values():
        path = cache.cache_path(spec)
        if spec.source == "csv":
            state = "manual CSV"
        elif path.exists():
            s = cache.load(path)
            state = f"cached, {s.index.min():%Y-%m} to {s.index.max():%Y-%m}"
        else:
            state = "not fetched"
        print(f"  {spec.key:<18} {spec.role:<7} {state}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="chipcycle")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download all series")
    f.add_argument("--refresh", action="store_true", help="ignore the cache")
    f.set_defaults(func=cmd_fetch)
    sub.add_parser("panel", help="build reference and real-time panels").set_defaults(func=cmd_panel)
    sub.add_parser("status", help="show cache state").set_defaults(func=cmd_status)
    sub.add_parser("analyze", help="run the analysis and write results/").set_defaults(func=cmd_analyze)
    sub.add_parser("stress", help="run robustness checks").set_defaults(func=cmd_stress)
    sub.add_parser("backtest", help="accuracy and trading backtests").set_defaults(func=cmd_backtest)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
