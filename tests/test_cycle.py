import numpy as np
import pandas as pd
import pytest

from chipcycle.cycle import cycle_turns, micron_table
from chipcycle.recent import extend_by_growth, to_percent


def _months(start, n, value=100.0):
    return pd.Series(value, index=pd.date_range(start, periods=n, freq="ME"))


def test_to_percent_differs_a_lot_from_log_points_at_large_growth():
    assert to_percent(0.0) == 0
    assert to_percent(100.0) == pytest.approx(171.83, abs=0.01)
    assert to_percent(156.7) == pytest.approx(379.0, abs=1.0)  # Micron's latest YoY


def test_extension_applies_growth_to_the_level_a_year_earlier():
    base = _months("2025-01-31", 12, 100.0)
    rep = pd.DataFrame({"yoy_pct": [50.0, 100.0]}, index=pd.to_datetime(["2026-01-31", "2026-02-28"]))
    out = extend_by_growth(base, rep)
    assert out["2026-01-31"] == pytest.approx(150.0)
    assert out["2026-02-28"] == pytest.approx(200.0)
    assert out["2025-12-31"] == 100.0  # history untouched


def test_extension_chains_past_one_year_and_skips_months_already_in_base():
    base = _months("2025-01-31", 12, 100.0)
    rep = pd.DataFrame({"yoy_pct": [999.0, 100.0, 50.0]},
                       index=pd.to_datetime(["2025-12-31", "2026-01-31", "2027-01-31"]))
    out = extend_by_growth(base, rep)
    assert out["2025-12-31"] == 100.0  # December was already in the base; reported value ignored
    assert out["2027-01-31"] == pytest.approx(100.0 * 2 * 1.5)  # chained through Jan 2026


def test_extension_fails_loudly_without_a_base_month():
    base = _months("2025-06-30", 6, 100.0)
    rep = pd.DataFrame({"yoy_pct": [10.0]}, index=pd.to_datetime(["2026-01-31"]))
    with pytest.raises(ValueError, match="a year before"):
        extend_by_growth(base, rep)


def _quarters(values, start="2010-02-28"):
    idx = [pd.Timestamp(start) + pd.Timedelta(days=int(91.3 * i)) for i in range(len(values))]
    return pd.Series(values, index=pd.DatetimeIndex(idx), dtype=float)


def test_cycle_turns_finds_upswing_lengths_and_the_yoy_lead():
    # Two humps with a trough between. Growth rates peak before levels do.
    rev = _quarters([10, 9, 8, 7, 8, 10, 14, 19, 24, 28, 31, 33, 34, 33, 31, 28, 25, 23, 22, 21, 22, 24, 27, 31, 36])
    t = cycle_turns(rev)
    first = t.iloc[0]
    assert first["up_quarters"] == 9           # trough index 3 -> peak index 12
    assert first["yoy_peak_lead_quarters"] > 0  # YoY peaks before revenue does
    assert first["down_quarters"] == 7          # peak 12 -> trough 19
    assert bool(t.iloc[-1]["ongoing"]) is True  # the last trough has no later peak


def test_guided_quarter_year_over_year_depends_on_year_ago_growth():
    q = pd.DataFrame({
        "end": pd.to_datetime(["2025-02-27", "2025-05-29", "2025-08-28", "2025-11-27", "2026-02-26", "2026-05-28", "2026-09-03"]),
        "revenue": np.array([8.0, 9.0, 10.0, 12.0, 20.0, 30.0, 40.0]) * 1e9,
    })
    g = pd.DataFrame({"quarter_end": ["2026-12-03"], "mid_billion": [44.0]})
    t = micron_table(q, g)
    last = t.iloc[-1]
    assert bool(last["guided"]) and last["revenue_billion"] == 44.0
    assert last["qoq_pct"] == pytest.approx(10.0)
    # Same quarter a year earlier (ended 2025-11-27) grew 20% on the quarter before.
    assert last["year_ago_qoq_pct"] == pytest.approx(20.0)
    # 10% < 20%, so YoY growth falls: 40/10 -> 44/12.
    assert t["yoy_pct"].iloc[-1] < t["yoy_pct"].iloc[-2]
