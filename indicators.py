import pandas as pd
import numpy as np
import ta

INDICATOR_PARAMS = {
    'scalp': {
        'rsi_period': 7,
        'ma_fast': 10,
        'ma_medium': 20,
        'ma_slow': 50,
        'bb_period': 20,
        'bb_std': 1.5,
        'atr_period': 5,
        'adx_period': 7,
        'stoch_k': 7,
        'stoch_d': 3,
        'stoch_smooth': 3,
        'mfi_period': 7,
        'williams_period': 7,
        'cci_period': 10,
    },
    'intraday': {
        'rsi_period': 14,
        'ma_fast': 20,
        'ma_medium': 50,
        'ma_slow': 100,
        'bb_period': 20,
        'bb_std': 2.0,
        'atr_period': 14,
        'adx_period': 14,
        'stoch_k': 14,
        'stoch_d': 3,
        'stoch_smooth': 3,
        'mfi_period': 14,
        'williams_period': 14,
        'cci_period': 20,
    },
    'swing': {
        'rsi_period': 14,
        'ma_fast': 20,
        'ma_medium': 50,
        'ma_slow': 200,
        'bb_period': 20,
        'bb_std': 2.0,
        'atr_period': 14,
        'adx_period': 14,
        'stoch_k': 21,
        'stoch_d': 5,
        'stoch_smooth': 5,
        'mfi_period': 14,
        'williams_period': 14,
        'cci_period': 20,
    },
}

