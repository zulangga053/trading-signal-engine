import time
import pandas as pd
import yfinance as yf
from typing import Optional

CACHE: dict[str, dict] = {}
CACHE_TTL: dict[str, int] = {
    '1m': 30,
    '2m': 60,
    '5m': 120,
    '15m': 300,
    '30m': 600,
    '1h': 900,
    '4h': 3600,
    '1d': 21600,
    '1wk': 43200,
}

def get_rates(
    yahoo_ticker: str,
    interval: str = '1h',
    period: str = '1mo',
    force_refresh: bool = False,
) -> pd.DataFrame:
    cache_key = f'{yahoo_ticker}:{interval}:{period}'
    now = time.time()

    if not force_refresh and cache_key in CACHE:
        entry = CACHE[cache_key]
        ttl = CACHE_TTL.get(interval, 300)
        if now - entry['ts'] < ttl:
            return entry['df']

    ticker = yf.Ticker(yahoo_ticker)
    df = ticker.history(period=period, interval=interval)

    if df.empty:
        raise ValueError(f'No data for {yahoo_ticker} ({interval})')

    df.columns = [c.lower() for c in df.columns]
    df.index.name = 'time'

    CACHE[cache_key] = {'df': df, 'ts': now}
    return df

def invalidate_cache():
    CACHE.clear()

def prefetch_pairs(pairs: list[tuple[str, str, str]], mode: str):
    for yahoo_ticker, interval, period in pairs:
        try:
            get_rates(yahoo_ticker, interval, period)
        except Exception:
            pass
