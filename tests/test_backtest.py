import numpy as np
import pandas as pd

from chipcycle.backtest import COST, random_timing_percentile, run_rule, stats


def _rets(n=240, seed=0):
    idx = pd.date_range("2005-01-16", periods=n, freq="MS") + pd.Timedelta(days=15)
    return pd.Series(np.random.default_rng(seed).normal(0.005, 0.05, n), index=idx)


def test_switching_costs_are_charged():
    r = pd.Series(0.0, index=range(4))
    out = run_rule(r, pd.Series([1, 0, 1, 1]))
    # Enter, exit, enter: three switches.
    assert np.isclose(out.sum(), 3 * np.log(1 - COST))


def test_foresight_rule_beats_random_timing():
    r = _rets()
    assert random_timing_percentile(r, (r > 0).astype(int), n=300) > 99


def test_coin_flip_rule_is_unremarkable():
    r = _rets()
    coin = pd.Series(np.random.default_rng(9).integers(0, 2, len(r)), index=r.index)
    assert 5 < random_timing_percentile(r, coin, n=300) < 95


def test_stats_on_flat_growth():
    r = pd.Series(np.log(1.01), index=range(12))
    s = stats(r)
    assert np.isclose(s["cagr_pct"], 100 * (1.01**12 - 1))
    assert s["max_drawdown_pct"] == 0
