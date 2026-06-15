from analysis import INDICATOR_PARAMS

METHODOLOGY = {
    'ema_alignment': {
        'name': 'Trend Filter',
        'rule': 'EMA20 > EMA50 untuk buy, EMA20 < EMA50 untuk sell',
        'why': 'Memastikan entry searah dengan momentum dominan. EMA20 adalah fast line yang merefleksikan harga terkini, EMA50 adalah medium line sebagai konfirmasi tren. Bullish alignment = EMA20 > EMA50 = tekanan beli dominan.',
    },
    'rsi_range': {
        'name': 'Momentum Filter',
        'rule': '30 \u2264 RSI \u2264 70',
        'why': 'Mencegah entry di zona overbought (RSI >70) atau oversold (RSI <30). RSI 30-70 adalah "sweet spot" di mana momentum masih sehat dan harga memiliki ruang untuk bergerak.',
    },
    'sdz_trigger': {
        'name': 'Timing Filter',
        'rule': 'SDZ entry trigger aktif (zone rejection + reversal confirmation + volume)',
        'why': 'SDZ Engine mendeteksi supply/demand zone dari engulfing pattern, memvalidasi dengan momentum impulsif (≥2×ATR), dan menunggu konfirmasi reversal (pin/engulfing/inside bar) + volume spike sebelum trigger entry. Tanpa trigger aktif, entry adalah "menebak" tanpa konfirmasi price action.',
    },
    'higher_tf_aligned': {
        'name': 'Context Filter',
        'rule': 'Higher timeframe (H4/H1/D1) searah dengan entry TF',
        'why': 'Higher TF adalah "big picture". Entry melawan higher TF = melawan arus utama. Probabilitas menang turun drastis. H4 alignment memastikan kita trading dengan tren, bukan melawannya.',
    },
    'sl_atr': {
        'name': 'Risk Filter',
        'rule': 'SL \u2264 2 \u00d7 ATR',
        'why': 'ATR mengukur volatilitas pasar. SL > 2x ATR berarti risk terlalu besar relatif terhadap pergerakan normal harga. Filter ini memastikan setiap trade memiliki risk yang terukur dan konsisten.',
    },
}

MODE_NAMES = {
    'scalp': 'SCALP (M1/M5)',
    'intraday': 'INTRADAY (H1)',
    'swing': 'SWING (D1)',
}

CONFIDENCE_MAP = {
    (8, 10): ('SANGAT KUAT', 'High conviction entry. Multi-TF aligned, semua layer konfirmasi.'),
    (6, 7.9): ('KUAT', 'Standard entry. Sebagian besar layer setuju, risk terukur.'),
    (4, 5.9): ('MODERAT', 'Watch list. Butuh konfirmasi tambahan sebelum eksekusi.'),
    (2, 3.9): ('LEMAH', 'Skip / reduce size. Terlalu banyak konflik antar layer.'),
    (0, 1.9): ('TIDAK LAYAK', 'No trade. Konflik signal, tidak ada konfluensi.'),
}

LAYER_ICONS = {
    'trend': '\u25b2', 'momentum': '\u26a1', 'volatility': '\u25b4',
    'volume': '\u25a0', 'pattern': '\u2726',
}

LAYER_NAMES = {
    'trend': 'TREND', 'momentum': 'MOMENTUM', 'volatility': 'VOLATILITY',
    'volume': 'VOLUME', 'pattern': 'SDZ (SUPPLY/DEMAND)',
}


def _conf_level(confidence):
    for (lo, hi), (label, desc) in sorted(CONFIDENCE_MAP.items(), reverse=True):
        if lo <= confidence <= hi:
            return label, desc
    return 'TIDAK DIKETAHUI', ''


def _bar(signal):
    if not signal:
        return '\u25c6'
    if 'strong_buy' in signal or 'buy' in signal:
        return '\u25b2'
    if 'strong_sell' in signal or 'sell' in signal:
        return '\u25bc'
    return '\u25c6'


def _rr_color(rr_ok):
    return '\033[92m' if rr_ok else '\033[91m'


