import numpy as np
import pandas as pd

from chipcycle.robustness import benjamini_hochberg, effective_n, phase_surrogate, surrogate_lead_test


def test_bh_matches_textbook_example():
    p = pd.Series([0.01, 0.04, 0.03, 0.20])
    adj = benjamini_hochberg(p)
    assert np.allclose(adj.to_numpy(), [0.04, 0.0533333, 0.0533333, 0.20])


def test_surrogate_keeps_power_spectrum():
    rng = np.random.default_rng(0)
    x = np.cumsum(rng.normal(size=200)) * 0.1 + rng.normal(size=200)
    s = phase_surrogate(x, rng)
    assert np.allclose(np.abs(np.fft.rfft(x - x.mean())), np.abs(np.fft.rfft(s - s.mean())), rtol=1e-6)


def test_effective_n_shrinks_for_persistent_series():
    idx = pd.date_range("2000-01-31", periods=300, freq="ME")
    rng = np.random.default_rng(1)
    white = pd.Series(rng.normal(size=300), index=idx)
    assert effective_n(white, pd.Series(rng.normal(size=300), index=idx)) > 200
    smooth = white.rolling(12).sum()
    assert effective_n(smooth, smooth.shift(1)) < 100


def test_surrogate_test_detects_a_planted_lead_and_rejects_noise():
    idx = pd.date_range("2000-01-31", periods=240, freq="ME")
    rng = np.random.default_rng(2)
    x = pd.Series(rng.normal(size=240), index=idx).rolling(6).mean()
    y_linked = x.shift(3) + pd.Series(rng.normal(scale=0.2, size=240), index=idx)
    y_noise = pd.Series(rng.normal(size=240), index=idx).rolling(6).mean()
    assert surrogate_lead_test(x, y_linked, n_sur=200)["p_value"] < 0.01
    assert surrogate_lead_test(x, y_noise, n_sur=200)["p_value"] > 0.05
