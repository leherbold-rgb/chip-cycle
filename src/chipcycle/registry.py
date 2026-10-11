"""The list of every series the project uses, and when each one becomes public.

Why the release lag matters
---------------------------
A data point is labelled with the period it describes ("March industrial
production"), but nobody could trade on it until it was published. US
industrial production for March comes out around April 16. Korea's March
exports come out on April 1. If a model lines both up under "March" it is
quietly using information that did not exist yet. That is look-ahead bias,
and it is the most common way backtests lie.

Each series below therefore carries `release_lag_days`: roughly how many days
after the end of the reference period the number is published. These are
approximations of the usual release calendar. A later stage can replace them
with exact historical vintages from ALFRED.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Source = Literal["fred", "yahoo", "csv", "comtrade"]
Freq = Literal["D", "W", "M", "Q"]


@dataclass(frozen=True)
class Series:
    key: str  # our short name, used as the column name everywhere
    source: Source
    source_id: str  # FRED id, Yahoo ticker, CSV filename, or Comtrade "reporter:hs:flow"
    freq: Freq  # native frequency as published
    release_lag_days: int  # days after period end until the value is public
    role: Literal["signal", "target", "market"]
    description: str


REGISTRY: dict[str, Series] = {
    s.key: s
    for s in [
        # Leading signals: the chip side.
        # Korea's customs data by HS code (via UN Comtrade). Korea Customs
        # Service publishes final monthly figures around the 15th. MOTIE's
        # flash total on the 1st uses a different product grouping, so 15 days
        # is the honest lag for this series.
        Series(
            "kr_semi_exports", "comtrade", "410:8542:X", "M", 15, "signal",
            "Korea integrated circuit exports, USD (HS 8542, UN Comtrade)",
        ),
        Series(
            "kr_memory_exports", "comtrade", "410:854232:X", "M", 15, "signal",
            "Korea memory chip exports, USD (HS 854232: DRAM and NAND, UN Comtrade)",
        ),
        Series(
            "kr_exports_total", "fred", "XTEXVA01KRM667S", "M", 1, "signal",
            "Korea total exports, USD, seasonally adjusted (OECD MEI via FRED)",
        ),
        # Real-economy and credit targets.
        Series(
            "us_indpro", "fred", "INDPRO", "M", 16, "target",
            "US industrial production index (Fed G.17, mid following month)",
        ),
        # FRED only serves the last three years of the ICE BofA high yield
        # spread, so Moody's Baa minus 10-year Treasury stands in for credit
        # stress. It is investment grade, but it has decades of history.
        Series(
            "us_baa_spread", "fred", "BAA10Y", "D", 1, "target",
            "Moody's Baa corporate yield minus 10-year Treasury, percent",
        ),
        # Liquidity proxy components: Fed balance sheet minus TGA minus reverse repo.
        Series(
            "fed_assets", "fred", "WALCL", "W", 1, "target",
            "Fed total assets, USD millions (H.4.1, Thursday after Wednesday close)",
        ),
        Series(
            "tga", "fred", "WTREGEN", "W", 1, "target",
            "Treasury General Account, USD millions (weekly)",
        ),
        Series(
            "rrp", "fred", "RRPONTSYD", "D", 1, "target",
            "Overnight reverse repo, USD billions (daily)",
        ),
        # Markets.
        Series("acwi", "yahoo", "ACWI", "D", 0, "market", "iShares MSCI ACWI ETF (global equities)"),
        Series("sox", "yahoo", "^SOX", "D", 0, "market", "PHLX Semiconductor Index"),
        Series("mu", "yahoo", "MU", "D", 0, "market", "Micron Technology"),
    ]
}


def by_source(source: Source) -> list[Series]:
    return [s for s in REGISTRY.values() if s.source == source]