def _bar_colored(signal):
    direction = 'BUY' if 'buy' in signal else 'SELL' if 'sell' in signal else 'NEUTRAL'
    bar = _bar(signal)
    color = '\033[92m' if 'buy' in signal else '\033[91m' if 'sell' in signal else '\033[93m'
    return f'{color}{bar} {direction}\033[0m'


def _signal_emoji(passed, total):
    if passed == total:
        return '\U0001f389'
    if passed >= total - 1:
        return '\u2705'
    if passed >= total // 2:
        return '\u26a0\ufe0f'
    return '\u274c'


def format_signal_card(result: dict, trading_plan: dict = None, higher_tf: dict = None) -> str:
    lines = []
    W = 68

    symbol = result.get('symbol', '?')
    mode = result.get('mode', 'intraday')
    mode_name = MODE_NAMES.get(mode, mode.upper())
    price = result.get('price', 0)
    c = result.get('confluence', {})
    e = result.get('execution', {})
    ind = result.get('indicators', {})
    sr = result.get('support_resistance', {})
    tp = trading_plan or {}
    ht = higher_tf or {}

    signal = c.get('signal', 'neutral')
    confidence = c.get('confidence', 0)
    conf_label, conf_desc = _conf_level(confidence)
    bar = _bar(signal)

    lines.append('')
    lines.append(f'\033[1;36m\u2554\u2550\u2550 SIGNAL ENGINE \u00b7 {symbol} \u00b7 {mode_name} \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557\033[0m')
    bar_color = '\033[92m' if 'buy' in signal else '\033[91m' if 'sell' in signal else '\033[93m'
    signal_label = 'BUY' if 'buy' in signal else 'SELL' if 'sell' in signal else 'NEUTRAL'
    lines.append(f'\033[1;36m\u2551\033[0m  {bar_color}{bar} {signal_label}\033[0m  |  Confidence: \033[1m{confidence}/10\033[0m ({conf_label})  \033[1;36m\u2551\033[0m')
    lines.append(f'\033[1;36m\u2551\033[0m  Price: \033[1m${price:.5f}\033[0m  |  ATR: \033[1m${ind.get("atr", 0):.5f}\033[0m                  \033[1;36m\u2551\033[0m')
    lines.append(f'\033[1;36m\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d\033[0m')
    lines.append('')

    tp_conds = tp.get('conditions', {})
    tp_pass = tp.get('pass_count', 0)
    tp_total = len(tp_conds)

    if tp_total > 0:
        emoji = _signal_emoji(tp_pass, tp_total)
        lines.append(f'  \033[1;34mTRADING PLAN CHECKLIST\033[0m  {emoji}  {tp_pass}/{tp_total} Conditions PASSED')
        lines.append(f'  \033[34m\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\033[0m')

        for key, cond in tp_conds.items():
            meta = METHODOLOGY.get(key, {})
            icon = '\u2705' if cond['pass'] else '\u274c'
            color = '\033[92m' if cond['pass'] else '\033[91m'
            lines.append(f'  {color}{icon} {meta.get("name", key)}\033[0m')
            lines.append(f'     \033[90m{cond["detail"]}\033[0m')
            lines.append(f'     \u2192 {meta.get("why", "")}')

        lines.append(f'  \033[90m\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\033[0m')
        rule = f'Rule: Entry hanya jika MINIMAL {tp_total - 1}/{tp_total} kondisi terpenuhi (saat ini {tp_pass}/{tp_total})'
        lines.append(f'     {rule}')
        lines.append('')

    lines.append(f'  \033[1;34m5-LAYER CONFLUENCE BREAKDOWN\033[0m')
    lines.append(f'  \033[34m\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\033[0m')
    for layer, data in c.get('breakdown', {}).items():
        s = int(data['score'])
        reason = data.get('reason', '')
        icon = '\u2705' if s > 0 else '\u26a0\ufe0f' if s == 0 else '\u274c'
        col = '\033[92m' if s > 0 else '\033[93m' if s == 0 else '\033[91m'
        lines.append(f'  {col}{icon} {LAYER_NAMES.get(layer, layer.upper())}  [{s:+d}] {reason}\033[0m')

    lines.append('')

    sdz = result.get('sdz')
    if sdz:
        regime = sdz.get('regime', {})
        r_trend = regime.get('trend', 'RANGE_BOUND') if regime else 'RANGE_BOUND'
        r_slope = regime.get('slope', 0.0) if regime else 0.0
        r_color = '\033[92m' if r_trend == 'BULLISH_TREND' else '\033[91m' if r_trend == 'BEARISH_TREND' else '\033[93m'

        is_active = sdz.get('status') == 'active'
        sdl_active = sdz.get('sdl_active', False)

        lines.append(f'  \033[1;34mSDZ ENGINE STATUS\033[0m')
        lines.append(f'  \033[34m\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\033[0m')
        lines.append(f'     Market Regime: {r_color}{r_trend}\033[0m (slope {r_slope:+.6f})')

        if is_active:
            lines.append(f'     Active Zones: {sdz.get("supply_zones", "?")} supply + {sdz.get("demand_zones", "?")} demand')

            zones_data = sdz.get('zones', {}) or {}
            for ztype, color, sym in [('supply', '\033[91m', '\u25bc'), ('demand', '\033[92m', '\u25b2')]:
                for z in zones_data.get(ztype, [])[:3]:
                    zl = z.get('zone_low', 0)
                    zh = z.get('zone_high', 0)
                    mom = z.get('momentum', 0)
                    age = z.get('age', 0)
                    lines.append(f'     {color}{sym} {ztype.upper()} Zone: ${zl:.5f}-${zh:.5f} | age:{age} | mom:{mom:.1f}×ATR\033[0m')

        if sdl_active:
            sdl_t = sdz.get('sdl_trigger')
            if sdl_t:
                t_color = '\033[92m' if sdl_t['direction'] == 'buy' else '\033[91m'
                lines.append(f'     {t_color}\u2713 SDL {sdl_t["direction"].upper()} TRIGGER: {sdl_t["zone_type"].upper()} proximity\033[0m')
                lines.append(f'       Confirmation: {sdl_t["confirmation"]} | fallback: S/R + reversal + volume')
                entry_str = f'Entry: ${sdl_t["entry"]:.5f}' if sdl_t.get('entry') else ''
                sl_str = f'SL: ${sdl_t["sl"]:.5f}' if sdl_t.get('sl') else ''
                tp1_str = f'TP1: ${sdl_t["tp1"]:.5f}' if sdl_t.get('tp1') else ''
                tp2_str = f'TP2: ${sdl_t["tp2"]:.5f}' if sdl_t.get('tp2') else ''
                lines.append(f'       {entry_str} | {sl_str} | {tp1_str} | {tp2_str}')
            else:
                lines.append(f'     \033[90mSDL active — no trigger (S/R proximity tanpa reversal)\033[0m')
        elif is_active:
            triggers = sdz.get('triggers', []) or []
            if triggers:
                t = triggers[0]
                t_color = '\033[92m' if t['direction'] == 'buy' else '\033[91m'
                lines.append(f'     {t_color}\u2713 {t["direction"].upper()} TRIGGER: {t["zone_type"].upper()} zone rejection\033[0m')
                lines.append(f'       Confirmation: {t["confirmation"]} | momentum: {t["momentum"]}×ATR')
                entry_str = f'Entry: ${t["entry"]:.5f}' if t.get('entry') else ''
                sl_str = f'SL: ${t["sl"]:.5f}' if t.get('sl') else ''
                tp1_str = f'TP1: ${t["tp1"]:.5f}' if t.get('tp1') else ''
                tp2_str = f'TP2: ${t["tp2"]:.5f}' if t.get('tp2') else ''
                lines.append(f'       {entry_str} | {sl_str} | {tp1_str} | {tp2_str}')
            else:
                lines.append(f'     \033[90mNo active trigger — waiting for confirmation\033[0m')
        else:
            lines.append(f'     \033[90mStatus: {sdz.get("status", "?")} — SDL fallback tidak aktif\033[0m')
        lines.append('')

    lines.append(f'  \033[1;34mEXECUTION PLAN\033[0m')
    lines.append(f'  \033[34m\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\033[0m')
    el = e.get('entry_zone_low', 0)
    eh = e.get('entry_zone_high', 0)
    sl = e.get('sl', 0)
    tp1 = e.get('tp1', 0)
    tp2 = e.get('tp2', 0)

    if el and eh:
        sl_pct = (sl / el - 1) * 100 if el else 0
        tp1_pct = (tp1 / el - 1) * 100 if el else 0
        tp2_pct = (tp2 / el - 1) * 100 if el else 0
        rr1 = e.get('rr1', 0)
        rr2 = e.get('rr2', 0)
        rr_ok = e.get('rr_ok', False)
        rr_col = '\033[92m' if rr_ok else '\033[91m'
        rr_label = 'PASS' if rr_ok else 'FAIL'

        lines.append(f'     Entry Zone:  \033[1m${el:.5f} - ${eh:.5f}\033[0m')
        lines.append(f'     Stop Loss:   \033[91m${sl:.5f}  ({sl_pct:+.2f}%)\033[0m')
        lines.append(f'     TP1:         \033[92m${tp1:.5f}  ({tp1_pct:+.2f}%)   RR: {rr1}:1\033[0m {rr_col}[{rr_label}]\033[0m')
        lines.append(f'     TP2:         \033[92m${tp2:.5f}  ({tp2_pct:+.2f}%)   RR: {rr2}:1\033[0m')

    if sr:
        lines.append(f'     Levels:  S1 \033[91m${sr.get("support_1", 0):.5f}\033[0m | Pivot \033[93m${sr.get("pivot", 0):.5f}\033[0m | R1 \033[92m${sr.get("resistance_1", 0):.5f}\033[0m')

    lines.append('')

    lines.append(f'  \033[1;34mHIGHER TF CONTEXT ({ht.get("timeframe", "?")})\033[0m')
    lines.append(f'  \033[34m\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\033[0m')
    h_sig = ht.get('signal', '?')
    h_conf = ht.get('confidence', '?')
    h_trend = ht.get('trend', '?')
    h_bar = _bar(h_sig) if h_sig and h_sig != '?' else '?'
    h_sig_display = h_sig.upper() if isinstance(h_sig, str) else '?'
    h_conf_display = h_conf if h_conf is not None else '?'
    h_trend_display = h_trend if h_trend else '?'
    lines.append(f'     {h_bar} Signal: {h_sig_display}  |  Confidence: {h_conf_display}/10  |  Trend: {h_trend_display}')

    aligned = result.get('multi_tf_aligned', False)
    if aligned:
        lines.append(f'     \033[92m\u2713 Aligned: H4 searah dengan H1 \u2192 confidence TIDAK di-downgrade\033[0m')
    else:
        lines.append(f'     \033[91m\u2717 Misaligned: H4 TIDAK searah \u2192 confidence di-downgrade 30%\033[0m')

    lines.append('')

    lines.append(f'  \033[1;34mCONSISTENCY CHECK\033[0m')
    lines.append(f'  \033[34m\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\033[0m')
    consistency_issues = []

    if tp_total > 0:
        cond1 = tp_conds.get('ema_alignment', {})
        cond3 = tp_conds.get('sdz_trigger', {})
        if not cond1.get('pass', False):
            consistency_issues.append(('\u26a0\ufe0f', 'Trend Filter tidak lolos', f'Signal {signal_label} dari konfluensi tetapi EMA tidak bullish. Periksa apakah signal benar-benar searah.'))
        if not cond3.get('pass', False):
            consistency_issues.append(('\u26a0\ufe0f', 'Timing Filter tidak lolos', 'Tidak ada SDZ/SDL trigger aktif. Entry tanpa konfirmasi price action + volume.'))
        if tp_pass >= tp_total - 1:
            consistency_issues.append(('\u2705', 'Trading Plan lolos', f'{tp_pass}/{tp_total} kondisi terpenuhi. Setup layak dieksekusi.'))

    if confidence < 5:
        consistency_issues.append(('\u26a0\ufe0f', 'Confidence rendah', f'Skor {confidence}/10 < 5. Risiko lebih tinggi dari biasanya.'))
    if not e.get('rr_ok', False):
        consistency_issues.append(('\u274c', 'RR tidak memadai', f'RR {e.get("rr1", 0)}:1 di bawah minimum {e.get("min_rr", 2)}:1. Trade tidak layak secara risk/reward.'))
    if not aligned:
        consistency_issues.append(('\u274c', 'Multi-TF misaligned', 'Entry melawan higher TF. Probabilitas menurun signifikan.'))

    if not consistency_issues:
        consistency_issues.append(('\u2705', 'Semua konsisten', 'TA \u2192 Entry \u2192 Method: fully aligned. Setup siap eksekusi.'))

    for icon, title, desc in consistency_issues:
        col = '\033[92m' if '\u2705' in icon else '\033[93m' if '\u26a0' in icon else '\033[91m'
        lines.append(f'  {col}{icon} {title}\033[0m')
        lines.append(f'     {desc}')

    lines.append('')

    ta_ok = confidence >= 5 and aligned and e.get('rr_ok', False)
    method_ok = tp_pass >= tp_total - 1
    entry_ok = ta_ok and method_ok

    if entry_ok:
        verdict = '\033[92mEKSEKUSI: Setup memenuhi syarat. Entry sesuai rencana.\033[0m'
    elif ta_ok and not method_ok:
        verdict = '\033[93mWATCH LIST: TA bagus tapi trading plan belum penuh. Tunggu konfirmasi.\033[0m'
    elif method_ok and not ta_ok:
        verdict = '\033[93mWATCH LIST: Trading plan ok tapi TA lemah. Cari entry lebih baik.\033[0m'
    else:
        verdict = '\033[91mSKIP: TA lemah + trading plan tidak lolos. Tidak layak entry.\033[0m'

    lines.append(f'  \033[1mVERDICT:\033[0m {verdict}')
    lines.append('')

    lines.append(f'  \033[90mMethodology: Hybrid Rule+AI | 5-Layer Confluence + 5-Condition Trading Plan\033[0m')
    lines.append(f'  \033[90mData: yfinance (forex) | gold-api.com (XAU/XAG) | Binance (crypto)\033[0m')
    lines.append(f'  \033[90mEntry manual | SL/TP berdasarkan ATR | Risk management wajib\033[0m')
    lines.append('')

    return '\n'.join(lines)


