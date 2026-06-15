import pandas as pd
import numpy as np
from indicators import compute_indicators, INDICATOR_PARAMS

LAYER_WEIGHTS = {
    'scalp': {'trend': 2.0, 'momentum': 1.5, 'volatility': 1.0, 'volume': 0.5, 'pattern': 1.5},
    'intraday': {'trend': 2.0, 'momentum': 1.5, 'volatility': 1.0, 'volume': 1.0, 'pattern': 1.5},
    'swing': {'trend': 2.5, 'momentum': 1.5, 'volatility': 1.0, 'volume': 1.0, 'pattern': 1.5},
}

LAYER_MAX_ABS = {
    'trend': 3,
    'momentum': 2,
    'volatility': 2,
    'volume': 2,
    'pattern': 4,
}

def score_trend(ind: dict, mode: str) -> tuple[int, str]:
    score = 0
    reasons = []
    ma = ind.get('ma_alignment', 'mixed')

    if ma == 'bullish_aligned':
        score += 2
        reasons.append('EMA aligned bullish')
    elif ma == 'bearish_aligned':
        score -= 2
        reasons.append('EMA aligned bearish')
    elif ma == 'golden_cross_potential':
        score += 1
        reasons.append('EMA golden cross potential')
    elif ma == 'death_cross_potential':
        score -= 1
        reasons.append('EMA death cross potential')

    macd = ind.get('macd_cross', 'unknown')
    if macd == 'golden_cross':
        score += 1
        reasons.append('MACD golden cross')
    elif macd == 'death_cross':
        score -= 1
        reasons.append('MACD death cross')
    elif macd == 'bullish':
        score += 0.5
        reasons.append('MACD bullish')
    elif macd == 'bearish':
        score -= 0.5
        reasons.append('MACD bearish')

    divergence = ind.get('macd_divergence', 'none')
    if divergence == 'bullish_divergence':
        score += 1
        reasons.append('Bullish divergence')
    elif divergence == 'bearish_divergence':
        score -= 1
        reasons.append('Bearish divergence')

    ts = ind.get('trend_structure', {})
    struct = ts.get('structure', 'neutral')
    if struct == 'bullish':
        if score >= 0:
            score += 1
        else:
            score += 0.5
        reasons.append(f'HH/HL structure ({ts.get("hh_count", 0)}x)')
    elif struct == 'bearish':
        if score <= 0:
            score -= 1
        else:
            score -= 0.5
        reasons.append(f'LH/LL structure ({ts.get("lh_count", 0)}x)')

    adx = ind.get('adx', 0)
    if adx > 25:
        if score > 0:
            reasons.append(f'ADX {adx} (strong trend)')
        else:
            reasons.append(f'ADX {adx} (strong trend)')
    elif adx < 20:
        if score > 1:
            score -= 0.5
        elif score < -1:
            score += 0.5
        reasons.append(f'ADX {adx} (weak trend)')

    return max(-3, min(3, score)), ', '.join(reasons) if reasons else 'neutral'

def score_momentum(ind: dict, mode: str) -> tuple[int, str]:
    score = 0
    reasons = []
    rsi = ind.get('rsi', 50)

    if rsi >= 70:
        score -= 1
        reasons.append(f'RSI {rsi} (overbought)')
    elif rsi <= 30:
        score += 1
        reasons.append(f'RSI {rsi} (oversold)')
    elif 40 < rsi < 60:
        score += 0.5
        reasons.append(f'RSI {rsi} (neutral bullish)')
    elif rsi >= 60:
        score += 0.5
        reasons.append(f'RSI {rsi} (momentum bullish)')
    elif rsi <= 40:
        score -= 0.5
        reasons.append(f'RSI {rsi} (momentum bearish)')

    stoch = ind.get('stoch_k', 50)
    stoch_cross = ind.get('stoch_cross', 'unknown')
    if stoch < 20 and stoch_cross == 'bullish':
        score += 1
        reasons.append('Stoch oversold + bullish cross')
    elif stoch > 80 and stoch_cross == 'bearish':
        score -= 1
        reasons.append('Stoch overbought + bearish cross')

    wr = ind.get('williams_r', -50)
    if wr < -80:
        score += 0.5
        reasons.append(f'W%R {wr} (oversold)')
    elif wr > -20:
        score -= 0.5
        reasons.append(f'W%R {wr} (overbought)')

    return max(-2, min(2, score)), ', '.join(reasons) if reasons else 'neutral'

