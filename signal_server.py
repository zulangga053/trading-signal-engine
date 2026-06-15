#!/usr/bin/env python3
"""
Trading Signal Engine — MCP Server
Modes: scalp, intraday, swing
"""

import json
import sys
import signal
import traceback
from typing import Any

from pairs import PAIRS, get_pair, get_pairs_for_mode, MODE_TF, MODE_PAIRS
from data import get_rates, invalidate_cache, prefetch_pairs
from analysis import full_analysis, validate_trading_plan
from display import format_signal_card, check_consistency, format_scan_table, format_pairs_list
from sdz_engine import get_engine, SDZEngine
import journal

MODE_HELP = {
    'scalp': 'Fast analysis M1/M5 — 10 major pairs. Valid ~15 menit.',
    'intraday': 'Medium analysis H1 — 20 pairs. Valid ~1-4 jam.',
    'swing': 'Long analysis D1 — 28+ pairs. Valid ~1-7 hari.',
}

MODE_PERIOD = {'scalp': '5d', 'intraday': '1mo', 'swing': '2y'}

running = True


def log(msg: str):
    print(msg, file=sys.stderr, flush=True)


def send_json(data: dict):
    line = json.dumps(data)
    sys.stdout.write(line + '\n')
    sys.stdout.flush()


def handle_request(req: dict) -> dict:
    method = req.get('method', '')
    req_id = req.get('id')
    params = req.get('params', {})

    if method == 'initialize':
        return {
            'jsonrpc': '2.0',
            'id': req_id,
            'result': {
                'protocolVersion': '2024-11-05',
                'capabilities': {'tools': {}},
                'serverInfo': {'name': 'trading-signal-engine', 'version': '2.0.0'},
            },
        }

    if method == 'notifications/initialized':
        return {'jsonrpc': '2.0', 'id': req_id, 'result': {}}

    if method == 'ping':
        return {'jsonrpc': '2.0', 'id': req_id, 'result': {}}

    if method == 'tools/list':
        return {
            'jsonrpc': '2.0',
            'id': req_id,
            'result': {'tools': TOOLS},
        }

    if method == 'tools/call':
        return handle_tool_call(req_id, params)

    return {
        'jsonrpc': '2.0',
        'id': req_id,
        'error': {'code': -32601, 'message': f'Method not found: {method}'},
    }


def handle_tool_call(req_id: Any, params: dict) -> dict:
    tool_name = params.get('name', '')
    args = params.get('arguments', {})

    try:
        if tool_name == 'get_pairs':
            return tool_get_pairs(req_id, args)
        elif tool_name == 'get_rates':
            return tool_get_rates(req_id, args)
        elif tool_name == 'get_indicators':
            return tool_get_indicators(req_id, args)
        elif tool_name == 'analyze_technical':
            return tool_analyze_technical(req_id, args)
        elif tool_name == 'scan_markets':
            return tool_scan_markets(req_id, args)
        elif tool_name == 'generate_signal':
            return tool_generate_signal(req_id, args)
        elif tool_name in ('scalp', 'scan_scalp'):
            return tool_scan_mode(req_id, 'scalp', args)
        elif tool_name in ('intraday', 'scan_intraday'):
            return tool_scan_mode(req_id, 'intraday', args)
        elif tool_name in ('swing', 'scan_swing'):
            return tool_scan_mode(req_id, 'swing', args)
        elif tool_name == 'sdz_zones':
            return tool_sdz_zones(req_id, args)
        elif tool_name == 'sdz_scan':
            return tool_sdz_scan(req_id, args)
        elif tool_name == 'sdz_logs':
            return tool_sdz_logs(req_id, args)
        elif tool_name == 'journal_list':
            return tool_journal_list(req_id, args)
        elif tool_name == 'journal_stats':
            return tool_journal_stats(req_id, args)
        elif tool_name == 'journal_update':
            return tool_journal_update(req_id, args)
        elif tool_name == 'journal_export':
            return tool_journal_export(req_id, args)
        elif tool_name == 'journal_report':
            return tool_journal_report(req_id, args)
        else:
            return {
                'jsonrpc': '2.0',
                'id': req_id,
                'error': {'code': -32602, 'message': f'Unknown tool: {tool_name}'},
            }
    except Exception as e:
        log(f'Error in {tool_name}: {traceback.format_exc()}')
        return {
            'jsonrpc': '2.0',
            'id': req_id,
            'error': {'code': -32000, 'message': str(e)},
        }