def check_consistency(result: dict, trading_plan: dict) -> dict:
    c = result.get('confluence', {})
    e = result.get('execution', {})
    ind = result.get('indicators', {})
    tp = trading_plan or {}

    signal = c.get('signal', 'neutral')
    confidence = c.get('confidence', 0)
    tp_pass = tp.get('pass_count', 0)
    tp_total = len(tp.get('conditions', {}))
    aligned = result.get('multi_tf_aligned', True)

    issues = []
    strong_signals = []

    if confidence >= 5:
        strong_signals.append('Confidence >= 5: sinyal cukup kuat')
    if aligned:
        strong_signals.append('Multi-TF aligned: tidak melawan tren besar')
    if e.get('rr_ok', False):
        strong_signals.append(f'RR {e.get("rr1", 0)}:1 memenuhi minimum {e.get("min_rr", 2)}:1')
    if tp_pass >= tp_total - 1:
        strong_signals.append(f'Trading plan {tp_pass}/{tp_total} lolos')

    if confidence < 5:
        issues.append(f'Confidence {confidence}/10 < 5: sinyal lemah')
    if not aligned:
        issues.append('Multi-TF misaligned: entry melawan higher TF')
    if not e.get('rr_ok', False):
        issues.append(f'RR {e.get("rr1", 0)}:1 di bawah minimum {e.get("min_rr", 2)}:1')
    if tp_pass < tp_total - 1:
        issues.append(f'Trading plan {tp_pass}/{tp_total}: terlalu banyak kondisi gagal')

    ta_to_entry = 'konsisten' if confidence >= 5 else 'lemah'
    ta_to_method = 'sesuai' if tp_pass >= tp_total - 1 else 'kurang sesuai'
    method_to_entry = 'konsisten' if (confidence >= 5 and tp_pass >= tp_total - 1) else 'perlu verifikasi'

    return {
        'consistent': len(issues) == 0,
        'issues': issues,
        'strong_signals': strong_signals,
        'ta_to_entry': ta_to_entry,
        'ta_to_method': ta_to_method,
        'method_to_entry': method_to_entry,
        'verdict': 'EKSEKUSI' if len(issues) == 0 else 'WATCH LIST' if len(issues) <= 2 else 'SKIP',
    }