def _fmt(val, sig=4):
    """Format number with adaptive precision."""
    if val is None or val == 0:
        return '0'
    if abs(val) >= 100:
        return f'{val:.2f}'
    if abs(val) >= 1:
        return f'{val:.4f}'
    if abs(val) >= 0.01:
        return f'{val:.5f}'
    return f'{val:.6f}'

def score_volatility(ind: dict, mode: str) -> tuple[int, str]:
    score = 0
    reasons = []
    bb_pos = ind.get('bb_position', 0.5)
    bb_width = ind.get('bb_width', 0)

    if bb_pos > 0.8:
        score += 1
        reasons.append(f'Price near upper BB ({bb_pos})')
    elif bb_pos < 0.2:
        score -= 1
        reasons.append(f'Price near lower BB ({bb_pos})')
    elif 0.4 < bb_pos < 0.6:
        score += 0.5
        reasons.append(f'Price mid BB ({bb_pos})')

    if bb_width > 0:
        p = INDICATOR_PARAMS[mode]
        if bb_width > 0.05:
            score += 0.5
            reasons.append(f'BB expanding ({bb_width:.3f})')
        elif bb_width < 0.02:
            reasons.append(f'BB squeeze ({bb_width:.3f})')

    atr = ind.get('atr', 0)
    close = ind.get('close', 0)
    if close > 0 and atr / close > 0.01:
        score += 0.5
        reasons.append(f'High volatility (ATR {_fmt(atr)})')
    elif close > 0 and atr / close < 0.003:
        reasons.append(f'Low volatility (ATR {_fmt(atr)})')

    return max(-2, min(2, score)), ', '.join(reasons) if reasons else 'neutral'

def score_volume(ind: dict, mode: str) -> tuple[int, str]:
    score = 0
    reasons = []
    vr = ind.get('volume_ratio', 1.0)
    if vr > 1.5:
        score += 1
        reasons.append(f'Volume spike ({vr:.1f}x avg)')
    elif vr > 1.2:
        score += 0.5
        reasons.append(f'Volume above avg ({vr:.1f}x)')
    elif vr < 0.5:
        score -= 0.5
        reasons.append(f'Volume low ({vr:.1f}x avg)')

    mfi = ind.get('mfi', 50)
    if mfi:
        if mfi > 80:
            score -= 0.5
            reasons.append(f'MFI {mfi} (overbought)')
        elif mfi < 20:
            score += 0.5
            reasons.append(f'MFI {mfi} (oversold)')
        elif mfi > 60:
            score += 0.5
            reasons.append(f'MFI {mfi} (volume bullish)')
        elif mfi < 40:
            score -= 0.5
            reasons.append(f'MFI {mfi} (volume bearish)')

    obv = ind.get('obv_trend', 'flat')
    if obv == 'rising':
        score += 0.5
        reasons.append('OBV rising (confirmation)')
    elif obv == 'falling':
        score -= 0.5
        reasons.append('OBV falling (divergence risk)')

    return max(-2, min(2, score)), ', '.join(reasons) if reasons else 'neutral'