def compute_indicators(df: pd.DataFrame, mode: str) -> dict:
    p = INDICATOR_PARAMS[mode]
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    volume = df['volume'].values if 'volume' in df.columns else None

    s_close = pd.Series(close)
    s_high = pd.Series(high)
    s_low = pd.Series(low)
    s_vol = pd.Series(volume) if volume is not None else None

    result = {}
    result['close'] = float(close[-1]) if len(close) > 0 else 0
    result['high'] = float(high[-1]) if len(high) > 0 else 0
    result['low'] = float(low[-1]) if len(low) > 0 else 0
    result['volume'] = float(volume[-1]) if volume is not None else 0

    len_req = max(p['rsi_period'], p['ma_slow'], p['bb_period'], p['atr_period'], p['adx_period'])
    if len(close) < len_req + 5:
        result['error'] = f'Not enough data ({len(close)} bars, need {len_req + 5})'
        return result

    rsi_series = ta.momentum.RSIIndicator(s_close, window=p['rsi_period']).rsi()
    result['rsi'] = round(float(rsi_series.dropna().iloc[-1]), 2) if not rsi_series.dropna().empty else 50.0

    macd = ta.trend.MACD(s_close, window_slow=26, window_fast=12, window_sign=9)
    macd_line = macd.macd()
    macd_signal = macd.macd_signal()
    macd_hist = macd.macd_diff()
    result['macd_line'] = round(float(macd_line.dropna().iloc[-1]), 5) if not macd_line.dropna().empty else 0
    result['macd_signal'] = round(float(macd_signal.dropna().iloc[-1]), 5) if not macd_signal.dropna().empty else 0
    result['macd_histogram'] = round(float(macd_hist.dropna().iloc[-1]), 5) if not macd_hist.dropna().empty else 0
    result['macd_cross'] = _macd_cross(macd_line, macd_signal)
    result['macd_divergence'] = _divergence(close, macd_line.dropna().values if not macd_line.dropna().empty else None)

    ma_fast_series = ta.trend.EMAIndicator(s_close, window=p['ma_fast']).ema_indicator()
    ma_medium_series = ta.trend.EMAIndicator(s_close, window=p['ma_medium']).ema_indicator()
    ma_slow_series = ta.trend.EMAIndicator(s_close, window=p['ma_slow']).ema_indicator()
    result['ma_fast'] = round(float(ma_fast_series.dropna().iloc[-1]), 5) if not ma_fast_series.dropna().empty else 0
    result['ma_medium'] = round(float(ma_medium_series.dropna().iloc[-1]), 5) if not ma_medium_series.dropna().empty else 0
    result['ma_slow'] = round(float(ma_slow_series.dropna().iloc[-1]), 5) if not ma_slow_series.dropna().empty else 0
    result['ma_alignment'] = _ma_alignment(result['ma_fast'], result['ma_medium'], result['ma_slow'], result['close'])

    bb = ta.volatility.BollingerBands(s_close, window=p['bb_period'], window_dev=p['bb_std'])
    result['bb_upper'] = round(float(bb.bollinger_hband().dropna().iloc[-1]), 5) if not bb.bollinger_hband().dropna().empty else 0
    result['bb_middle'] = round(float(bb.bollinger_mavg().dropna().iloc[-1]), 5) if not bb.bollinger_mavg().dropna().empty else 0
    result['bb_lower'] = round(float(bb.bollinger_lband().dropna().iloc[-1]), 5) if not bb.bollinger_lband().dropna().empty else 0
    result['bb_width'] = round((result['bb_upper'] - result['bb_lower']) / result['bb_middle'], 4) if result['bb_middle'] else 0
    result['bb_position'] = _bb_position(result['close'], result['bb_lower'], result['bb_upper'])

    atr_series = ta.volatility.AverageTrueRange(s_high, s_low, s_close, window=p['atr_period']).average_true_range()
    result['atr'] = round(float(atr_series.dropna().iloc[-1]), 5) if not atr_series.dropna().empty else 0

    stoch = ta.momentum.StochasticOscillator(s_high, s_low, s_close, window=p['stoch_k'], smooth_window=p['stoch_smooth'])
    result['stoch_k'] = round(float(stoch.stoch().dropna().iloc[-1]), 2) if not stoch.stoch().dropna().empty else 50
    result['stoch_d'] = round(float(stoch.stoch_signal().dropna().iloc[-1]), 2) if not stoch.stoch_signal().dropna().empty else 50
    result['stoch_cross'] = _cross(result.get('stoch_k', 50), result.get('stoch_d', 50))

    adx_series = ta.trend.ADXIndicator(s_high, s_low, s_close, window=p['adx_period']).adx()
    result['adx'] = round(float(adx_series.dropna().iloc[-1]), 2) if not adx_series.dropna().empty else 0

    willy = ta.momentum.WilliamsRIndicator(s_high, s_low, s_close, lbp=p['williams_period']).williams_r()
    result['williams_r'] = round(float(willy.dropna().iloc[-1]), 2) if not willy.dropna().empty else -50

    cci_series = ta.trend.CCIIndicator(s_high, s_low, s_close, window=p['cci_period']).cci()
    result['cci'] = round(float(cci_series.dropna().iloc[-1]), 2) if not cci_series.dropna().empty else 0

    if s_vol is not None:
        mfi_series = ta.volume.MFIIndicator(s_high, s_low, s_close, s_vol, window=p['mfi_period']).money_flow_index()
        result['mfi'] = round(float(mfi_series.dropna().iloc[-1]), 2) if not mfi_series.dropna().empty else 50

        obv_series = ta.volume.OnBalanceVolumeIndicator(s_close, s_vol).on_balance_volume()
        result['obv'] = float(obv_series.dropna().iloc[-1]) if not obv_series.dropna().empty else 0
        result['obv_trend'] = _obv_trend(obv_series.dropna().values if not obv_series.dropna().empty else None)

    vol_sma_series = ta.trend.SMAIndicator(pd.Series(volume) if volume is not None else pd.Series([0]), window=20).sma_indicator()
    result['volume_ratio'] = round(result['volume'] / float(vol_sma_series.dropna().iloc[-1]), 2) if not vol_sma_series.dropna().empty and float(vol_sma_series.dropna().iloc[-1]) > 0 else 1.0

    hi_idx = _swing_high(low, high, 5)
    lo_idx = _swing_low(low, high, 5)
    if low is not None and len(low) > 0:
        recent_lows = [low[i] for i in lo_idx if i >= len(low) - 20]
        recent_highs = [high[i] for i in hi_idx if i >= len(high) - 20]
    else:
        recent_lows, recent_highs = [], []
    result['support_1'] = float(max(recent_lows[-3:])) if len(recent_lows) >= 3 else float(low[-10:].min() if len(low) >= 10 else low[-1])
    result['resistance_1'] = float(min(recent_highs[-3:])) if len(recent_highs) >= 3 else float(high[-10:].max() if len(high) >= 10 else high[-1])

    pivot = (float(high[-1]) + float(low[-1]) + result['close']) / 3 if len(high) > 0 and len(low) > 0 else result['close']
    result['pivot'] = round(pivot, 5)
    result['r1'] = round(2 * pivot - (float(low[-1]) if len(low) > 0 else 0), 5)
    result['s1'] = round(2 * pivot - (float(high[-1]) if len(high) > 0 else 0), 5)

    result['trend_structure'] = _detect_trend_structure(high, low, close)

    return result