def format_scan_table(results: list, mode: str, limit: int = 5) -> str:
    lines = []
    mode_name = MODE_NAMES.get(mode, mode.upper())

    lines.append(f'\033[1;36m\u2554\u2550\u2550 SIGNAL SCAN \u00b7 {mode_name} \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557\033[0m')
    lines.append(f'\033[1;36m\u2551\033[0m  Top {min(limit, len(results))} signals sorted by strength        \033[1;36m\u2551\033[0m')
    lines.append(f'\033[1;36m\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d\033[0m')
    lines.append('')

    for i, r in enumerate(results[:limit], 1):
        symbol = r.get('symbol', '?')
        c = r.get('confluence', {})
        e = r.get('execution', {})
        signal = c.get('signal', 'neutral')
        confidence = c.get('confidence', 0)
        price = r.get('price', 0)
        rr_ok = e.get('rr_ok', False)
        conf_label, _ = _conf_level(confidence)
        bar = _bar(signal)

        sig_col = '\033[92m' if 'buy' in signal else '\033[91m' if 'sell' in signal else '\033[93m'
        rr_mark = '\033[92m\u2713\033[0m' if rr_ok else '\033[91m\u2717\033[0m'

        lines.append(f'  \033[1m#{i} {sig_col}{bar} {symbol.upper()}\033[0m  |  {sig_col}{signal.upper()}\033[0m  |  \033[1m{confidence}/10\033[0m ({conf_label})  |  RR {rr_mark}')
        lines.append(f'     Price: \033[1m${price:.5f}\033[0m  |  TP1: \033[92m${e.get("tp1", 0):.5f}\033[0m  |  SL: \033[91m${e.get("sl", 0):.5f}\033[0m')

        ind = r.get('indicators', {})
        ma = ind.get('ma_alignment', '?')
        rsi = ind.get('rsi', '?')
        sdz = r.get('sdz', {})
        sdz_status = sdz.get('status', 'inactive') if sdz else 'inactive'
        sdz_str = f'SDZ: {sdz_status}' if sdz_status != 'inactive' else 'SDZ: init'
        lines.append(f'     MA: {ma}  |  RSI: {rsi}  |  {sdz_str}')

        lines.append('')

    lines.append(f'  \033[90mScan mode: {mode} | Ranking by absolute net score | Entry manual\033[0m')
    lines.append('')

    return '\n'.join(lines)