def tool_get_pairs(req_id: Any, args: dict) -> dict:
    category = args.get('category')
    if category:
        result = [(p.symbol, p.name, p.category) for p in PAIRS if p.category == category]
        return {
            'jsonrpc': '2.0',
            'id': req_id,
            'result': {'content': [{'type': 'text', 'text': json.dumps(result, indent=2)}]},
        }
    else:
        grouped = {}
        for p in PAIRS:
            grouped.setdefault(p.category, []).append({'symbol': p.symbol, 'name': p.name})
        return {
            'jsonrpc': '2.0',
            'id': req_id,
            'result': {'content': [{'type': 'text', 'text': format_pairs_list(grouped)}]},
        }


def tool_get_rates(req_id: Any, args: dict) -> dict:
    symbol = args.get('symbol', '').upper()
    interval = args.get('interval', '1h')
    period = args.get('period', '1mo')
    limit = args.get('limit', 100)

    pair = get_pair(symbol)
    if not pair:
        return {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32000, 'message': f'Unknown pair: {symbol}'}}

    df = get_rates(pair.yahoo_ticker, interval, period)
    df = df.tail(limit)
    candles = []
    for idx, row in df.iterrows():
        candles.append({
            'time': str(idx),
            'open': round(float(row['open']), 5),
            'high': round(float(row['high']), 5),
            'low': round(float(row['low']), 5),
            'close': round(float(row['close']), 5),
            'volume': round(float(row['volume']), 2),
        })

    return {
        'jsonrpc': '2.0',
        'id': req_id,
        'result': {'content': [{'type': 'text', 'text': json.dumps(candles, indent=2)}]},
    }


def tool_get_indicators(req_id: Any, args: dict) -> dict:
    symbol = args.get('symbol', '').upper()
    mode = args.get('mode', 'intraday')
    interval = args.get('interval', '1h')
    period = args.get('period', '1mo')

    pair = get_pair(symbol)
    if not pair:
        return {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32000, 'message': f'Unknown pair: {symbol}'}}

    df = get_rates(pair.yahoo_ticker, interval, period)
    from indicators import compute_indicators
    ind = compute_indicators(df, mode)

    return {
        'jsonrpc': '2.0',
        'id': req_id,
        'result': {'content': [{'type': 'text', 'text': json.dumps(ind, indent=2)}]},
    }


def tool_analyze_technical(req_id: Any, args: dict) -> dict:
    symbol = args.get('symbol', '').upper()
    mode = args.get('mode', 'intraday')
    interval = args.get('interval')

    pair = get_pair(symbol)
    if not pair:
        return {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32000, 'message': f'Unknown pair: {symbol}'}}

    if not interval:
        interval = MODE_TF[mode][1] if mode in MODE_TF else '1h'

    period = MODE_PERIOD.get(mode, '1mo')
    df = get_rates(pair.yahoo_ticker, interval, period)
    sdz = get_engine(pair.symbol)
    sdz_result = sdz.update(df)
    result = full_analysis(df, mode, symbol, sdz_result=sdz_result)

    card = format_signal_card(result)

    return {
        'jsonrpc': '2.0',
        'id': req_id,
        'result': {'content': [{'type': 'text', 'text': card}]},
    }


