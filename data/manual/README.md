# Hand-collected series

Some of the most useful series have no clean free API, so they live here as
CSVs with two columns:

```
date,value
2024-01-01,9370000000
2024-02-01,9940000000
```

`date` can be any day inside the reference month. `value` is in US dollars.
One row per month and no duplicate months.

Korea's chip exports are no longer manual: they come from UN Comtrade
automatically (see `src/chipcycle/ingest/comtrade.py`).

## tw_exports.csv: Taiwan exports (optional, not used yet)

Published by Taiwan's Ministry of Finance around the 7th to 9th of the
following month. History is on the MOF trade statistics portal
(portal.sw.nat.gov.tw). Start with total exports. Electronic components
(HS chapter 85) can be added as its own series later.

To use it, add a `Series(..., "csv", "tw_exports.csv", ...)` entry to
`src/chipcycle/registry.py` with an 8-day release lag.

## kr_semi_motr.csv: Korea semiconductor exports, recent months

Used by `chipcycle cycle`. Korea's trade ministry publishes the previous
month's semiconductor exports and the year-over-year change on the 1st of
each month. UN Comtrade posts the HS-code figures months later, so these were
transcribed from press reports to cover the gap. Columns: `date`, `value`
(USD), `yoy_pct` (as reported), `confidence` and `source` (the article).
Where two outlets differ slightly the source note says so. The ministry's
category is broader than HS 8542, so its levels run about 22% higher; the
code joins on growth, not levels (see `src/chipcycle/recent.py`).

To update: add the new month from the ministry's release, with its source.

## micron_guidance.csv: Micron's guided revenue

The midpoint and range for the next quarter, from Micron's earnings call.
The quarter end is assumed to be 13 weeks after the last reported quarter.

## dram_contract_price_reports.csv: reported memory prices

Quarterly DRAM contract price changes as reported by one outlet's summary of
TrendForce research, rounded. Low confidence. TrendForce's own pages were not
reachable from the environment this was built in, so check them directly.

