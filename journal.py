"""
Trading Journal — SQLite + Markdown Report
Tracks every signal generated, outcome, and performance stats.
"""
import json
import os
import sqlite3
import csv
from datetime import datetime, timedelta

DB_DIR = os.path.expanduser('~/.trading-signal-engine/journal')
DB_PATH = os.path.join(DB_DIR, 'trades.db')
REPORT_DIR = os.path.expanduser('~/.trading-signal-engine/reports')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    mode TEXT NOT NULL,
    signal TEXT NOT NULL,
    confidence REAL NOT NULL,
    price REAL,
    atr REAL,
    layer_scores TEXT,
    trading_plan TEXT,
    entry_zone_low REAL,
    entry_zone_high REAL,
    sl REAL,
    tp1 REAL,
    tp2 REAL,
    rr REAL,
    outcome TEXT DEFAULT 'pending',
    pnl REAL,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_created ON trades(created_at);
CREATE INDEX IF NOT EXISTS idx_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_outcome ON trades(outcome);
'''


def _connect():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.executescript(SCHEMA)
    return conn


def save_trade(signal_data: dict) -> int:
    """Save a generated signal to journal. Returns trade ID."""
    conn = _connect()
    try:
        now = datetime.utcnow().isoformat()
        layers = signal_data.get('confluence', {}).get('breakdown', {})
        layer_scores = {k: v.get('score', 0) for k, v in layers.items()}
        tp = signal_data.get('trading_plan', {})
        exec_plan = signal_data.get('execution', {})
        conn.execute('''
            INSERT INTO trades
                (symbol, mode, signal, confidence, price, atr,
                 layer_scores, trading_plan,
                 entry_zone_low, entry_zone_high, sl, tp1, tp2, rr,
                 created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            signal_data.get('symbol', '?'),
            signal_data.get('mode', 'intraday'),
            signal_data.get('confluence', {}).get('signal', 'neutral'),
            signal_data.get('confluence', {}).get('confidence', 0),
            signal_data.get('price'),
            signal_data.get('indicators', {}).get('atr'),
            json.dumps(layer_scores),
            json.dumps({k: v.get('pass') for k, v in tp.get('conditions', {}).items()}),
            exec_plan.get('entry_zone_low'),
            exec_plan.get('entry_zone_high'),
            exec_plan.get('sl'),
            exec_plan.get('tp1'),
            exec_plan.get('tp2'),
            exec_plan.get('rr1'),
            now,
        ))
        conn.commit()
        cursor = conn.execute('SELECT last_insert_rowid()')
        return cursor.fetchone()[0]
    finally:
        conn.close()


def update_outcome(trade_id: int, outcome: str, pnl: float = None, notes: str = ''):
    if outcome not in ('win', 'loss', 'pending', 'cancel'):
        raise ValueError('outcome must be win/loss/pending/cancel')
    conn = _connect()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute('''
            UPDATE trades SET outcome=?, pnl=?, notes=?, updated_at=?
            WHERE id=?
        ''', (outcome, pnl, notes, now, trade_id))
        conn.commit()
    finally:
        conn.close()