def tool_scan_markets(req_id: Any, args: dict) -> dict:
    mode = args.get('mode', 'intraday')
    limit = args.get('limit', 5)
    pairs = get_pairs_for_mode(mode)
    interval = MODE_TF[mode][1]
    period = MODE_PERIOD.get(mode, '1mo')

    results = []
    for pair in pairs[:15]:
        try:
            df = get_rates(pair.yahoo_ticker, interval, period)
            sdz = get_engine(pair.symbol)
            sdz_result = sdz.update(df)
            analysis = full_analysis(df, mode, pair.symbol, sdz_result=sdz_result)
            results.append(analysis)
        except Exception as e:
            log(f'Scan error {pair.symbol}: {e}')

    results.sort(key=lambda x: abs(x.get('confluence', {}).get('net_score', 0)), reverse=True)

    card = format_scan_table(results, mode, limit)

    return {
        'jsonrpc': '2.0',
        'id': req_id,
        'result': {'content': [{'type': 'text', 'text': card}]},
    }


def tool_generate_signal(req_id: Any, args: dict) -> dict:
    symbol = args.get('symbol', '').upper()
    mode = args.get('mode', 'intraday')

    pair = get_pair(symbol)
    if not pair:
        return {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32000, 'message': f'Unknown pair: {symbol}'}}

    tfs = MODE_TF.get(mode, ['1h'])
    period = MODE_PERIOD.get(mode, '1mo')

    entry_tf = tfs[1] if len(tfs) > 1 else tfs[0]
    higher_tf = tfs[2] if len(tfs) > 2 else tfs[1] if len(tfs) > 1 else tfs[0]
    lower_tf = tfs[0]

    df_entry = get_rates(pair.yahoo_ticker, entry_tf, period)
    sdz = get_engine(pair.symbol)
    sdz_result = sdz.update(df_entry)
    result = full_analysis(df_entry, mode, pair.symbol, sdz_result=sdz_result)

    try:
        df_higher = get_rates(pair.yahoo_ticker, higher_tf, '5y' if mode == 'swing' else '6mo')
        sdz_higher = get_engine(f'{pair.symbol}_{higher_tf}')
        sdz_higher_result = sdz_higher.update(df_higher)
        higher = full_analysis(df_higher, mode, f'{symbol} ({higher_tf})', sdz_result=sdz_higher_result)
        result['higher_tf'] = {
            'timeframe': higher_tf,
            'signal': higher.get('confluence', {}).get('signal'),
            'confidence': higher.get('confluence', {}).get('confidence'),
            'trend': higher.get('indicators', {}).get('ma_alignment'),
        }
    except Exception:
        result['higher_tf'] = {'error': 'cannot_fetch'}

    try:
        df_lower = get_rates(pair.yahoo_ticker, lower_tf, '5d' if mode == 'scalp' else '15d' if mode == 'intraday' else '1mo')
        lower = full_analysis(df_lower, mode, f'{symbol} ({lower_tf})')
        result['lower_tf'] = {
            'timeframe': lower_tf,
            'signal': lower.get('confluence', {}).get('signal'),
            'confidence': lower.get('confluence', {}).get('confidence'),
        }
    except Exception:
        result['lower_tf'] = {'error': 'cannot_fetch'}

    tf_aligned = True
    if 'higher_tf' in result and 'signal' in result['higher_tf']:
        h_sig = result['higher_tf']['signal']
        e_sig = result.get('confluence', {}).get('signal')
        if h_sig and e_sig:
            h_bull = 'bull' in h_sig or 'buy' in h_sig
            e_bull = 'bull' in e_sig or 'buy' in e_sig
            if h_bull != e_bull:
                tf_aligned = False
                result['confluence']['confidence'] = round(result['confluence']['confidence'] * 0.7, 1)
                result['confluence']['signal'] = 'neutral'
                result['confluence']['reason'] = 'Multi-tf misalignment'

    result['multi_tf_aligned'] = tf_aligned
    result['multi_tf'] = {
        'lower': lower_tf,
        'entry': entry_tf,
        'higher': higher_tf,
        'aligned': tf_aligned,
    }

    entry_ma = result.get('indicators', {}).get('ma_alignment')
    higher_sig = result.get('higher_tf', {}).get('signal')
    result['trading_plan'] = validate_trading_plan(
        ind=result.get('indicators', {}),
        mode=mode,
        higher_tf_signal=higher_sig,
        entry_ma=entry_ma,
    )

    signal_card = format_signal_card(result, result['trading_plan'], result.get('higher_tf', {}))
    result['consistency'] = check_consistency(result, result['trading_plan'])

    return {
        'jsonrpc': '2.0',
        'id': req_id,
        'result': {'content': [{'type': 'text', 'text': signal_card}]},
    }


