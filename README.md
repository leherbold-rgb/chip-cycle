# chip-cycle

**Do Korean and Taiwanese semiconductor exports lead the global economy?**

Korea publishes its exports for the previous month on the 1st of each month.
That makes it one of the earliest pieces of hard data on the world economy.
Chips sit at the start of almost every supply chain, so when companies expect
demand to change, chip orders move first.

This project tests that claim properly. It measures how many months chip
exports lead industrial production, credit spreads, liquidity and equities;
checks whether the lead is stable over time; tests whether it improves
forecasts out of sample; and applies it to Micron, whose two main competitors
are Korean.

## Status

| Stage | What | State |
|---|---|---|
| 1 | Data pipeline with release-date alignment | Done ([notes](docs/stage-1-data.md)) |
| 2 | Transforms: growth rates, stationarity tests, liquidity proxy | Next |
| 3 | Lead-lag: prewhitened cross-correlation, Granger causality | |
| 4 | Stability: rolling-window lags, structural breaks (2008, 2018, AI cycle) | |
| 5 | Out-of-sample forecasting vs. baseline, Diebold-Mariano test | |
| 6 | Micron revenue nowcast from Korean memory exports | |
| 7 | Automated monthly report | |

No results are reported until the stage that produces them is done.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                  # 12 tests, no network needed
chipcycle fetch         # FRED + Yahoo into data/raw/
chipcycle panel         # reference and real-time panels into data/processed/
chipcycle status
```

The Korea and Taiwan chip series need a one-time manual download. See
[data/manual/README.md](data/manual/README.md).

## Layout

```
src/chipcycle/
  registry.py   every series, its source, and its publication lag
  ingest/       FRED, Yahoo, and hand-collected CSV fetchers
  cache.py      local parquet cache
  timing.py     monthly alignment, reference and real-time panels
  cli.py
tests/          parsing and look-ahead tests
docs/           one write-up per stage
```
