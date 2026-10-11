# Stage 1: getting the data right

Nothing in this stage tests the hypothesis. It builds the foundation that
every later result depends on, and it handles the one mistake that would
invalidate all of them.

## What was built

| File | Job |
|---|---|
| `registry.py` | Every series, where it comes from, and how many days after the period ends it is published |
| `ingest/` | One fetcher per source (FRED, Yahoo, UN Comtrade, hand-collected CSV). Each returns the same shape |
| `cache.py` | Saves each series to `data/raw/` so analysis never waits on, or silently changes with, a network call |
| `timing.py` | Converts everything to monthly and builds the two panels below |
| `cli.py` | `chipcycle fetch`, `chipcycle panel`, `chipcycle status` |

## The idea that matters: two panels

Every economic number has two dates: the period it **describes** and the day
it was **published**. US industrial production for March describes March but
comes out around April 16.

**Reference panel**: one row per month, each value filed under the month it
describes. Use this for questions about the economy: "does chip activity in
month m move ahead of production in month m+k?"

**Real-time panel**: one row per decision date, each value being the latest
one actually published by that date. Use this for questions about
forecasting: "on April 2, what could I have known, and does it help predict
what comes out on April 16?"

If you forecast with the reference panel, you use numbers before they
existed. This is called **look-ahead bias**, and it makes backtests look
better than reality. `tests/test_timing.py` checks that the real-time panel
cannot do this.

## Why decision dates default to the 2nd of the month

Korea publishes March exports on April 1. The US publishes March industrial
production around April 16. On April 2 you have a two-week head start on
hard data about March. On April 30 you don't. The "lead" this project
measures partly comes from **publication timing**, separate from any economic
lead. Keeping those two apart is a good point to make in an interview.

## Where the Korea chip data comes from

Korea reports customs trade to the UN by HS commodity code. HS 8542 is all
integrated circuits; HS 854232 is memory (DRAM and NAND), the slice that
matters for Micron. UN Comtrade serves both monthly back to 2010 with no key.

Two dates are worth knowing. MOTIE's flash release on the 1st is the famous
early number, but it uses Korea's own product grouping (MTI codes), not HS.
The HS-based customs figures come out around the 15th, so the registry uses
a 15-day lag for these series. That is conservative: the true information
edge is a bit larger than the model assumes, which is the safe direction to
be wrong in.

## Choices worth defending

- **Daily and weekly data are averaged within the month**, not sampled on
  the last day. Monthly economic data describe a whole month, so an average
  is the like-for-like comparison. A month-end snapshot would also carry
  more noise.
- **An unfinished month is never used.** A February average is not usable on
  February 10. The test `test_realtime_ignores_partial_current_month_of_daily_data`
  checks this.
- **Release lags are approximations.** They encode the typical calendar, not
  each historical release date, and they ignore **revisions**: industrial
  production is revised for months after its first print. A stricter version
  would pull first-release values ("vintages") from ALFRED. That is a known
  limitation, worth stating plainly.

## Questions to be ready for

- *What's the difference between the two panels?* Described period vs. publication date. One is for studying the economy, the other for testing forecasts.
- *How do you prevent look-ahead bias?* A backward as-of join on release dates, plus tests that fail if a future value gets in.
- *What's still imperfect?* Approximate release lags and revised rather than first-print data. ALFRED vintages would fix both.