def tool_scan_mode(req_id: Any, mode: str, args: dict) -> dict:
    symbol = args.get('symbol')
    if symbol:
        return tool_generate_signal(req_id, {'symbol': symbol, 'mode': mode})

    limit = args.get('limit', 5)
    pairs = get_pairs_for_mode(mode)
    interval = MODE_TF[mode][1]
    period = MODE_PERIOD.get(mode, '1mo')

    log(f'Scanning {mode} — {len(pairs)} pairs')
    results = []

    for pair in pairs[:15]:
            try:
                df = get_rates(pair.yahoo_ticker, interval, period)
                sdz = get_engine(pair.symbol)
                sdz_result = sdz.update(df)
                analysis = full_analysis(df, mode, pair.symbol, sdz_result=sdz_result)
                score = analysis.get('confluence', {}).get('net_score', 0)
                results.append((score, analysis))
            except Exception as e:
                log(f'  {pair.symbol}: {e}')

    results.sort(key=lambda x: abs(x[0]), reverse=True)
    top = [r[1] for r in results[:limit]]

    card = format_scan_table(top, mode, limit)

    return {
        'jsonrpc': '2.0',
        'id': req_id,
        'result': {'content': [{'type': 'text', 'text': card}]},
    }


def tool_sdz_zones(req_id: Any, args: dict) -> dict:
    symbol = args.get('symbol', '').upper()
    pair = get_pair(symbol)
    if not pair:
        return {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32000, 'message': f'Unknown pair: {symbol}'}}
    sdz = get_engine(pair.symbol)
    status = sdz.get_status()
    zones = sdz.get_zones()
    triggers = sdz.get_triggers()
    lines = [f'SDZ Engine — {symbol}', f'Status: {status["status"]}', f'Regime: {status["regime"]["trend"]}',
             f'ATR: {status["atr"]:.6f}', f'Total zones: {status["total_zones"]}',
             f'Active triggers: {status["active_triggers"]}', '']
    for ztype in ('supply', 'demand'):
        for z in zones.get(ztype, []):
            lines.append(f'{ztype.upper()} zone: {z["zone_low"]:.5f}-{z["zone_high"]:.5f} momentum={z["momentum"]:.1f}×ATR')
    for t in triggers:
        lines.append(f'\nTRIGGER: {t["direction"].upper()} | {t["confirmation"]} | entry={t["entry"]:.5f} sl={t["sl"]:.5f}')
    return {'jsonrpc': '2.0', 'id': req_id, 'result': {'content': [{'type': 'text', 'text': '\n'.join(lines)}]}}


def tool_sdz_scan(req_id: Any, args: dict) -> dict:
    mode = args.get('mode', 'intraday')
    pairs = get_pairs_for_mode(mode)
    interval = MODE_TF[mode][1]
    period = MODE_PERIOD.get(mode, '1mo')
    limit = args.get('limit', 5)
    results = []
    for pair in pairs[:15]:
        try:
            df = get_rates(pair.yahoo_ticker, interval, period)
            sdz = get_engine(pair.symbol)
            sdz_result = sdz.update(df)
            results.append((pair.symbol, sdz_result))
        except Exception as e:
            log(f'SDZ scan {pair.symbol}: {e}')
    results.sort(key=lambda x: x[1].get('total_zones', 0) if x[1] else 0, reverse=True)
    lines = [f'SDZ Scan — {mode.upper()}']
    for sym, r in results[:limit]:
        reg = r.get('regime', {}).get('trend', '?')
        nz = r.get('total_zones', 0)
        nt = len(r.get('triggers', []))
        s = r.get('status', '?')
        lines.append(f'{sym:<12} status={s:<10} zones={nz:<2} triggers={nt:<1} regime={reg}')
    return {'jsonrpc': '2.0', 'id': req_id, 'result': {'content': [{'type': 'text', 'text': '\n'.join(lines)}]}}


