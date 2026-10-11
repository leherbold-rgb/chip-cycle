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

## tw_exports.csv: Taiwan exports

Published by Taiwan's Ministry of Finance around the 7th to 9th of the
following month. History is on the MOF trade statistics portal
(portal.sw.nat.gov.tw). Start with total exports. Electronic components
(HS chapter 85) can be added as its own series later.