def score_pattern(ind: dict, mode: str) -> tuple[int, str]:
    score = 0
    reasons = []
    pat = ind.get('pattern', 'none')

    bullish_patterns = ['bullish_engulfing', 'hammer', 'morning_star', 'marubozu_bullish']
    bearish_patterns = ['bearish_engulfing', 'shooting_star', 'evening_star', 'marubozu_bearish']
    reversal_patterns = ['bullish_engulfing', 'bearish_engulfing', 'hammer', 'shooting_star', 'morning_star', 'evening_star']
    rejection_patterns = ['hammer', 'shooting_star', 'doji']

    close = ind.get('close', 0)
    s1 = ind.get('support_1', 0)
    r1 = ind.get('resistance_1', 0)
    at_support = s1 and close and abs(close - s1) / close < 0.005
    at_resistance = r1 and close and abs(r1 - close) / close < 0.005

    if pat in bullish_patterns:
        is_engulfing = pat == 'bullish_engulfing'
        is_rejection = pat in rejection_patterns and pat != 'doji'
        base = 3 if is_engulfing else 2 if is_rejection else 2
        score += base
        reasons.append(f'Pattern: {pat}' + (' (engulfing)' if is_engulfing else ''))
        if at_support:
            score += 2
            reasons.append('Bullish reversal at support')
    elif pat in bearish_patterns:
        is_engulfing = pat == 'bearish_engulfing'
        is_rejection = pat in rejection_patterns and pat != 'doji'
        base = -3 if is_engulfing else -2 if is_rejection else -2
        score += base
        reasons.append(f'Pattern: {pat}' + (' (engulfing)' if is_engulfing else ''))
        if at_resistance:
            score -= 2
            reasons.append('Bearish reversal at resistance')
    elif pat == 'doji':
        score += 0.5
        reasons.append('Pattern: doji (indecision)')

    if at_support and pat not in bullish_patterns:
        score += 1
        reasons.append('Price at support')
    if at_resistance and pat not in bearish_patterns:
        score -= 1
        reasons.append('Price at resistance')

    sd = ind.get('supply_demand', [])
    for zone in sd:
        ztype = zone.get('type', '')
        zlow = zone.get('zone_low', 0)
        zhigh = zone.get('zone_high', 0)
        strength = zone.get('strength', 1)
        if ztype == 'demand' and zlow <= close <= zhigh * 1.01:
            bonus = 1 + (strength - 1) * 0.5
            score += bonus
            reasons.append(f'Demand zone (strength {strength})')
        elif ztype == 'supply' and zhigh >= close >= zlow * 0.99:
            bonus = 1 + (strength - 1) * 0.5
            score -= bonus
            reasons.append(f'Supply zone (strength {strength})')

    fvg_list = ind.get('fvg', [])
    for fvg in fvg_list:
        ft = fvg.get('type', '')
        gh = fvg.get('gap_high', 0)
        gl = fvg.get('gap_low', 0)
        if ft == 'bullish_fvg' and gl <= close <= gh:
            score += 1
            reasons.append('FVG imbalance (bullish gap)')
        elif ft == 'bearish_fvg' and gl <= close <= gh:
            score -= 1
            reasons.append('FVG imbalance (bearish gap)')

    return max(-4, min(4, score)), ', '.join(reasons) if reasons else 'neutral'

def calculate_confluence(ind: dict, mode: str) -> dict:
    layers = {
        'trend': score_trend(ind, mode),
        'momentum': score_momentum(ind, mode),
        'volatility': score_volatility(ind, mode),
        'volume': score_volume(ind, mode),
        'pattern': score_pattern(ind, mode),
    }

    weights = LAYER_WEIGHTS[mode]
    total_weighted = 0
    total_weight = 0
    breakdown = {}

    for layer, (raw_score, reason) in layers.items():
        w = weights[layer]
        weighted = raw_score * w
        total_weighted += weighted
        total_weight += w
        breakdown[layer] = {
            'score': raw_score,
            'weight': w,
            'weighted': round(weighted, 2),
            'reason': reason,
        }

    max_possible = sum(LAYER_MAX_ABS[l] * weights[l] for l in layers)
    raw_conf = total_weighted / max_possible if max_possible > 0 else 0
    confidence = round((raw_conf + 1) / 2 * 10, 1)
    confidence = max(0, min(10, confidence))

    if confidence >= 7:
        signal = 'strong_buy' if total_weighted > 0 else 'strong_sell'
    elif confidence >= 5:
        signal = 'buy' if total_weighted > 0 else 'sell'
    elif confidence >= 3:
        signal = 'weak_buy' if total_weighted > 0 else 'weak_sell'
    else:
        signal = 'neutral'

    net_score = round(total_weighted, 2)

    return {
        'signal': signal,
        'confidence': confidence,
        'net_score': net_score,
        'breakdown': breakdown,
        'total_weighted': total_weighted,
    }

