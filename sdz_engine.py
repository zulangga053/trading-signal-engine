"""
SDZ-Price Action Engine v1.0
Supply & Demand Zone Detection with Engulfing-Momentum Confluence
Independent module — runs on H1 bar close.
"""
import json
import os
import time
import numpy as np
from collections import deque

WILDER_PERIOD = 14
LOOKBACK_BARS = 50
MIN_IMPULSE_RATIO = 2.0
ENGULFING_BODY_RATIO = 1.2
ZONE_WIDTH_MAX = 3.0
PROXIMITY_MERGE = 1.0
ENTRY_PROXIMITY = 0.2
RETRACEMENT_TOLERANCE = 0.382
VOL_EXPANSION_THRESHOLD = 1.3
VOL_ENTRY_THRESHOLD = 1.2
EXPIRE_ATR_MULTIPLE = 2.0
MAX_ZONE_AGE = 15
MAX_ZONES_PER_TYPE = 50
MAX_LOGS = 1000
STATE_DIR = os.path.expanduser('~/.trading-signal-engine/sdz')
STATE_EXPIRE_SEC = 86400  # 24h — discard stale state

_SPREAD_BUFFER = {
    'forex': 0.0002,
    'crypto': 0.001,
    'commodity': 0.5,
}


def _spread(symbol: str) -> float:
    sym = symbol.upper()
    if any(x in sym for x in ('BTC', 'ETH')):
        return _SPREAD_BUFFER['crypto']
    if any(x in sym for x in ('XAU', 'XAG')):
        return _SPREAD_BUFFER['commodity']
    return _SPREAD_BUFFER['forex']


def _wilder_atr(high, low, close):
    """Wilder's smoothed ATR (ATR = (prev_ATR * 13 + TR) / 14)."""
    tr = np.maximum(
        high - low,
        np.maximum(
            np.abs(high - np.roll(close, 1)),
            np.abs(low - np.roll(close, 1)),
        ),
    )
    tr[0] = high[0] - low[0]
    if len(tr) < 2:
        return float(tr[-1])
    atr = float(np.mean(tr[1:WILDER_PERIOD + 1]))
    for i in range(WILDER_PERIOD + 1, len(tr)):
        atr = (atr * (WILDER_PERIOD - 1) + tr[i]) / WILDER_PERIOD
    return atr


