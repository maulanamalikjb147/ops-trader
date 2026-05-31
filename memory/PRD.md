# Signal Bot - PRD (Product Requirements Document)

**Last Updated**: 2026-05-31 (OKX-only + WebSocket streaming + Config-synced pair selector)
**Status**: Production-ready

---

## Problem Statement
Build a personal-use crypto trading signal system with Bloomberg Terminal-style web dashboard, automated signal generation, demo/live trading, Telegram notifications, and Notion logging.

---

## Architecture

### Tech Stack
- **Frontend**: React.js (Bloomberg Terminal dark theme, JetBrains Mono)
- **Backend**: FastAPI (Python) on port 8001
- **Database**: MongoDB (local)
- **Auth**: JWT (httponly cookies), admin seeded at startup
- **Exchange**: ccxt library (live) + DemoExchange (paper trading via OKX)
- **Notifications**: python-telegram-bot v22, notion-client
- **Scheduler**: asyncio background tasks (swing/scalp/hybrid loops)

### Admin Credentials
- **Username**: opsculun
- **Password**: @Traderculun147

---

## What's Been Implemented

### Session 1 (2026-05-30) - MVP
- Bloomberg Terminal dark UI
- Signal generation engine (swing/scalp/hybrid)
- Demo exchange (paper trading)
- OKX live exchange support
- Telegram bot integration
- Notion trading journal integration (auto-create database)
- Position monitoring (TP/SL/BEP detection)
- Performance analytics page
- Settings page (bot config, exchanges, integrations, controls)
- TradingView charts

### Session 2 (2026-05-31) - OKX-Only + WebSocket
1. **Removed Binance/Bybit APIs** - DemoExchange.get_current_price() now uses OKX via data_fetcher.get_current_price(). No more Binance 451 errors.
2. **OKX WebSocket Price Stream** - Added `OKXWebSocketClient` in data_fetcher.py. Subscribes to OKX SWAP tickers via `wss://ws.okx.com:8443/ws/v5/public`. Started on server startup, reconnects on disconnect. REST fallback if WS not yet seeded.
3. **Dashboard pair selector** - Now loads `coins_to_scan` from `/api/config` instead of hardcoded list. Updates automatically when settings change.
4. **Market scanner** - Removed Binance/Bybit functions, OKX-only.
5. **TradingView chart** - Changed default prefix from BINANCE to OKX for demo/unknown exchanges.
6. **Bot status** - Added `okx_ws_connected` and `okx_ws_subscribed` fields.
7. **WS re-subscribe** - When coins_to_scan is updated via PUT /config, new coins are subscribed to OKX WS automatically.

---

## Notion Integration Guide
User does NOT need to create Notion database manually. The app auto-creates it.

### Steps:
1. Go to **notion.so/my-integrations** → Create new integration → Copy Secret key
2. Open a Notion page and share it with your integration (click "..." → "Add connections")
3. In app: Settings → INTEGRATIONS → paste API key
4. Click **⚡ AUTO-CREATE DATABASE** → paste parent page URL
5. Bot will auto-create "Trading Journal" database with all 20 columns

### Auto-created columns:
| Column | Type | Description |
|--------|------|-------------|
| Pair | Title | e.g. "BTC/USDT LONG" |
| Side | Select | LONG / SHORT |
| Trading Mode | Select | swing / scalp / hybrid |
| Exchange | Select | demo / okx |
| Entry | Number | Entry price |
| TP1, TP2 | Number | Take profit levels |
| SL | Number | Stop loss |
| Score | Number | Signal confidence score |
| Result | Select | OPEN / WIN / LOSS / BEP / DAILY_SUMMARY |
| Close Reason | Select | TP1 / TP2 / SL / BEP / MANUAL |
| BEP Activated | Checkbox | Break-even activated |
| Date | Date | Signal created at |
| Margin USDT | Number | Position margin |
| Leverage | Number | Leverage used |
| Profit USDT | Number | PNL in USD |
| PNL USDT | Number | Same as profit |
| PNL Percent | Number | PNL percentage |
| R Value | Number | Risk-reward multiple |
| Close Price | Number | Exit price |
| Hold Duration | Text | e.g. "45m" |

---

## Prioritized Backlog

### P0 (Critical)
- All core features working ✓

### P1 (Nice to have)
- WS price display widget on dashboard showing live OKX prices
- Add `okx_ws_connected` status in Settings > CONTROLS > INTEGRATIONS STATUS

### P2 (Future)
- Multiple exchange support for signal scanning
- Backtesting mode
- Mobile responsive UI

---

## Next Tasks
- None blocking - all requested features implemented and tested