def calculate_sl_tp(ind: dict, mode: str, signal: str) -> dict:
    atr = ind.get('atr', 0)
    close = ind.get('close', 0)
    if atr == 0 or close == 0:
        return {'error': 'no_data'}

    if mode == 'scalp':
        sl_mult = 1.0
        tp1_mult = 1.5
        tp2_mult = 2.5
        min_rr = 1.5
    elif mode == 'intraday':
        sl_mult = 1.5
        tp1_mult = 3.0
        tp2_mult = 4.5
        min_rr = 2.0
    else:
        sl_mult = 2.0
        tp1_mult = 6.0
        tp2_mult = 8.0
        min_rr = 3.0

    is_buy = signal in ('strong_buy', 'buy', 'weak_buy')
    sl = round(close - (atr * sl_mult) if is_buy else close + (atr * sl_mult), 5)
    tp1 = round(close + (atr * tp1_mult) if is_buy else close - (atr * tp1_mult), 5)
    tp2 = round(close + (atr * tp2_mult) if is_buy else close - (atr * tp2_mult), 5)

    sl_pips = round(abs(close - sl), 5)
    tp1_pips = round(abs(tp1 - close), 5)
    rr1 = round(tp1_pips / sl_pips, 2) if sl_pips > 0 else 0
    rr2 = round(tp2_pips / sl_pips, 2) if sl_pips and (tp2_pips := round(abs(tp2 - close), 5)) > 0 else 0

    rr_ok = rr1 >= min_rr - 0.02

    return {
        'entry_zone_high': round(close * 1.0002 if is_buy else close * 0.9998, 5),
        'entry_zone_low': round(close * 0.9998 if is_buy else close * 1.0002, 5),
        'sl': sl,
        'tp1': tp1,
        'tp2': tp2,
        'sl_pips': sl_pips,
        'tp1_pips': tp1_pips,
        'rr1': rr1,
        'rr2': rr2,
        'min_rr': min_rr,
        'rr_ok': rr_ok,
        'atr_used': atr,
    }

def validate_trading_plan(ind: dict, mode: str, higher_tf_signal: str = None, entry_ma: str = None) -> dict:
    conditions = {}

    ma = ind.get('ma_alignment', 'mixed')
    close = ind.get('close', 0)
    ma_fast = ind.get('ma_fast', 0)
    ma_medium = ind.get('ma_medium', 0)

    cond1_pass = ma == 'bullish_aligned'
    conditions['ema_alignment'] = {
        'pass': cond1_pass,
        'detail': f'EMA{INDICATOR_PARAMS[mode]["ma_fast"]} ({ma_fast:.5f}) > EMA{INDICATOR_PARAMS[mode]["ma_medium"]} ({ma_medium:.5f})' if cond1_pass else f'Not bullish aligned ({ma})',
    }

    rsi = ind.get('rsi', 50)
    cond2_pass = 30 <= rsi <= 70
    conditions['rsi_range'] = {
        'pass': cond2_pass,
        'detail': f'RSI {rsi} ({ "valid" if cond2_pass else "OUT OF" } 30-70 range)',
    }

    pat = ind.get('pattern', 'none')
    bullish_patterns = ['bullish_engulfing', 'hammer', 'morning_star', 'marubozu_bullish']
    bearish_patterns = ['bearish_engulfing', 'shooting_star', 'evening_star', 'marubozu_bearish']
    s1 = ind.get('support_1', 0)
    at_support = s1 and close and abs(close - s1) / close < 0.005
    r1 = ind.get('resistance_1', 0)
    at_resistance = r1 and close and abs(r1 - close) / close < 0.005

    reversal_at_level = (pat in bullish_patterns and at_support) or (pat in bearish_patterns and at_resistance)
    conditions['reversal_at_level'] = {
        'pass': reversal_at_level,
        'detail': f'Pattern {pat}' + (' at support' if at_support and pat in bullish_patterns else ' at resistance' if at_resistance and pat in bearish_patterns else ' (not at level)' if pat in bullish_patterns + bearish_patterns else ' (no reversal)'),
    }

    cond4_pass = higher_tf_signal is None or 'neutral' in higher_tf_signal or False
    if higher_tf_signal:
        h_bull = 'bull' in higher_tf_signal or 'buy' in higher_tf_signal
        if entry_ma:
            e_bull = 'bullish' in entry_ma or 'buy' in entry_ma
            cond4_pass = h_bull == e_bull
        else:
            cond4_pass = False
    tf_name = {'scalp': 'M15', 'intraday': 'H4', 'swing': 'D1'}.get(mode, 'higher TF')
    conditions['higher_tf_aligned'] = {
        'pass': cond4_pass,
        'detail': f'{tf_name} aligned' if cond4_pass else f'{tf_name} NOT aligned / unknown',
    }

    atr = ind.get('atr', 0)
    sl_mult = {'scalp': 1.0, 'intraday': 1.5, 'swing': 2.0}.get(mode, 1.5)
    sl = atr * sl_mult
    max_sl = atr * 2.0
    cond5_pass = sl <= max_sl
    conditions['sl_atr'] = {
        'pass': cond5_pass,
        'detail': f'SL {sl_mult}×ATR ({sl:.5f}) ≤ 2×ATR ({max_sl:.5f})',
    }

    pass_count = sum(1 for c in conditions.values() if c['pass'])
    fail_count = len(conditions) - pass_count
    overall = pass_count == len(conditions)

    return {
        'conditions': conditions,
        'pass_count': pass_count,
        'fail_count': fail_count,
        'overall': overall,
        'score': f'{pass_count}/{len(conditions)}',
    }

