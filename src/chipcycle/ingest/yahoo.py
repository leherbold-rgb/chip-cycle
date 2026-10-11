"""Daily adjusted closes from Yahoo Finance."""

from __future__ import annotations

import pandas as pd


def fetch_yahoo(ticker: str, start: str = "1995-01-01") -> pd.Series:
    import yfinance as yf

    df = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    if df.empty:
        raise RuntimeError(f"Yahoo returned no data for {ticker}")
    close = df["Close"]
    # Newer yfinance returns a one-column frame keyed by ticker.
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close.index = pd.DatetimeIndex(close.index.tz_localize(None), name="date")
    return close.astype(float).dropna().sort_index()
