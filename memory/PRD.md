# Signal Bot - PRD (Product Requirements Document)

**Last Updated**: 2026-05-30
**Status**: MVP Complete + All Requested Features Implemented

### Latest Change (2026-05-30)
- Added "Load Top Futures Pairs" feature in Settings → COINS TO SCAN section.
  - New backend: `/api/market/top-pairs?exchange=binance|bybit&limit=N` (in `market_scanner.py`).
  - Uses **Binance Futures** (fapi.binance.com) for binance/demo/okx/bitget active exchanges.
  - Uses **Bybit Linear (USDT perpetual)** for bybit / bybit_testnet active exchanges.
  - Sorted by 24h transaction volume (highest first), perpetual contracts only.
  - UI: 3 buttons (LOAD TOP 20 / LOAD TOP 50 / TOP 100) + CLEAR. Auto-selects exchange source based on `active_exchange`. Confirmed working with 50 pairs loaded from Binance Futures.

---

## Problem Statement
Build a personal-use crypto trading signal system similar to the MASTER_PROMPT_SIGNAL_BOT.md specification, with Bloomberg Terminal-style web dashboard, automated signal generation, demo/live trading, Telegram notifications, and Notion logging.

---

## Architecture

### Tech Stack
- **Frontend**: React.js (Bloomberg Terminal dark theme, JetBrains Mono)
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Cache**: Redis (in-memory fallback)
- **Auth**: JWT (httponly cookies)
- **Exchange**: ccxt library (live) + DemoExchange (paper trading)
- **Notifications**: python-telegram-bot v22, notion-client
- **Scheduler**: APScheduler (asyncio)

### Key Files
```
/app/backend/
├── server.py           - FastAPI + all routes + WebSocket
├── models.py           - Pydantic models
├── auth.py             - JWT auth utilities
├── data_fetcher.py     - External API fetching (Fear&Greed, Binance, Bybit)
├── signal_engine.py    - Swing/Scalp/Hybrid scoring
├── exchange_handler.py - RealExchange (ccxt) + DemoExchange
├── position_monitor.py - Real-time TP/SL/BEP detection
├── telegram_bot.py     - Telegram notifications
├── notion_sync.py      - Notion database sync
└── scheduler.py        - Signal scanning orchestrator

/app/frontend/src/
├── App.js              - Router + auth protection
├── store/useStore.js   - Zustand global state + WebSocket
├── pages/
│   ├── Login.js, Register.js
│   ├── Dashboard.js    - TradingView chart + positions
│   ├── Signals.js      - Signal history + filters
│   ├── Performance.js  - Equity curve + KPI cards
│   └── Settings.js     - All config + exchanges + integrations
└── components/
    ├── Layout.js       - Top bar + nav + stats
    ├── PositionCard.js - Live PNL + INST TP/SL/BEP
    ├── SignalCard.js   - Signal display
    └── SignalLog.js    - Terminal-style feed
```

---

## Core Requirements (Implemented)

### Authentication
- [x] Login with username/password (opsculun/@Traderculun147)
- [x] Register new users
- [x] JWT httponly cookies
- [x] Admin seeding on startup

### Signal Engine
- [x] Swing mode (4H/1D, score 4/5)
- [x] Scalp mode (1m/5m, score 3/5)
- [x] Hybrid mode (15m/1H/4H, score 4/5)
- [x] Data sources: Fear&Greed, Funding Rate, Volume, EMA, CEX Flow
- [x] Auto scan with configurable intervals

### Trading
- [x] Demo mode (paper trading, real prices from Binance)
- [x] Live mode via ccxt (Binance/Bybit/OKX/Bitget)
- [x] Max open positions limit
- [x] Max total margin limit
- [x] Configurable leverage

### Position Management
- [x] **INST TP** = market close at TP price (not limit)
- [x] **INST SL** = market close at SL price (not limit)
- [x] **SL→BEP** = move SL to entry price
- [x] Auto BEP after TP1 hit
- [x] Partial close at TP1
- [x] Real-time PNL via WebSocket

### Notifications
- [x] Telegram signal card on new signal
- [x] Telegram BEP notification
- [x] Telegram close notification with PNL
- [x] Notion page creation per signal
- [x] Notion fields: Margin USDT, Leverage, Profit USDT (new requirement)
- [x] Graceful disabled mode when keys not configured

### UI/UX
- [x] Bloomberg Terminal dark theme
- [x] JetBrains Mono font throughout
- [x] TradingView embedded chart
- [x] Real-time WebSocket updates
- [x] Active positions with live PNL
- [x] Signal log (terminal-style feed)

### Documentation
- [x] README.md with full documentation
- [x] Configuration guide
- [x] API reference
- [x] Notion schema documentation

---

## User Personas
- **Primary**: Solo crypto trader (opsculun) - uses demo mode first, then live
- **Secondary**: Additional team members via register feature

---

## What's Implemented (2026-05-30)
1. Full authentication system (login/register/JWT)
2. Signal generation engine (Swing/Scalp/Hybrid)
3. Demo mode paper trading with real price tracking
4. Bloomberg Terminal UI with TradingView chart
5. Active positions panel with INST TP/SL/BEP buttons
6. Position monitor (every 10s)
7. Telegram bot integration (configured via Settings)
8. Notion sync with margin/leverage/profit USDT
9. Max open positions + max margin + leverage settings
10. Performance page with equity curve
11. Settings page (4 tabs: Bot Config, Exchanges, Integrations, Controls)
12. WebSocket real-time updates
13. Documentation (README.md)
14. **Dockerfile** for backend (Python 3.11-slim)
15. **Dockerfile** for frontend (multi-stage: Node18 builder + nginx)
16. **docker-compose.yml** (all-in-one: MongoDB + Redis + Backend + Frontend)
17. **docker-compose.prod.yml** (external DB version)
18. **Kubernetes manifests** (/app/k8s/ - 9 files)
19. **.env.example** with full credential config guide
20. **deploy.sh** automated K8s deploy script
21. **k8s/README.md** deployment documentation

---

## Backlog / P2 Features
- [ ] Email notifications (backup to Telegram)
- [ ] Price alerts (separate from signals)
- [ ] Monthly Notion summary generation
- [ ] Mobile-responsive layout
- [ ] Signal backtest report
- [ ] Webhook integration for external signals

---

## Test Credentials
- Username: opsculun
- Password: @Traderculun147
- Role: admin
