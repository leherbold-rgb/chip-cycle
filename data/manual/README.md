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

## kr_semi_exports.csv: Korea semiconductor exports

The core signal. Published by Korea's Ministry of Trade, Industry and Energy
(MOTIE) on the 1st of each month for the previous month, in a press release
that breaks exports out by product, semiconductors included.

Where to get history:
- **K-stat** (stat.kita.net, run by the Korea International Trade
  Association): trade by MTI code. Semiconductors are MTI 831. Monthly export
  values back to the 1990s, downloadable to Excel.
- Alternative: **Korea Customs Service** trade statistics (unipass.customs.go.kr),
  by HS code 8542 (integrated circuits).

Keep one source for the whole history. Mixing MTI 831 and HS 8542 will
create a break in the series.

## tw_exports.csv: Taiwan exports

Published by Taiwan's Ministry of Finance around the 7th to 9th of the
following month. History is on the MOF trade statistics portal
(portal.sw.nat.gov.tw). Start with total exports. Electronic components
(HS chapter 85) can be added as its own series later.