def _ma_alignment(ma_fast, ma_medium, ma_slow, close):
    if ma_fast == 0 or ma_medium == 0 or ma_slow == 0:
        return 'unknown'
    if close > ma_fast > ma_medium > ma_slow:
        return 'bullish_aligned'
    if close < ma_fast < ma_medium < ma_slow:
        return 'bearish_aligned'
    if close > ma_fast and ma_fast < ma_medium:
        return 'golden_cross_potential'
    if close < ma_fast and ma_fast > ma_medium:
        return 'death_cross_potential'
    return 'mixed'

def _macd_cross(macd_line, macd_signal):
    ml = macd_line.dropna()
    ms = macd_signal.dropna()
    if len(ml) < 2 or len(ms) < 2:
        return 'unknown'
    if ml.iloc[-1] > ms.iloc[-1] and ml.iloc[-2] <= ms.iloc[-2]:
        return 'golden_cross'
    if ml.iloc[-1] < ms.iloc[-1] and ml.iloc[-2] >= ms.iloc[-2]:
        return 'death_cross'
    if ml.iloc[-1] > ms.iloc[-1]:
        return 'bullish'
    return 'bearish'

def _cross(k, d):
    if abs(k - d) < 0.5:
        return 'crossing'
    if k > d:
        return 'bullish'
    return 'bearish'

def _bb_position(close, lower, upper):
    if upper == lower:
        return 0.5
    return round((close - lower) / (upper - lower), 2)

def _divergence(prices, macd_vals):
    if macd_vals is None or len(macd_vals) < 10:
        return 'none'
    p = prices[-10:]
    m = macd_vals[-10:]
    price_lower = p[-1] < p[0] and p[-1] < min(p) * 0.999
    macd_higher = m[-1] > m[0] and m[-1] > max(m) * 0.999
    if price_lower and macd_higher:
        return 'bullish_divergence'
    price_higher = p[-1] > p[0] and p[-1] > max(p) * 0.999
    macd_lower = m[-1] < m[0] and m[-1] < min(m) * 0.999
    if price_higher and macd_lower:
        return 'bearish_divergence'
    return 'none'

def _obv_trend(obv_vals):
    if obv_vals is None or len(obv_vals) < 5:
        return 'flat'
    recent = obv_vals[-5:]
    if recent[-1] > recent[0] * 1.001:
        return 'rising'
    if recent[-1] < recent[0] * 0.999:
        return 'falling'
    return 'flat'

def _swing_high(low, high, window=5):
    idx = []
    if low is None or high is None or len(low) < window * 2 + 1:
        return idx
    for i in range(window, len(low) - window):
        if high[i] == max(high[i - window:i + window + 1]):
            idx.append(i)
    return idx

def _swing_low(low, high, window=5):
    idx = []
    if low is None or high is None or len(low) < window * 2 + 1:
        return idx
    for i in range(window, len(low) - window):
        if low[i] == min(low[i - window:i + window + 1]):
            idx.append(i)
    return idx


def _detect_trend_structure(high, low, close, lookback=20):
    """Detect market structure via swing point majority voting.

    Uses window=3 for swing detection (sensitive, captures micro-structure).
    Counts HH/HL vs LH/LL within lookback, requires >=60% majority + >=2 bullish/bearish counts.
    """
    result = {'structure': 'neutral', 'hh_count': 0, 'lh_count': 0, 'direction': 0}
    if len(close) < lookback + 3:
        return result

    swh = _swing_high(low, high, 3)
    swl = _swing_low(low, high, 3)

    recent_h = [float(high[i]) for i in swh if i >= len(close) - lookback]
    recent_l = [float(low[i]) for i in swl if i >= len(close) - lookback]

    if len(recent_h) < 3 and len(recent_l) < 3:
        return result

    hh = sum(1 for i in range(1, len(recent_h)) if recent_h[i] > recent_h[i-1])
    hl = sum(1 for i in range(1, len(recent_l)) if recent_l[i] > recent_l[i-1])
    lh = sum(1 for i in range(1, len(recent_h)) if recent_h[i] < recent_h[i-1])
    ll = sum(1 for i in range(1, len(recent_l)) if recent_l[i] < recent_l[i-1])
    total = max(len(recent_h) - 1, 1) + max(len(recent_l) - 1, 1)

    bullish = hh + hl
    bearish = lh + ll
    majority = max(bullish, bearish) / total if total > 0 else 0

    if bullish > bearish and majority >= 0.6 and bullish >= 2:
        result['structure'] = 'bullish'
        result['hh_count'] = hh
        result['lh_count'] = lh
        result['direction'] = 1
    elif bearish > bullish and majority >= 0.6 and bearish >= 2:
        result['structure'] = 'bearish'
        result['hh_count'] = hh
        result['lh_count'] = lh
        result['direction'] = -1

    return result



