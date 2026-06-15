# Trading Signal Engine v2.0

AI-powered intraday/scalp/swing signal generator — hybrid rule+AI approach.
SDZ Price-Action Engine (engulfing-based S&D zones) + 5-Layer Confluence + Auto Journal.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Step-by-Step Trading Workflow](#step-by-step-trading-workflow)
3. [Command Reference](#command-reference)
4. [Interpreting Signal Cards](#interpreting-signal-cards)
5. [Journal Management](#journal-management)
6. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
opencode CLI
    │
    ▼
MCP Server (signal_server.py) — 17 tools
    │
    ├── Data Layer (data.py + pairs.py)
    │     └── yfinance / Binance / gold-api.com → OHLCV
    │
    ├── SDZ Engine (sdz_engine.py)
    │     └── Engulfing detection → Momentum validation → Zone hierarchy → Triggers
    │
    ├── Analysis Layer (analysis.py + indicators.py)
    │     └── 5-Layer Confluence + Trading Plan + SL/TP
    │
    ├── Display Layer (display.py)
    │     └── ANSI signal cards + scan tables
    │
    └── Journal Layer (journal.py) — NEW
          └── SQLite DB → Stats → CSV Export → Markdown Report
```

---

## Step-by-Step Trading Workflow

### Phase 0: Startup

```bash
# 1. Start opencode (auto-launches MCP server)
opencode

# Output:
# [SIGNAL ENGINE] 31 pairs loaded
# [SIGNAL ENGINE] Journal: 17 tools | SQLite at .../trades.db
```

Server siap digunakan. SDZ engine otomatis restore state dari sesi sebelumnya (zones, ATR, regime tidak hilang).

---

### Phase 1: Market Scan — Cari Peluang

Tujuan: Menemukan pair dengan sinyal terkuat di mode yang sesuai.

```bash
# Scan semua pair intraday (H1) — ranking by net score
intraday
# Output: Top 5 pairs sorted by signal strength

# Scan scalp (M5) — untuk day trading cepat
scalp

# Scan swing (D1) — untuk posisi multi-hari
swing
```

**Output contoh:**
```
╔══ SIGNAL SCAN · INTRADAY (H1) ═══════════════════╗
║  Top 5 signals sorted by strength                ║
╚═══════════════════════════════════════════════════╝

  #1 ▲ BTC/USD  |  BUY  |  6.5/10 (KUAT)  |  RR ✓
     Price: $66397  |  TP1: $67485  |  SL: $65853
     MA: bullish_aligned  |  RSI: 58.73

  #2 ▲ USD/CAD  |  BUY  |  6.3/10 (KUAT)  |  RR ✓
     ...
```

**Filter cepat:**
- Confidence ≥ 6 → layak dipertimbangkan
- Confidence ≥ 8 → high conviction
- RR ✓ = risk/reward terpenuhi
- Perhatikan MA alignment (bullish/bearish)

---

### Phase 2: Analisis Detail — Konfirmasi Sinyal

Tujuan: Memvalidasi sinyal dengan 5-layer confluence + trading plan + multi-TF.

```bash
# Analisis lengkap pair spesifik
intraday BTC/USD
# atau
swing XAUUSD
# atau
scalp GBPJPY
```

**Apa yang kamu dapatkan:**

| Section | Fungsi |
|---------|--------|
| **Signal Header** | Arah (BUY/SELL/NEUTRAL) + Confidence 0-10 + ATR |
| **Journal ID** | Nomor entry di database (auto-save) |
| **Trading Plan** | 5 kondisi PASS/FAIL — minimal 4/5 untuk entry |
| **5-Layer Confluence** | Trend, Momentum, Volatility, Volume, SDZ |
| **SDZ Engine Status** | Market regime + zone aktif + trigger |
| **Execution Plan** | Entry zone, SL, TP1, TP2, RR ratio |
| **Higher TF Context** | Alignment check (H4/D1) |
| **Verdict** | EKSEKUSI / WATCH LIST / SKIP |

**Cara membaca 5-Layer:**

```
TREND       [+2] EMA aligned bullish, ADX 42 (strong)  → BULLISH
MOMENTUM    [+0] RSI 58 (neutral)                       → NETRAL
VOLATILITY  [+0] Price mid BB                           → NETRAL
VOLUME      [+0] OBV flat                               → NETRAL
SDZ         [+0] No trigger aktif                        → NETRAL
```

- **Score positif** → layer mendukung BUY
- **Score negatif** → layer mendukung SELL
- **Semakin banyak layer sepakat** → confidence semakin tinggi

**Cara membaca Trading Plan:**

```
✅ Trend Filter    — EMA20 > EMA50 (bullish aligned)
✅ Momentum Filter — RSI dalam 30-70 range
❌ Timing Filter   — SDZ trigger belum aktif (SDL fallback bisa gantikan)
✅ Context Filter  — H4 searah
✅ Risk Filter     — SL ≤ 2×ATR
─────────────────────────────────
Rule: Entry hanya jika MINIMAL 4/5 kondisi terpenuhi (saat ini 4/5)
```

Jika timing filter satu-satunya yang gagal tapi **SDL fallback** aktif → tetap dianggap PASS.

---

### Phase 3: Eksekusi — Entry Manual

Tujuan: Entry sesuai rencana dengan risk management.

Setelah verdis **EKSEKUSI**, lakukan entry manual di broker:

```bash
# Contoh signal:
Verdict: EKSEKUSI: Setup memenuhi syarat. Entry sesuai rencana.

Execution Plan:
  Entry Zone:  $66383.84 - $66410.40
  Stop Loss:   $65853.20  (-0.80%)
  TP1:         $67484.96  (+1.66%)   RR: 2.0:1  [PASS]
  TP2:         $68028.88  (+2.48%)   RR: 3.0:1
```

**Aturan entry:**
1. Gunakan **limit order** di entry zone (bukan market order)
2. SL sesuai level yang diberikan — jangan dimundurin
3. TP1 = take profit minimal (RR 1:2 untuk intraday)
4. TP2 = target lanjutan (bisa trailing setelah TP1 hit)
5. Jangan over-leverage — hitung posisi berdasarkan risk 1-2% equity

**Jika tidak yakin:**
- Verdis **WATCH LIST** → tunggu konfirmasi tambahan (SDL trigger atau price action)
- Verdis **SKIP** → jangan entry, cari pair lain

---

### Phase 4: Journal — Catat Hasil Trade

Tujuan: Melacak performa untuk evaluasi.

**Setelah entry dilakukan (opsional):**
```bash
# Catat outcome setelah trade closed
journal_update trade_id=1 outcome=win pnl=50.5 notes="TP1 hit, bagus"
journal_update trade_id=1 outcome=loss pnl=-30 notes="SL tersentuh, salah timing"
journal_update trade_id=1 outcome=cancel notes="Batal entry, harga skip"
```

**Parameter:**
- `trade_id` — nomor dari Journal ID di signal card
- `outcome` — `win` / `loss` / `cancel`
- `pnl` — profit/loss dalam pip atau USD (opsional)
- `notes` — catatan evaluasi (opsional)

---

### Phase 5: Review — Evaluasi Performa

Tujuan: Analisis mingguan untuk improvement.

```bash
# Lihat performa terkini
journal_stats
# Output:
#   Total signals: 24
#   Closed trades: 21  |  Wins: 15  |  Losses: 6
#   Win rate: 71.4%
#   By Pair:
#     BTC/USD    8 trades  6W/2L  75.0% WR
#     USD/CAD    5 trades  4W/1L  80.0% WR

# Statistik periode tertentu (7 hari terakhir)
journal_stats days=7

# Lihat daftar trade
journal_list
journal_list limit=20 symbol=BTC/USD

# Export ke CSV untuk analisis Excel
journal_export
# Output: CSV exported: ~/.trading-signal-engine/journal/trades_export_20260616.csv

# Generate laporan markdown mingguan
journal_report days=7
# Output: Report: ~/.trading-signal-engine/reports/report_20260616.md
```

**Interpretasi Statistik:**

| Metric | Bagus | Perlu Waspada |
|--------|-------|---------------|
| Win Rate | >65% | <50% |
| By Confidence 8-10 | >80% WR | <60% WR — sistem perlu tuning |
| By Confidence 6-7 | >60% WR | <50% WR — terlalu agresif |
| Avg RR | >2:1 | <1.5:1 — risk/reward tidak optimal |

---

## Command Reference

### Analysis & Signals

| Perintah | Fungsi | Contoh |
|----------|--------|--------|
| `intraday` | Scan semua pair H1, ranking by score | `intraday` |
| `intraday EURUSD` | Single pair analysis H1 | `intraday BTC/USD` |
| `scalp` | Scan scalp M5 | `scalp` |
| `scalp BTCUSD` | Single pair scalp | `scalp GBPJPY` |
| `swing` | Scan swing D1 | `swing` |
| `swing XAUUSD` | Single pair swing | `swing AUDUSD` |
| `pairs` | List semua 31 pair | `pairs` |
| `analize EURUSD intraday` | 5-layer breakdown | `analize BTCUSD swing` |
| `sinyal EURUSD swing` | Full signal + trading plan | `sinyal AUDUSD intraday` |

### SDZ Engine Tools

| Perintah | Fungsi | Contoh |
|----------|--------|--------|
| `sdz_zones EURUSD` | Lihat zone aktif + trigger | `sdz_zones BTC/USD` |
| `sdz_scan intraday` | Scan SDZ zone density | `sdz_scan swing` |
| `sdz_logs BTCUSD` | History engine | `sdz_logs EUR/USD n=20` |

### Journal Tools

| Perintah | Fungsi | Contoh |
|----------|--------|--------|
| `journal_list` | 10 trade terakhir | `journal_list limit=20 symbol=BTC/USD` |
| `journal_stats` | Performa all time | `journal_stats days=7` |
| `journal_update trade_id=1 outcome=win pnl=50` | Update hasil trade | `journal_update trade_id=3 outcome=loss pnl=-20 notes="SL hit"` |
| `journal_export` | Export CSV | `journal_export path=~/Desktop/trades.csv` |
| `journal_report` | Generate markdown report | `journal_report days=14` |

---

## Interpreting Signal Cards

### Confidence Score

| Score | Label | Action |
|-------|-------|--------|
| 8-10 | SANGAT KUAT | High conviction entry. Multi-TF aligned. |
| 6-7.9 | KUAT | Standard entry. Sebagian besar layer setuju. |
| 4-5.9 | MODERAT | Watch list. Butuh konfirmasi tambahan. |
| 2-3.9 | LEMAH | Skip / reduce size. Banyak konflik layer. |
| 0-1.9 | TIDAK LAYAK | No trade. Tidak ada konfluensi. |

### Verdict

| Verdict | Arti | Action |
|---------|------|--------|
| ✅ **EKSEKUSI** | 4/5 plan lolos + RR ok | Entry sesuai rencana |
| ⏳ **WATCH LIST** | TA bagus tapi plan < 4/5 | Tunggu konfirmasi lanjutan |
| ❌ **SKIP** | TA lemah + plan tidak lolos | Cari pair lain |

### SDZ vs SDL — Timing Filter

| Status | Arti |
|--------|------|
| **SDZ active + trigger** | Supply/demand zone rejection confirmed — timing optimal |
| **SDL active + trigger** | Fallback: S/R proximity + reversal — timing cukup |
| **No trigger** | Tidak ada konfirmasi price action — timing tidak terpenuhi |

> **Catatan:** SDL fallback otomatis aktif saat SDZ engine masih warming up. Scoring SDL = ±2 (vs SDZ = ±4). Setelah engine warm, SDZ yang digunakan.

---

## Journal Management

### Database Location
```
~/.trading-signal-engine/
├── journal/trades.db     # SQLite — semua signal
├── journal/*.csv         # Export file
├── reports/*.md          # Markdown reports
└── sdz/*.json            # SDZ engine state persist
```

### Auto-Save
Setiap kali kamu menjalankan `intraday BTC/USD` (atau perintah signal lainnya), sistem otomatis:
1. Generate signal card
2. Save ke SQLite
3. Assign Journal ID
4. Tampilkan di output: `Journal ID: #4`

### Lifecycle Trade

```
Signal Generated (auto-save, pending)
    │
    ├── Kamu entry? → Biarkan pending
    │       │
    │       ├── Trade closed WIN  → journal_update outcome=win pnl=...
    │       ├── Trade closed LOSS → journal_update outcome=loss pnl=...
    │       └── Batal entry       → journal_update outcome=cancel
    │
    └── Kamu skip? → Biarkan pending (bisa direview nanti)
```

---

## Troubleshooting

| Masalah | Penyebab | Solusi |
|---------|----------|--------|
| `SDZ engine not ready` | Baru restart, engine warming up | Jalankan 1-2x update dulu. State persist akan restore dari sesi sebelumnya. |
| `No data for XXX` | yfinance timeout / pair tidak valid | Coba lagi. Pastikan symbol benar (EURUSD bukan EUR/USD di parameter). |
| `RR 0:1` | ATR = 0 — data tidak cukup | Periksa period (swing butuh 2y, intraday 1mo). |
| `Multi-TF misaligned` | H1 vs H4/H1 vs D1 tidak searah | Confidence otomatis di-downgrade 30%. Pertimbangkan timeframe alignment. |
| Journal error | SQLite corrupted | Hapus `~/.trading-signal-engine/journal/trades.db` — akan auto-create ulang. |

---

## Requirements

- Python 3.13+
- opencode CLI
- Packages: yfinance, ta, mcp (built-in opencode), httpx, pandas, numpy

```
pip install yfinance ta httpx pandas numpy --break-system-packages
```

---

*Methodology: Hybrid Rule+AI | 5-Layer Confluence + SDZ Price-Action + 5-Condition Trading Plan*
*Data: yfinance (forex) | gold-api.com (XAU/XAG) | Binance (crypto)*
*Entry manual | SL/TP berdasarkan ATR | Risk management wajib*
