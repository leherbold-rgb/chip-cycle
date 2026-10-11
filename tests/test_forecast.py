"""Forecasts must only ever use data available at the forecast origin."""

import numpy as np
import pandas as pd

from chipcycle.forecast import diebold_mariano, market_test, oos_forecast


def _series(n=120, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2000-01-31", periods=n, freq="ME")
    return pd.Series(rng.normal(size=n), index=idx)


def test_forecast_training_never_reaches_past_origin():
    y, x = _series(), _series(seed=1)
    for h in (1, 3, 6):
        fc = oos_forecast(y, x, h, min_train=24)
        # The first forecast needs min_train usable rows (after 3 lags) plus h.
        first_origin = fc["origin"].min()
        assert y.index.get_loc(first_origin) >= 24 + 2 + h - 1
        assert ((fc.index.to_period("M") - fc["origin"].dt.to_period("M")).map(lambda d: d.n) == h).all()


def test_future_values_cannot_change_past_forecasts():
    y, x = _series(), _series(seed=1)
    full = oos_forecast(y, x, 3, min_train=24)
    y2, x2 = y.copy(), x.copy()
    y2.iloc[90:] += 100  # wreck the future
    x2.iloc[90:] -= 100
    cut = oos_forecast(y2, x2, 3, min_train=24)
    early = full["origin"] < y.index[90]
    pd.testing.assert_frame_equal(
        full.loc[early, ["baseline", "augmented"]], cut.loc[early, ["baseline", "augmented"]]
    )


def test_signal_that_knows_the_future_wins():
    y = _series()
    x = y.shift(-3)  # x_t equals y_{t+3}: perfect foresight, a sanity check of the machinery
    fc = oos_forecast(y, x, 3, min_train=24)
    e_b, e_a = fc["actual"] - fc["baseline"], fc["actual"] - fc["augmented"]
    assert (e_a**2).mean() < 0.01 * (e_b**2).mean()
    _, p = diebold_mariano(e_b.to_numpy(), e_a.to_numpy(), 3)
    assert p < 0.01


def test_noise_signal_does_not_win_significantly():
    fc = oos_forecast(_series(), _series(seed=7), 1, min_train=24)
    _, p = diebold_mariano(
        (fc["actual"] - fc["baseline"]).to_numpy(), (fc["actual"] - fc["augmented"]).to_numpy(), 1
    )
    assert p > 0.05


def test_market_test_respects_release_lag():
    days = pd.bdate_range("2010-01-01", "2020-12-31")
    prices = pd.Series(np.exp(np.cumsum(np.random.default_rng(3).normal(0, 0.01, len(days)))), index=days)
    signal = _series(n=132)
    signal.index = pd.date_range("2010-01-31", periods=132, freq="ME")
    fc, res = market_test(prices, signal, release_lag_days=15, h=3)
    assert res["n_forecasts"] > 0
    # Decisions happen on the 16th, after the 15-day release lag of the prior month.
    assert (fc.index.day == 16).all()