def tool_sdz_logs(req_id: Any, args: dict) -> dict:
    symbol = args.get('symbol', '').upper()
    pair = get_pair(symbol)
    if not pair:
        return {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32000, 'message': f'Unknown pair: {symbol}'}}
    n = args.get('n', 10)
    sdz = get_engine(pair.symbol)
    logs = sdz.get_logs(n)
    lines = [f'SDZ Logs — {symbol} (last {len(logs)})']
    for entry in logs:
        lines.append(str(entry))
    return {'jsonrpc': '2.0', 'id': req_id, 'result': {'content': [{'type': 'text', 'text': '\n'.join(lines)}]}}


def tool_journal_list(req_id: Any, args: dict) -> dict:
    limit = args.get('limit', 10)
    symbol = args.get('symbol')
    trades = journal.list_trades(limit=limit, symbol=symbol)
    lines = [f'Journal — Last {len(trades)} Trades']
    lines.append(f'{"ID":<4} {"Date":<12} {"Symbol":<10} {"Mode":<10} {"Signal":<12} {"Conf":<6} {"Outcome":<8}')
    lines.append('-' * 70)
    for t in trades:
        dt = t['created_at'][:10] if t['created_at'] else '?'
        lines.append(f'{t["id"]:<4} {dt:<12} {t["symbol"]:<10} {t["mode"]:<10} '
                     f'{t["signal"]:<12} {t["confidence"]:<6} {t["outcome"]:<8}')
    return {'jsonrpc': '2.0', 'id': req_id, 'result': {'content': [{'type': 'text', 'text': '\n'.join(lines)}]}}


def tool_journal_stats(req_id: Any, args: dict) -> dict:
    days = args.get('days')
    stats = journal.get_stats(days=days)
    period = f'last {days}d' if days else 'all time'
    lines = [f'Journal Stats — {period}']
    lines.append(f'  Total signals: {stats["total"]}')
    lines.append(f'  Closed trades: {stats["closed"]}')
    lines.append(f'  Wins: {stats["wins"]}  |  Losses: {stats["losses"]}  |  Pending: {stats["pending"]}')
    lines.append(f'  Win rate: {stats["win_rate"]}%')
    lines.append('')
    if stats['by_pair']:
        lines.append('By Pair:')
        for sym, d in sorted(stats['by_pair'].items(), key=lambda x: x[1]['total'], reverse=True):
            wr = round(d['wins'] / max(d['wins'] + d['losses'], 1) * 100, 1)
            lines.append(f'  {sym:<10} {d["total"]} trades  {d["wins"]}W/{d["losses"]}L  {wr}% WR')
    lines.append('')
    if stats['by_confidence']:
        lines.append('By Confidence:')
        for score, d in sorted(stats['by_confidence'].items()):
            if d['total'] == 0:
                continue
            wr = round(d['wins'] / max(d['wins'] + d['losses'], 1) * 100, 1)
            lines.append(f'  Score {score:<3} {d["total"]} trades  {d["wins"]}W/{d["losses"]}L  {wr}% WR')
    return {'jsonrpc': '2.0', 'id': req_id, 'result': {'content': [{'type': 'text', 'text': '\n'.join(lines)}]}}


def tool_journal_update(req_id: Any, args: dict) -> dict:
    trade_id = args.get('trade_id')
    outcome = args.get('outcome')
    pnl = args.get('pnl')
    notes = args.get('notes', '')
    if not trade_id or not outcome:
        return {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32000, 'message': 'trade_id and outcome required'}}
    trade = journal.get_trade(trade_id)
    if not trade:
        return {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32000, 'message': f'Trade #{trade_id} not found'}}
    journal.update_outcome(trade_id, outcome, pnl, notes)
    return {'jsonrpc': '2.0', 'id': req_id, 'result': {'content': [{'type': 'text', 'text': f'Journal #{trade_id} updated → {outcome}'}]}}


