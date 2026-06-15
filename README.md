# Trading Signal Engine

Free, AI-powered intraday/scalp/swing signal generator combining rule-based technical analysis (5-layer confluence + Supply & Demand + FVG + trend structure) with AI interpretation via opencode.

## Features

- **5-Layer Confluence**: Trend, Momentum, Volatility, Volume, Pattern
- **Structural Analysis**: Market structure (HH/HL), Supply & Demand zones, Fair Value Gaps
- **3 Trading Modes**: Scalp (M1/M5/M15), Intraday (H1), Swing (D1)
- **31 Pairs**: Major forex, crosses, exotics, gold, crypto
- **Trading Plan Validator**: 5-condition PASS/FAIL checklist
- **Data Sources**: yfinance (forex) + gold-api.com (XAU/XAG) + Binance data (crypto)
- **No API keys required** for forex/crypto

## Architecture

```
signal_server.py   — MCP server (9 tools → formatted text)
display.py         — ANSI-colored signal cards, scan tables
analysis.py        — 5-layer confluence + trading plan validator
indicators.py      — TA indicators + S&D, FVG, market structure
pairs.py           — 31 pairs config
data.py            — yfinance fetcher + cache
```

## Usage

Via opencode CLI after connecting the MCP server:

- `/intraday` — scan all intraday pairs
- `/intraday EURUSD` — single pair analysis
- `/scalp` — fast scalping scan
- `/swing XAUUSD` — swing analysis
- `/analyze EURUSD` — full technical analysis

## Requirements

- Python 3.13+
- opencode CLI
- Packages: yfinance, ta, mcp, httpx, pandas, numpy