def list_trades(limit: int = 10, symbol: str = None) -> list:
    conn = _connect()
    try:
        if symbol:
            rows = conn.execute(
                'SELECT * FROM trades WHERE symbol=? ORDER BY created_at DESC LIMIT ?',
                (symbol, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM trades ORDER BY created_at DESC LIMIT ?',
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_trade(trade_id: int) -> dict:
    conn = _connect()
    try:
        r = conn.execute('SELECT * FROM trades WHERE id=?', (trade_id,)).fetchone()
        return dict(r) if r else {}
    finally:
        conn.close()


def get_stats(days: int = None) -> dict:
    """Return aggregated performance stats."""
    conn = _connect()
    try:
        where_clause = ''
        params = ()
        if days:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            where_clause = 'WHERE created_at >= ?'
            params = (cutoff,)

        def q(sql_after_where):
            if not sql_after_where:
                return conn.execute(
                    f'SELECT COUNT(*) FROM trades {where_clause}', params
                ).fetchone()[0]
            if where_clause:
                return conn.execute(
                    f'SELECT COUNT(*) FROM trades {where_clause} {sql_after_where}', params
                ).fetchone()[0]
            # No date filter — strip leading AND
            clean = sql_after_where.replace('AND ', '', 1)
            return conn.execute(
                f'SELECT COUNT(*) FROM trades WHERE {clean}'
            ).fetchone()[0]

        total = q('')
        closed = q('AND outcome IN ("win","loss")')
        wins = q('AND outcome="win"')
        losses = q('AND outcome="loss"')
        pending = q('AND outcome="pending"')

        win_rate = round(wins / closed * 100, 1) if closed > 0 else 0.0

        by_pair = {}
        pair_rows = conn.execute(
            f'SELECT symbol, outcome FROM trades {where_clause}', params
        ).fetchall()
        for r in pair_rows:
            s = r[0]
            if s not in by_pair:
                by_pair[s] = {'total': 0, 'wins': 0, 'losses': 0}
            by_pair[s]['total'] += 1
            if r[1] == 'win':
                by_pair[s]['wins'] += 1
            elif r[1] == 'loss':
                by_pair[s]['losses'] += 1

        by_confidence = {str(i): {'total': 0, 'wins': 0, 'losses': 0}
                         for i in range(0, 11)}
        conf_rows = conn.execute(
            f'SELECT confidence, outcome FROM trades {where_clause}', params
        ).fetchall()
        for r in conf_rows:
            bucket = str(int(r[0]))
            if bucket in by_confidence:
                by_confidence[bucket]['total'] += 1
                if r[1] == 'win':
                    by_confidence[bucket]['wins'] += 1
                elif r[1] == 'loss':
                    by_confidence[bucket]['losses'] += 1

        return {
            'total': total,
            'closed': closed,
            'wins': wins,
            'losses': losses,
            'pending': pending,
            'win_rate': win_rate,
            'by_pair': by_pair,
            'by_confidence': by_confidence,
            'days': days,
        }
    finally:
        conn.close()


def export_csv(path: str = None):
    if not path:
        path = os.path.join(DB_DIR, f'trades_export_{datetime.now().strftime("%Y%m%d")}.csv')
    conn = _connect()
    try:
        rows = conn.execute('''
            SELECT id, created_at, symbol, mode, signal, confidence, price,
                   outcome, pnl, rr, notes
            FROM trades ORDER BY created_at DESC
        ''').fetchall()
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['ID', 'Date', 'Symbol', 'Mode', 'Signal', 'Confidence',
                        'Price', 'Outcome', 'PnL', 'RR', 'Notes'])
            for r in rows:
                w.writerow(r)
        return path
    finally:
        conn.close()


def generate_report(days: int = 7) -> str:
    """Generate markdown trading report for the period."""
    stats = get_stats(days=days)
    now = datetime.utcnow()
    period = f'{now.strftime("%Y-%m-%d")} (last {days}d)'

    lines = []
    lines.append(f'# Trading Report — {period}')
    lines.append('')
    lines.append('## Performance Summary')
    lines.append('')
    lines.append(f'| Metric | Value |')
    lines.append(f'|--------|-------|')
    lines.append(f'| Total Signals | {stats["total"]} |')
    lines.append(f'| Closed Trades | {stats["closed"]} |')
    lines.append(f'| Wins | {stats["wins"]} |')
    lines.append(f'| Losses | {stats["losses"]} |')
    lines.append(f'| Pending | {stats["pending"]} |')
    lines.append(f'| **Win Rate** | **{stats["win_rate"]}%** |')
    lines.append('')

    if stats['by_pair']:
        lines.append('## By Pair')
        lines.append('')
        lines.append('| Pair | Total | Wins | Losses | Win Rate |')
        lines.append('|------|-------|------|--------|----------|')
        for sym, d in sorted(stats['by_pair'].items(), key=lambda x: x[1]['total'], reverse=True):
            wr = round(d['wins'] / max(d['wins'] + d['losses'], 1) * 100, 1)
            lines.append(f'| {sym} | {d["total"]} | {d["wins"]} | {d["losses"]} | {wr}% |')
        lines.append('')

    if stats['by_confidence']:
        lines.append('## By Confidence Score')
        lines.append('')
        lines.append('| Score | Total | Wins | Losses | Win Rate |')
        lines.append('|-------|-------|------|--------|----------|')
        for score, d in sorted(stats['by_confidence'].items()):
            if d['total'] == 0:
                continue
            wr = round(d['wins'] / max(d['wins'] + d['losses'], 1) * 100, 1)
            lines.append(f'| {score} | {d["total"]} | {d["wins"]} | {d["losses"]} | {wr}% |')
        lines.append('')

    recent = list_trades(limit=5)
    if recent:
        lines.append('## Latest Trades')
        lines.append('')
        lines.append('| ID | Date | Symbol | Mode | Signal | Conf | Outcome |')
        lines.append('|----|------|--------|------|--------|------|---------|')
        for t in recent:
            dt = t['created_at'][:10] if t['created_at'] else '?'
            lines.append(
                f'| {t["id"]} | {dt} | {t["symbol"]} | {t["mode"]} | '
                f'{t["signal"]} | {t["confidence"]} | {t["outcome"]} |'
            )
        lines.append('')

    lines.append('---')
    lines.append(f'*Generated: {now.strftime("%Y-%m-%d %H:%M UTC")}*')
    lines.append('*Trading Signal Engine v2.0 — SDZ Price Action*')

    report = '\n'.join(lines)
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, f'report_{now.strftime("%Y%m%d")}.md')
    with open(path, 'w') as f:
        f.write(report)
    return path
