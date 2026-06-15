from dataclasses import dataclass
from typing import Optional

PAIR_CATEGORIES = ['major', 'cross', 'exotic', 'commodity', 'crypto']

@dataclass
class Pair:
    symbol: str
    yahoo_ticker: str
    name: str
    category: str
    source: str

PAIRS: list[Pair] = [
    # Major Forex
    Pair('EUR/USD', 'EURUSD=X', 'Euro / US Dollar', 'major', 'forex'),
    Pair('GBP/USD', 'GBPUSD=X', 'British Pound / US Dollar', 'major', 'forex'),
    Pair('USD/JPY', 'USDJPY=X', 'US Dollar / Japanese Yen', 'major', 'forex'),
    Pair('USD/CHF', 'USDCHF=X', 'US Dollar / Swiss Franc', 'major', 'forex'),
    Pair('AUD/USD', 'AUDUSD=X', 'Australian Dollar / US Dollar', 'major', 'forex'),
    Pair('USD/CAD', 'USDCAD=X', 'US Dollar / Canadian Dollar', 'major', 'forex'),
    Pair('NZD/USD', 'NZDUSD=X', 'New Zealand Dollar / US Dollar', 'major', 'forex'),
    # Cross
    Pair('EUR/GBP', 'EURGBP=X', 'Euro / British Pound', 'cross', 'forex'),
    Pair('EUR/JPY', 'EURJPY=X', 'Euro / Japanese Yen', 'cross', 'forex'),
    Pair('EUR/CHF', 'EURCHF=X', 'Euro / Swiss Franc', 'cross', 'forex'),
    Pair('GBP/JPY', 'GBPJPY=X', 'British Pound / Japanese Yen', 'cross', 'forex'),
    Pair('EUR/AUD', 'EURAUD=X', 'Euro / Australian Dollar', 'cross', 'forex'),
    Pair('GBP/AUD', 'GBPAUD=X', 'British Pound / Australian Dollar', 'cross', 'forex'),
    Pair('EUR/CAD', 'EURCAD=X', 'Euro / Canadian Dollar', 'cross', 'forex'),
    Pair('AUD/JPY', 'AUDJPY=X', 'Australian Dollar / Japanese Yen', 'cross', 'forex'),
    Pair('NZD/JPY', 'NZDJPY=X', 'New Zealand Dollar / Japanese Yen', 'cross', 'forex'),
    Pair('CHF/JPY', 'CHFJPY=X', 'Swiss Franc / Japanese Yen', 'cross', 'forex'),
    # Exotic
    Pair('USD/TRY', 'USDTRY=X', 'US Dollar / Turkish Lira', 'exotic', 'forex'),
    Pair('EUR/TRY', 'EURTRY=X', 'Euro / Turkish Lira', 'exotic', 'forex'),
    Pair('USD/ZAR', 'USDZAR=X', 'US Dollar / South African Rand', 'exotic', 'forex'),
    Pair('USD/MXN', 'USDMXN=X', 'US Dollar / Mexican Peso', 'exotic', 'forex'),
    Pair('USD/SGD', 'USDSGD=X', 'US Dollar / Singapore Dollar', 'exotic', 'forex'),
    Pair('USD/HKD', 'USDHKD=X', 'US Dollar / Hong Kong Dollar', 'exotic', 'forex'),
    Pair('USD/NOK', 'USDNOK=X', 'US Dollar / Norwegian Krone', 'exotic', 'forex'),
    Pair('USD/SEK', 'USDSEK=X', 'US Dollar / Swedish Krona', 'exotic', 'forex'),
    # Commodities
    Pair('XAU/USD', 'GC=F', 'Gold Futures', 'commodity', 'commodity'),
    Pair('XAG/USD', 'SI=F', 'Silver Futures', 'commodity', 'commodity'),
    # Crypto
    Pair('BTC/USD', 'BTC-USD', 'Bitcoin', 'crypto', 'crypto'),
    Pair('ETH/USD', 'ETH-USD', 'Ethereum', 'crypto', 'crypto'),
    Pair('SOL/USD', 'SOL-USD', 'Solana', 'crypto', 'crypto'),
    Pair('BNB/USD', 'BNB-USD', 'BNB', 'crypto', 'crypto'),
]

PAIR_BY_SYMBOL: dict[str, Pair] = {p.symbol: p for p in PAIRS}

MODE_PAIRS: dict[str, list[str]] = {
    'scalp': [
        'EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'AUD/USD', 'USD/CAD', 'NZD/USD',
        'EUR/JPY', 'GBP/JPY',
        'BTC/USD', 'ETH/USD',
    ],
    'intraday': [
        'EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'AUD/USD', 'USD/CAD', 'NZD/USD',
        'EUR/GBP', 'EUR/JPY', 'EUR/CHF', 'GBP/JPY', 'EUR/AUD', 'GBP/AUD',
        'XAU/USD',
        'BTC/USD', 'ETH/USD', 'SOL/USD',
    ],
    'swing': [p.symbol for p in PAIRS],
}

MODE_TF = {
    'scalp': ['1m', '5m', '15m'],
    'intraday': ['15m', '1h', '4h'],
    'swing': ['4h', '1d', '1wk'],
}

def get_pair(symbol: str) -> Optional[Pair]:
    s = symbol.upper().strip()
    if s in PAIR_BY_SYMBOL:
        return PAIR_BY_SYMBOL[s]
    alt = s.replace('/', '')
    for p in PAIRS:
        if p.symbol.replace('/', '') == alt:
            return p
    return None

def get_pairs_for_mode(mode: str) -> list[Pair]:
    symbols = MODE_PAIRS.get(mode, [])
    result = []
    for s in symbols:
        p = get_pair(s)
        if p:
            result.append(p)
    return result