def format_pairs_list(categorized: dict) -> str:
    lines = []
    cat_names = {
        'major': 'MAJOR PAIRS',
        'cross': 'CROSS PAIRS',
        'exotic': 'EXOTIC PAIRS',
        'commodity': 'COMMODITY',
        'crypto': 'CRYPTO',
    }

    lines.append('\033[1;36m\u2554\u2550\u2550 SUPPORTED PAIRS \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557\033[0m')
    lines.append('\033[1;36m\u2551\033[0m  31 pairs across 5 categories                    \033[1;36m\u2551\033[0m')
    lines.append('\033[1;36m\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d\033[0m')
    lines.append('')

    for cat, cat_label in cat_names.items():
        items = categorized.get(cat, [])
        if not items:
            continue
        lines.append(f'  \033[1;34m{cat_label}\033[0m  (\033[90m{len(items)} pairs\033[0m)')
        pairs_line = '  \033[90m  \033[0m'.join(f'\033[1m{p["symbol"]}\033[0m' if isinstance(p, dict) else str(p) for p in items)
        for p in items:
            sym = p['symbol'] if isinstance(p, dict) else str(p)
            name = p.get('name', '') if isinstance(p, dict) else ''
            lines.append(f'    \033[1m{sym}\033[0m  \033[90m{name}\033[0m')
        lines.append('')

    lines.append(f'  \033[90mUse: /analyze EUR/USD intraday | /signal EUR/USD swing | intraday GBP/JPY\033[0m')
    lines.append('')

    return '\n'.join(lines)