def tool_journal_export(req_id: Any, args: dict) -> dict:
    path = args.get('path')
    result_path = journal.export_csv(path)
    return {'jsonrpc': '2.0', 'id': req_id, 'result': {'content': [{'type': 'text', 'text': f'CSV exported: {result_path}'}]}}


def tool_journal_report(req_id: Any, args: dict) -> dict:
    days = args.get('days', 7)
    path = journal.generate_report(days=days)
    return {'jsonrpc': '2.0', 'id': req_id, 'result': {'content': [{'type': 'text', 'text': f'Report generated: {path}'}]}}


TOOLS = [
    {
        'name': 'get_pairs',
        'description': 'Get supported trading pairs grouped by category, or filter by category',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'category': {
                    'type': 'string',
                    'enum': ['major', 'cross', 'exotic', 'commodity', 'crypto'],
                    'description': 'Filter by category',
                }
            },
        },
    },
    {
        'name': 'get_rates',
        'description': 'Get OHLCV candles for a pair. Supports 1m,2m,5m,15m,30m,1h,4h,1d,1wk intervals.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'symbol': {'type': 'string', 'description': 'e.g. EUR/USD, XAU/USD, BTC/USD'},
                'interval': {'type': 'string', 'description': 'Timeframe: 1m,5m,15m,1h,4h,1d,1wk'},
                'period': {'type': 'string', 'description': 'Period: 5d,1mo,3mo,6mo,1y,2y,5y'},
                'limit': {'type': 'number', 'description': 'Number of candles'},
            },
            'required': ['symbol'],
        },
    },
    {
        'name': 'get_indicators',
        'description': 'Get all technical indicators for a pair: RSI, MACD, MA, Bollinger, ATR, Stochastic, ADX, OBV, MFI, patterns.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'symbol': {'type': 'string', 'description': 'e.g. EUR/USD'},
                'mode': {'type': 'string', 'enum': ['scalp', 'intraday', 'swing'], 'description': 'Trading mode (affects indicator params)'},
                'interval': {'type': 'string', 'description': 'Timeframe'},
            },
            'required': ['symbol'],
        },
    },
    {
        'name': 'analyze_technical',
        'description': 'Full technical analysis: 5-layer confluence + scoring + SL/TP levels for a single pair.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'symbol': {'type': 'string', 'description': 'e.g. EUR/USD'},
                'mode': {'type': 'string', 'enum': ['scalp', 'intraday', 'swing'], 'description': 'Trading mode'},
                'interval': {'type': 'string', 'description': 'Override timeframe'},
            },
            'required': ['symbol'],
        },
    },
    {
        'name': 'generate_signal',
        'description': 'Generate complete trade signal: multi-timeframe analysis + entry zone + SL/TP + confidence score + confluence.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'symbol': {'type': 'string', 'description': 'e.g. EUR/USD'},
                'mode': {'type': 'string', 'enum': ['scalp', 'intraday', 'swing'], 'description': 'Trading mode'},
            },
            'required': ['symbol'],
        },
    },
    {
        'name': 'scan_markets',
        'description': 'Scan all pairs in a mode and rank by signal strength.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'mode': {'type': 'string', 'enum': ['scalp', 'intraday', 'swing']},
                'limit': {'type': 'number', 'description': 'Number of top signals'},
            },
        },
    },
    {
        'name': 'scalp',
        'description': f'Fast scalping scan — 11 pairs M5/M15. {MODE_HELP["scalp"]}',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'symbol': {'type': 'string', 'description': 'Optional: single pair analysis'},
                'limit': {'type': 'number', 'description': 'Top N signals'},
            },
        },
    },
    {
        'name': 'intraday',
        'description': f'Intraday analysis — 17 pairs H1. {MODE_HELP["intraday"]}',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'symbol': {'type': 'string', 'description': 'Optional: single pair analysis'},
                'limit': {'type': 'number', 'description': 'Top N signals'},
            },
        },
    },
    {
        'name': 'swing',
        'description': f'Swing analysis — 32 pairs D1. {MODE_HELP["swing"]}',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'symbol': {'type': 'string', 'description': 'Optional: single pair analysis'},
                'limit': {'type': 'number', 'description': 'Top N signals'},
            },
        },
    },
    {
        'name': 'sdz_zones',
        'description': 'View active SDZ zones and entry triggers for a symbol.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'symbol': {'type': 'string', 'description': 'e.g. EUR/USD'},
            },
            'required': ['symbol'],
        },
    },
    {
        'name': 'sdz_scan',
        'description': 'Scan all pairs in a mode for SDZ zone activity and triggers.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'mode': {'type': 'string', 'enum': ['scalp', 'intraday', 'swing']},
                'limit': {'type': 'number', 'description': 'Number of top results'},
            },
        },
    },
    {
        'name': 'sdz_logs',
        'description': 'View SDZ engine logs for a symbol.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'symbol': {'type': 'string', 'description': 'e.g. EUR/USD'},
                'n': {'type': 'number', 'description': 'Number of log entries'},
            },
            'required': ['symbol'],
        },
    },
    {
        'name': 'journal_list',
        'description': 'View recent journal entries. Optionally filter by symbol.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'limit': {'type': 'number', 'description': 'Number of entries (default 10)'},
                'symbol': {'type': 'string', 'description': 'Filter by symbol e.g. EUR/USD'},
            },
        },
    },
    {
        'name': 'journal_stats',
        'description': 'View performance statistics from the trading journal.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'days': {'type': 'number', 'description': 'Period in days (default: all time)'},
            },
        },
    },
    {
        'name': 'journal_update',
        'description': 'Update the outcome of a journal entry after trade is closed.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'trade_id': {'type': 'number', 'description': 'Journal entry ID'},
                'outcome': {'type': 'string', 'enum': ['win', 'loss', 'pending', 'cancel'], 'description': 'Trade outcome'},
                'pnl': {'type': 'number', 'description': 'Profit/loss in pips or USD'},
                'notes': {'type': 'string', 'description': 'Optional notes'},
            },
            'required': ['trade_id', 'outcome'],
        },
    },
    {
        'name': 'journal_export',
        'description': 'Export journal to CSV file.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'path': {'type': 'string', 'description': 'Output file path (optional, auto-generated)'},
            },
        },
    },
    {
        'name': 'journal_report',
        'description': 'Generate a Markdown trading report for the specified period.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'days': {'type': 'number', 'description': 'Period in days (default 7)'},
            },
        },
    },
]


def main():
    log('[SIGNAL ENGINE] Starting MCP server on stdio...')
    log(f'[SIGNAL ENGINE] {len(PAIRS)} pairs loaded')
    log('[SIGNAL ENGINE] Modes: scalp (M1/M5), intraday (H1), swing (D1)')
    log(f'[SIGNAL ENGINE] Journal: {len(TOOLS)} tools | SQLite at {journal.DB_PATH}')
    log('[SIGNAL ENGINE] Journal report: journal_stats, journal_list, journal_update, journal_export')

    buffer = ''
    for line in sys.stdin:
        if not running:
            break
        buffer += line
        try:
            req = json.loads(buffer)
            buffer = ''
            response = handle_request(req)
            if response:
                send_json(response)
        except json.JSONDecodeError:
            continue
        except Exception as e:
            log(f'Fatal: {traceback.format_exc()}')
            send_json({'jsonrpc': '2.0', 'error': {'code': -32000, 'message': str(e)}})


def shutdown(*_):
    global running
    running = False
    log('[SIGNAL ENGINE] Shutting down...')
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    main()