def full_analysis(df: pd.DataFrame, mode: str, symbol: str) -> dict:
    ind = compute_indicators(df, mode)
    if 'error' in ind:
        return {'error': ind['error']}

    confluence = calculate_confluence(ind, mode)
    sl_tp = calculate_sl_tp(ind, mode, confluence['signal'])

    if 'error' not in sl_tp and not sl_tp.get('rr_ok', True):
        confluence['confidence'] = round(confluence['confidence'] * 0.7, 1)
        if confluence['confidence'] < 5:
            confluence['signal'] = 'neutral'
        confluence['rr_downgraded'] = True
        confluence['rr_reason'] = f'RR {sl_tp["rr1"]}:1 below minimum {sl_tp["min_rr"]}:1'
    else:
        confluence['rr_downgraded'] = False

    return {
        'symbol': symbol,
        'mode': mode,
        'price': ind.get('close', 0),
        'high': ind.get('high', 0),
        'low': ind.get('low', 0),
        'volume': ind.get('volume', 0),
        'indicators': {
            'rsi': ind.get('rsi'),
            'macd': round(ind.get('macd_line', 0), 5),
            'macd_signal': ind.get('macd_signal'),
            'macd_histogram': ind.get('macd_histogram'),
            'macd_cross': ind.get('macd_cross'),
            'divergence': ind.get('macd_divergence'),
            'ma_fast': ind.get('ma_fast'),
            'ma_medium': ind.get('ma_medium'),
            'ma_slow': ind.get('ma_slow'),
            'ma_alignment': ind.get('ma_alignment'),
            'bb_upper': ind.get('bb_upper'),
            'bb_middle': ind.get('bb_middle'),
            'bb_lower': ind.get('bb_lower'),
            'bb_position': ind.get('bb_position'),
            'atr': ind.get('atr'),
            'adx': ind.get('adx'),
            'stoch_k': ind.get('stoch_k'),
            'stoch_d': ind.get('stoch_d'),
            'stoch_cross': ind.get('stoch_cross'),
            'williams_r': ind.get('williams_r'),
            'cci': ind.get('cci'),
            'mfi': ind.get('mfi'),
            'volume_ratio': ind.get('volume_ratio'),
            'obv': ind.get('obv'),
            'obv_trend': ind.get('obv_trend'),
            'pattern': ind.get('pattern'),
            'trend_structure': ind.get('trend_structure'),
            'supply_demand': ind.get('supply_demand'),
            'fvg': ind.get('fvg'),
        },
        'support_resistance': {
            'support_1': ind.get('support_1'),
            'resistance_1': ind.get('resistance_1'),
            'pivot': ind.get('pivot'),
            's1': ind.get('s1'),
            'r1': ind.get('r1'),
        },
        'confluence': confluence,
        'execution': sl_tp,
    }