class SDZEngine:
    """Supply & Demand Zone Engine — stateful per symbol."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.spread = _spread(symbol)
        self.zones = {'supply': [], 'demand': []}
        self.logs = deque(maxlen=MAX_LOGS)
        self.regime = {'trend': 'RANGE_BOUND', 'slope': 0.0}
        self.atr_wilder = 0.0
        self.vol_sma20 = 0.0
        self._last_price = 0.0
        self._bar_count = 0
        self._triggers = []

    def update(self, df) -> dict:
        """Process one new bar close. Returns SDZ result dict."""
        n = len(df)
        if n < 30:
            return {'status': 'insufficient_data',
                'zones': {'supply': [], 'demand': []},
                'triggers': [], 'regime': self.regime,
                'total_zones': 0, 'atr': self.atr_wilder,
                'sdl_active': False, 'sdl_trigger': None, 'sdl_reason': ''}

        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        open_ = df['open'].values.astype(float)
        volume = df['volume'].values.astype(float) if 'volume' in df.columns else None

        self._last_price = float(close[-1])
        self._bar_count += 1

        self.atr_wilder = _wilder_atr(high, low, close)
        if volume is not None:
            self.vol_sma20 = float(np.mean(volume[-20:])) if len(volume) >= 20 else float(np.mean(volume))

        sdl = self._sdl_fallback_check(df)

        if self.atr_wilder <= 0 or self._bar_count < 2:
            result = {
                'status': 'warming_up',
                'zones': {'supply': [], 'demand': []},
                'triggers': [], 'regime': self.regime,
                'total_zones': 0, 'atr': self.atr_wilder,
                'sdl_active': sdl.get('active', False),
                'sdl_trigger': sdl.get('trigger'),
                'sdl_reason': sdl.get('reason', ''),
            }
            self.save_state()
            return result

        lookback = min(LOOKBACK_BARS, n - 2)
        df_slice = df.iloc[-lookback - 5:].copy()
        new_zones = self._detect_engulfing(df_slice)
        self._hierarchy(new_zones)
        self.regime = self._market_regime(close)
        self._expire_zones()
        self._triggers = self._check_triggers(df)

        result = {
            'status': 'active',
            'zones': {
                'supply': [{k: float(v) if isinstance(v, (float, np.floating)) else v for k, v in z.items()}
                          for z in self.zones['supply'][:10]],
                'demand': [{k: float(v) if isinstance(v, (float, np.floating)) else v for k, v in z.items()}
                          for z in self.zones['demand'][:10]],
            },
            'triggers': self._triggers,
            'regime': self.regime,
            'atr': self.atr_wilder,
            'total_zones': len(self.zones['supply']) + len(self.zones['demand']),
            'sdl_active': sdl.get('active', False),
            'sdl_trigger': sdl.get('trigger'),
            'sdl_reason': sdl.get('reason', ''),
        }

        self.save_state()
        return result

    def _detect_engulfing(self, df) -> list:
        """§II — Base Zone Identification from engulfing patterns."""
        close = df['close'].values.astype(float)
        open_ = df['open'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        n = len(df)
        zones = []

        for i in range(1, n - 1):
            c, o, h, l = close[i], open_[i], high[i], low[i]
            pc, po = close[i - 1], open_[i - 1]
            body = abs(c - o)
            pbody = abs(pc - po)
            rng = h - l

            if body <= 0 or pbody <= 0:
                continue

            if rng < self.atr_wilder * 0.8:
                continue

            if body < pbody * ENGULFING_BODY_RATIO:
                continue

            # §II.A — Bearish Engulfing
            if (c < o and pc > po and o >= pc and c <= po):
                zones.append({'type': 'bearish_engulfing', 'idx': i,
                              'high': float(h), 'low': float(l),
                              'open': float(o), 'close': float(c)})

            # §II.B — Bullish Engulfing
            elif (c > o and pc < po and o <= pc and c >= po):
                zones.append({'type': 'bullish_engulfing', 'idx': i,
                              'high': float(h), 'low': float(l),
                              'open': float(o), 'close': float(c)})

        return self._validate_momentum(df, zones)

    def _validate_momentum(self, df, engulfing_list) -> list:
        """§III — Momentum Impulsive Validation.

        Scan j ∈ [i+1, i+5] for:
          - For supply: drop ≥ 2×ATR, candle bearish, retrace < 38.2%, vol > 1.3×SMA20
          - For demand: rally ≥ 2×ATR, candle bullish, retrace < 38.2%, vol > 1.3×SMA20
        """
        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        open_ = df['open'].values.astype(float)
        volume = df['volume'].values.astype(float) if 'volume' in df.columns else None
        n = len(df)

        valid = []
        for eg in engulfing_list:
            i = eg['idx']
            if i + 1 >= n:
                continue

            scan_end = min(i + 6, n)
            max_move = 0.0
            max_retrace = 0.0
            vol_ok = False
            dir_ok = False
            best_j = None

            for j in range(i + 1, scan_end):
                if eg['type'] == 'bearish_engulfing':
                    move = (eg['close'] - low[j]) / self.atr_wilder
                    retrace_pct = (high[j] - eg['close']) / (max(abs(eg['close'] - low[j]), 0.0001))
                    if close[j] < open_[j]:
                        dir_ok = True
                else:
                    move = (high[j] - eg['close']) / self.atr_wilder
                    retrace_pct = (eg['close'] - low[j]) / (max(abs(high[j] - eg['close']), 0.0001))
                    if close[j] > open_[j]:
                        dir_ok = True

                if move > max_move:
                    max_move = move
                    best_j = j
                if retrace_pct > max_retrace:
                    max_retrace = retrace_pct

                if volume is not None and self.vol_sma20 > 0 and volume[j] > self.vol_sma20 * VOL_EXPANSION_THRESHOLD:
                    vol_ok = True

            if max_move >= MIN_IMPULSE_RATIO and max_retrace < RETRACEMENT_TOLERANCE and dir_ok:
                ztype = 'supply' if eg['type'] == 'bearish_engulfing' else 'demand'
                valid.append({
                    'type': ztype,
                    'zone_high': float(eg['high']),
                    'zone_low': float(eg['low']),
                    'momentum': round(max_move, 2),
                    'idx': i,
                    'age': 0,
                    'confirmed_by_idx': best_j,
                })

        return valid

    def _hierarchy(self, new_zones):
        """§IV — Zone Hierarchy & Management.

        - Width > 3×ATR → invalidate
        - Overlap < 1×ATR → retain strongest momentum
        - Enforce MAX_ZONES_PER_TYPE buffer
        """
        for z in new_zones:
            ztype = z['type']
            width = z['zone_high'] - z['zone_low']
            if width > ZONE_WIDTH_MAX * self.atr_wilder:
                continue

            dup = False
            for existing in self.zones[ztype]:
                mid_e = (existing['zone_high'] + existing['zone_low']) / 2
                mid_z = (z['zone_high'] + z['zone_low']) / 2
                if abs(mid_e - mid_z) < PROXIMITY_MERGE * self.atr_wilder:
                    dup = True
                    if z['momentum'] > existing['momentum']:
                        existing.update(z)
                    break

            if not dup:
                self.zones[ztype].append(z)

    def _should_expire(self, zone, price) -> bool:
        zone_mid = (zone['zone_high'] + zone['zone_low']) / 2
        dist = abs(price - zone_mid)
        if dist > EXPIRE_ATR_MULTIPLE * self.atr_wilder:
            return True
        zone['age'] = zone.get('age', 0) + 1
        if zone['age'] > MAX_ZONE_AGE:
            return True
        return False

    def _expire_zones(self):
        for ztype in ['supply', 'demand']:
            self.zones[ztype] = [z for z in self.zones[ztype]
                                 if not self._should_expire(z, self._last_price)]
            if len(self.zones[ztype]) > MAX_ZONES_PER_TYPE:
                self.zones[ztype].sort(key=lambda z: (-z['momentum'], -z['idx']))
                self.zones[ztype] = self.zones[ztype][:MAX_ZONES_PER_TYPE]

    def _market_regime(self, close) -> dict:
        """§VII — Market Regime Filter.

        SMA50 > SMA200 & slope(SMA50) > 0 → BULLISH_TREND
        SMA50 < SMA200 & slope(SMA50) < 0 → BEARISH_TREND
        Else → RANGE_BOUND
        """
        if len(close) < 200:
            return {'trend': 'RANGE_BOUND', 'slope': 0.0}
        sma50 = float(np.mean(close[-50:]))
        sma200 = float(np.mean(close[-200:]))
        sma50_prev = float(np.mean(close[-55:-5])) if len(close) >= 55 else sma50
        slope = (sma50 - sma50_prev) / abs(sma50_prev) if sma50_prev != 0 else 0.0

        if sma50 > sma200 and slope > 0:
            return {'trend': 'BULLISH_TREND', 'slope': round(slope, 6)}
        if sma50 < sma200 and slope < 0:
            return {'trend': 'BEARISH_TREND', 'slope': round(slope, 6)}
        return {'trend': 'RANGE_BOUND', 'slope': round(slope, 6)}

    def _reversal_confirmation(self, df) -> dict:
        """Detect reversal patterns on last 1-2 bars for entry trigger."""
        if len(df) < 2:
            return {'bullish': False, 'bearish': False, 'type': 'none'}

        c, o, h, l = df['close'].values[-1], df['open'].values[-1], df['high'].values[-1], df['low'].values[-1]
        pc, po = df['close'].values[-2], df['open'].values[-2]
        ph, pl = df['high'].values[-2], df['low'].values[-2]
        body = abs(c - o)
        upper_w = float(h - max(c, o))
        lower_w = float(min(c, o) - l)

        result = {'bullish': False, 'bearish': False, 'type': 'none'}

        if body > 0 and (h - l) > 0:
            if c < o and upper_w > body * 2 and lower_w < body * 0.3:
                result.update({'bearish': True, 'type': 'bearish_pin_bar'})
            elif c > o and lower_w > body * 2 and upper_w < body * 0.3:
                result.update({'bullish': True, 'type': 'bullish_pin_bar'})

        if h < ph and l < pl:
            if c < o:
                result.update({'bearish': True, 'type': 'inside_bar_breakdown'})
            elif c > o:
                result.update({'bullish': True, 'type': 'inside_bar_breakout'})

        return result

    def _check_triggers(self, df) -> list:
        """§V — Entry Trigger Conditions.

        5 conditions per entry:
          1. Price in zone proximity (±0.2×ATR)
          2. Reversal confirmation (pin/engulfing/inside bar)
          3. Volume > 1.2×SMA20
          4. No HTF opposition (simplified: regime check)
          5. Market regime not opposing
        """
        triggers = []
        n = len(df)
        if n < 2:
            return triggers

        close = float(df['close'].values[-1])
        volume = float(df['volume'].values[-1]) if 'volume' in df.columns else 0
        reversal = self._reversal_confirmation(df)

        for z in self.zones['supply']:
            zl, zh = z['zone_low'], z['zone_high']
            if not (zl - ENTRY_PROXIMITY * self.atr_wilder <= close <= zh + ENTRY_PROXIMITY * self.atr_wilder):
                continue

            if not reversal['bearish']:
                continue

            if volume < self.vol_sma20 * VOL_ENTRY_THRESHOLD:
                continue

            if self.regime['trend'] == 'BULLISH_TREND':
                continue

            sl = zh + 0.5 * self.atr_wilder
            risk = abs(sl - close)
            if risk <= 0:
                continue
            entry_bid = close - self.spread
            sl_ask = sl + self.spread

            triggers.append({
                'direction': 'sell',
                'zone_type': 'supply',
                'zone_low': zl, 'zone_high': zh,
                'entry': round(entry_bid, 6),
                'sl': round(sl_ask, 6),
                'tp1': round(close - risk * 1.5, 6),
                'tp2': round(close - risk * 2.5, 6),
                'tp3': round(close - risk * 3.5, 6),
                'risk': round(risk, 6),
                'confirmation': reversal['type'],
                'momentum': z['momentum'],
            })

        for z in self.zones['demand']:
            zl, zh = z['zone_low'], z['zone_high']
            if not (zl - ENTRY_PROXIMITY * self.atr_wilder <= close <= zh + ENTRY_PROXIMITY * self.atr_wilder):
                continue

            if not reversal['bullish']:
                continue

            if volume < self.vol_sma20 * VOL_ENTRY_THRESHOLD:
                continue

            if self.regime['trend'] == 'BEARISH_TREND':
                continue

            sl = zl - 0.5 * self.atr_wilder
            risk = abs(close - sl)
            if risk <= 0:
                continue
            entry_ask = close + self.spread
            sl_bid = sl - self.spread

            triggers.append({
                'direction': 'buy',
                'zone_type': 'demand',
                'zone_low': zl, 'zone_high': zh,
                'entry': round(entry_ask, 6),
                'sl': round(sl_bid, 6),
                'tp1': round(close + risk * 1.5, 6),
                'tp2': round(close + risk * 2.5, 6),
                'tp3': round(close + risk * 3.5, 6),
                'risk': round(risk, 6),
                'confirmation': reversal['type'],
                'momentum': z['momentum'],
            })

        return triggers

    @property
    def _state_path(self) -> str:
        safe = self.symbol.replace('/', '_').replace(' ', '_')
        return os.path.join(STATE_DIR, f'{safe}.json')

    def save_state(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        data = {
            'symbol': self.symbol,
            'timestamp': time.time(),
            'atr_wilder': self.atr_wilder,
            'vol_sma20': self.vol_sma20,
            '_last_price': self._last_price,
            '_bar_count': self._bar_count,
            'regime': self.regime,
            'zones': self.zones,
            'logs': list(self.logs),
        }
        with open(self._state_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def load_state(self) -> bool:
        if not os.path.exists(self._state_path):
            return False
        try:
            with open(self._state_path) as f:
                data = json.load(f)
            elapsed = time.time() - data.get('timestamp', 0)
            if elapsed > STATE_EXPIRE_SEC:
                os.remove(self._state_path)
                return False
            self.atr_wilder = data.get('atr_wilder', 0.0)
            self.vol_sma20 = data.get('vol_sma20', 0.0)
            self._last_price = data.get('_last_price', 0.0)
            self._bar_count = data.get('_bar_count', 0)
            self.regime = data.get('regime', {'trend': 'RANGE_BOUND', 'slope': 0.0})
            raw_zones = data.get('zones', {'supply': [], 'demand': []})
            self.zones = {
                'supply': list(raw_zones.get('supply', [])),
                'demand': list(raw_zones.get('demand', [])),
            }
            raw_logs = data.get('logs', [])
            self.logs = deque(raw_logs[-MAX_LOGS:], maxlen=MAX_LOGS)
            return True
        except Exception:
            return False

    def _sdl_fallback_check(self, df) -> dict:
        """Simple Demand/Supply Lite — fallback timing filter saat SDZ warming up.

        Checks:
          1. Price in proximity of recent pivot S/R (within 1×ATR)
          2. Reversal confirmation (pin/engulfing/inside bar)
          3. Volume > 1.2×SMA20
        Returns a pseudo-trigger dict or None.
        """
        n = len(df)
        if n < 10 or self.atr_wilder <= 0:
            return {'active': False, 'trigger': None}

        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        open_ = df['open'].values.astype(float)
        volume = df['volume'].values.astype(float) if 'volume' in df.columns else None

        last_close = float(close[-1])
        last_high = float(high[-1])
        last_low = float(low[-1])

        reversal = self._reversal_confirmation(df)
        vol_ok = True
        if volume is not None and self.vol_sma20 > 0:
            vol_ok = float(volume[-1]) > self.vol_sma20 * VOL_ENTRY_THRESHOLD

        lookback = min(30, n - 2)
        swing_highs = []
        swing_lows = []
        for i in range(3, lookback - 3):
            if high[i] == max(high[i-3:i+4]):
                swing_highs.append(float(high[i]))
            if low[i] == min(low[i-3:i+4]):
                swing_lows.append(float(low[i]))

        nearest_res = None
        nearest_sup = None
        for sh in swing_highs:
            if sh > last_close:
                if nearest_res is None or sh < nearest_res:
                    nearest_res = sh
        for sl in swing_lows:
            if sl < last_close:
                if nearest_sup is None or sl > nearest_sup:
                    nearest_sup = sl

        # SELL: price near resistance + bearish reversal + volume
        if nearest_res is not None:
            dist_res = abs(last_close - nearest_res)
            if dist_res <= self.atr_wilder and reversal['bearish'] and vol_ok:
                if self.regime['trend'] != 'BULLISH_TREND':
                    sl = last_close + 0.5 * self.atr_wilder
                    risk = abs(sl - last_close)
                    entry_bid = last_close - self.spread
                    sl_ask = sl + self.spread
                    return {
                        'active': True,
                        'trigger': {
                            'direction': 'sell',
                            'zone_type': 'supply',
                            'zone_low': round(nearest_res, 6),
                            'zone_high': round(nearest_res * 1.001, 6),
                            'entry': round(entry_bid, 6),
                            'sl': round(sl_ask, 6),
                            'tp1': round(last_close - risk * 1.5, 6),
                            'tp2': round(last_close - risk * 2.5, 6),
                            'risk': round(risk, 6),
                            'confirmation': f"sdl_{reversal['type']}",
                            'momentum': 0.0,
                        },
                        'reason': 'SDL fallback: supply proximity + reversal + volume',
                    }

        # BUY: price near support + bullish reversal + volume
        if nearest_sup is not None:
            dist_sup = abs(last_close - nearest_sup)
            if dist_sup <= self.atr_wilder and reversal['bullish'] and vol_ok:
                if self.regime['trend'] != 'BEARISH_TREND':
                    sl = last_close - 0.5 * self.atr_wilder
                    risk = abs(last_close - sl)
                    entry_ask = last_close + self.spread
                    sl_bid = sl - self.spread
                    return {
                        'active': True,
                        'trigger': {
                            'direction': 'buy',
                            'zone_type': 'demand',
                            'zone_low': round(nearest_sup * 0.999, 6),
                            'zone_high': round(nearest_sup, 6),
                            'entry': round(entry_ask, 6),
                            'sl': round(sl_bid, 6),
                            'tp1': round(last_close + risk * 1.5, 6),
                            'tp2': round(last_close + risk * 2.5, 6),
                            'risk': round(risk, 6),
                            'confirmation': f"sdl_{reversal['type']}",
                            'momentum': 0.0,
                        },
                        'reason': 'SDL fallback: demand proximity + reversal + volume',
                    }

        return {'active': False, 'trigger': None}

    def log(self, entry: dict):
        self.logs.append(entry)

    def get_logs(self, n=10) -> list:
        return list(self.logs)[-n:]

    def get_zones(self, type_filter=None) -> dict:
        if type_filter:
            return {type_filter: self.zones.get(type_filter, [])}
        return dict(self.zones)

    def get_triggers(self) -> list:
        return list(self._triggers)

    def get_status(self) -> dict:
        return {
            'symbol': self.symbol,
            'status': 'active' if self._bar_count > 1 else 'warming_up',
            'total_zones': len(self.zones['supply']) + len(self.zones['demand']),
            'supply_zones': len(self.zones['supply']),
            'demand_zones': len(self.zones['demand']),
            'active_triggers': len(self._triggers),
            'regime': self.regime,
            'atr': self.atr_wilder,
            'bars_processed': self._bar_count,
        }


_registry = {}


def get_engine(symbol: str) -> SDZEngine:
    """Singleton factory: one SDZEngine per symbol.
    Restores persisted state if available and not stale.
    """
    if symbol not in _registry:
        engine = SDZEngine(symbol)
        engine.load_state()
        _registry[symbol] = engine
    return _registry[symbol]


def score_sdz(sdz_result: dict) -> tuple:
    """Convert SDZ state into confluence score (replaces old pattern layer).

    Scoring:
      +4  Active buy trigger (demand rejection confirmed)
      -4  Active sell trigger (supply rejection confirmed)
      +2  Demand zone in proximity + momentum ≥ 2.5 | SDL buy fallback
      -2  Supply zone in proximity + momentum ≥ 2.5 | SDL sell fallback
      +1  Demand zone exists (any distance)
      -1  Supply zone exists (any distance)
      +0.5 Market regime searah (range_bound → either)
      -0.5 Market regime berlawanan
    """
    score = 0
    reasons = []

    # Check SDL fallback first (works even during warming_up)
    sdl_active = sdz_result.get('sdl_active', False) if sdz_result else False
    sdl_trigger = sdz_result.get('sdl_trigger') if sdz_result else None
    if sdl_active and sdl_trigger:
        if sdl_trigger['direction'] == 'buy':
            score += 2
            reasons.append(f"SDL buy: {sdl_trigger['confirmation']} at demand")
        elif sdl_trigger['direction'] == 'sell':
            score -= 2
            reasons.append(f"SDL sell: {sdl_trigger['confirmation']} at supply")

    if sdz_result and sdz_result.get('status') != 'active':
        if sdl_active:
            score = max(-4, min(4, score))
            return score, ', '.join(reasons) if reasons else 'SDL active'
        return 0, 'SDZ engine not ready'

    triggers = sdz_result.get('triggers', [])
    zones = sdz_result.get('zones', {})
    regime = sdz_result.get('regime', {})

    for t in triggers:
        if t['direction'] == 'buy':
            score += 4
            reasons.append(f"Buy trigger: {t['confirmation']} at demand (momentum {t['momentum']}×ATR)")
        elif t['direction'] == 'sell':
            score -= 4
            reasons.append(f"Sell trigger: {t['confirmation']} at supply (momentum {t['momentum']}×ATR)")

    for z in zones.get('demand', []):
        if z.get('momentum', 0) >= 2.5:
            score += 2
            reasons.append(f"Demand zone proximity ({z['momentum']}×ATR)")
        else:
            score += 1
            reasons.append("Demand zone present")

    for z in zones.get('supply', []):
        if z.get('momentum', 0) >= 2.5:
            score -= 2
            reasons.append(f"Supply zone proximity ({z['momentum']}×ATR)")
        else:
            score -= 1
            reasons.append("Supply zone present")

    r_trend = regime.get('trend', 'RANGE_BOUND')
    if r_trend == 'BULLISH_TREND' and score > 0:
        score += 0.5
        reasons.append('Regime bullish searah')
    elif r_trend == 'BEARISH_TREND' and score < 0:
        score += 0.5
        reasons.append('Regime bearish searah')
    elif r_trend == 'RANGE_BOUND':
        score += 0.5
        reasons.append('Regime range (netral)')
    elif r_trend == 'BULLISH_TREND' and score < 0:
        score -= 0.5
        reasons.append('Regime bullish berlawanan')
    elif r_trend == 'BEARISH_TREND' and score > 0:
        score -= 0.5
        reasons.append('Regime bearish berlawanan')

    score = max(-4, min(4, score))
    return score, ', '.join(reasons) if reasons else 'neutral'
