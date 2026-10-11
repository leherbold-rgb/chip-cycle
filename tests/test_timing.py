"""The look-ahead guarantees. These are the tests that matter most."""

import pandas as pd

from chipcycle.registry import Series
from chipcycle.timing import (
    monthly_decision_dates,
    realtime_panel,
    reference_panel,
    to_monthly,
)

KOREA = Series("korea", "csv", "", "M", 1, "signal", "")
INDPRO = Series("indpro", "fred", "", "M", 16, "target", "")
DAILY = Series("daily", "fred", "", "D", 1, "target", "")
SPECS = {s.key: s for s in [KOREA, INDPRO, DAILY]}


def monthly(values, start="2024-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"), dtype=float)


def test_monthly_series_moves_to_month_end():
    out = to_monthly(monthly([1, 2]), "M")
    assert list(out.index) == [pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-29")]


def test_daily_series_averages_within_month():
    s = pd.Series([1.0, 3.0, 10.0], index=pd.to_datetime(["2024-01-05", "2024-01-20", "2024-02-01"]))
    out = to_monthly(s, "D")
    assert out.loc["2024-01-31"] == 2.0
    assert out.loc["2024-02-29"] == 10.0


def test_reference_panel_aligns_by_described_month():
    p = reference_panel({"korea": monthly([1, 2, 3]), "indpro": monthly([10, 20, 30])}, SPECS)
    assert p.loc["2024-02-29"].tolist() == [2.0, 20.0]


def test_decision_dates_default_to_second_of_month():
    d = monthly_decision_dates("2024-01", "2024-03")
    assert list(d.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-02-02", "2024-03-02"]


def test_realtime_never_uses_unpublished_values():
    raw = {"korea": monthly([1, 2, 3]), "indpro": monthly([10, 20, 30])}
    rt = realtime_panel(raw, SPECS, pd.DatetimeIndex(["2024-04-02", "2024-04-16", "2024-04-17"]))
    # April 2: Korea March (released Apr 1) is out, US March IP (Apr 16) is not.
    assert rt.values.loc["2024-04-02"].tolist() == [3.0, 20.0]
    assert rt.months_stale.loc["2024-04-02"].tolist() == [1, 2]
    # Released on the 16th counts as known on the 16th.
    assert rt.values.loc["2024-04-16", "indpro"] == 30.0


def test_realtime_is_empty_before_first_release():
    rt = realtime_panel({"korea": monthly([1])}, SPECS, pd.DatetimeIndex(["2024-01-15"]))
    assert rt.values["korea"].isna().all()


def test_realtime_ignores_partial_current_month_of_daily_data():
    s = pd.Series(1.0, index=pd.date_range("2024-01-01", "2024-02-10", freq="D"))
    rt = realtime_panel({"daily": s}, SPECS, pd.DatetimeIndex(["2024-02-10"]))
    # February is not complete, so the latest usable month is January.
    assert rt.reference_month.iloc[0, 0] == pd.Timestamp("2024-01-31")
