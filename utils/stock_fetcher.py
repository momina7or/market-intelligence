"""
Stock Fetcher — pulls historical price data via yfinance (completely free).
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional


class StockFetcher:
    def fetch(self, ticker: str, days: int = 30) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data for a single ticker.
        Returns a DataFrame with DatetimeIndex or None on failure.
        """
        end = datetime.today()
        start = end - timedelta(days=days)
        try:
            df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
            if df.empty:
                return None
            # Flatten MultiIndex columns if present (yfinance ≥0.2.x)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df[["Open", "High", "Low", "Close", "Volume"]]
        except Exception:
            return None

    def fetch_many(self, tickers: list[str], days: int = 30) -> dict[str, pd.DataFrame]:
        """Fetch multiple tickers. Returns dict of {ticker: DataFrame}."""
        results = {}
        for ticker in tickers:
            df = self.fetch(ticker, days=days)
            if df is not None:
                results[ticker] = df
        return results

    def get_price_change(self, df: pd.DataFrame) -> dict:
        """
        Compute summary statistics from a price DataFrame.
        Returns dict with keys: start_price, end_price, change_pct, volatility.
        """
        if df is None or df.empty:
            return {}
        try:
            start_price = float(df["Close"].iloc[0])
            end_price = float(df["Close"].iloc[-1])
            change_pct = ((end_price - start_price) / start_price) * 100
            daily_returns = df["Close"].pct_change().dropna()
            volatility = float(daily_returns.std() * (252 ** 0.5) * 100)  # annualised %
            return {
                "start_price": round(start_price, 2),
                "end_price": round(end_price, 2),
                "change_pct": round(change_pct, 2),
                "volatility": round(volatility, 1),
            }
        except Exception:
            return {}
