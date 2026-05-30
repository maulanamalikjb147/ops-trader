# Signal Bot — Complete Documentation

## Overview

Signal Bot is a personal-use crypto trading signal system with:
- Bloomberg Terminal-style web dashboard
- Automated signal generation (Swing / Scalp / Hybrid modes)
- **Demo mode** (paper trading, zero real money, uses real prices)
- Live trading via ccxt (Binance, Bybit, OKX, Bitget)
- Telegram notifications for all signal events
- Notion database logging with margin/leverage/profit USDT data
- Real-time WebSocket updates
- JWT-based authentication (login/register)

---

## Quick Start

### Default Login
```
Username: opsculun
Password: @Traderculun147
```

### Run Locally
```bash
# Backend
cd /app/backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Frontend (in another terminal)
cd /app/frontend
yarn install && yarn start

# Redis (required for caching)
redis-server --daemonize yes
```

---

## Environment Variables (`/app/backend/.env`)

```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=signal_bot
JWT_SECRET=<64-char random hex>
ADMIN_USERNAME=opsculun
ADMIN_PASSWORD=@Traderculun147
REDIS_URL=redis://localhost:6379
CORS_ORIGINS=*
FRONTEND_URL=http://localhost:3000
```

---

## Settings Page Configuration

### Bot Config Tab
| Setting | Description | Default |
|---------|-------------|---------|
| Max Open Positions | Max concurrent trades | 3 |
| Max Total Margin | Max USDT allocated | 500 USDT |
| Default Leverage | Leverage per trade | 5x |
| Risk Per Trade | % of balance per trade | 1% |
| Auto BEP | Move SL to entry after TP1 | ON |
| Partial Close | Close 50% at TP1 | ON |

### Exchange Tab
- **Demo** — paper trading (zero API needed)
- **Bybit Testnet** — testnet.bybit.com
- **Binance/Bybit/OKX/Bitget** — live exchanges

### Integrations Tab
| Integration | Source |
|-------------|--------|
| Telegram Token | @BotFather on Telegram |
| Telegram Chat ID | @userinfobot on Telegram |
| Notion API Key | notion.so/my-integrations |
| Notion Database ID | From Notion DB URL |
| CoinGecko Key | coingecko.com/api (optional) |

---

## Demo Mode (Paper Trading)

- No real API required
- Creates simulated positions in MongoDB
- Tracks REAL market prices (Binance public API)
- Detects TP/SL hits based on actual price movement
- Reports to Telegram + Notion same as live mode
- Virtual balance: configurable (default $10,000 USDT)

---

## TP/SL/BEP Buttons

| Button | Action |
|--------|--------|
| **INST TP** | Instant take-profit at MARKET price (not limit) |
| **INST SL** | Instant stop-loss at MARKET price (not limit) |
| **SL→BEP** | Move SL to entry price → trade becomes risk-free |

---

## Signal Modes

| Mode | Timeframe | Score Required | TP1/TP2/SL |
|------|-----------|----------------|------------|
| Swing | 4H/1D | 4/5 | +2.5% / +5.0% / -2.5% |
| Scalp | 1m/5m | 3/5 | +0.5% / +1.0% / -0.4% |
| Hybrid | 15m/1H/4H | 4/5 | +1.5% / +5.0% / -2.5% |

---

## Notion Schema

Each signal creates a Notion page with:
- Pair, Side, Trading Mode, Exchange
- Entry, TP1, TP2, SL, Close Price
- **Margin USDT** — margin used for the trade
- **Leverage** — leverage multiplier
- **Profit USDT** — realized profit in USDT
- PNL%, R Value, Hold Duration, BEP Activated
- Result: OPEN / WIN / LOSS / BEP

---

## API Endpoints

```
POST   /api/auth/login
POST   /api/auth/register
GET    /api/auth/me
GET    /api/signals
POST   /api/signals/{id}/close
POST   /api/signals/{id}/set-tp     { price: float }
POST   /api/signals/{id}/set-sl     { price: float }
POST   /api/signals/{id}/set-bep
GET    /api/positions
GET    /api/performance
GET    /api/performance/equity
GET    /api/exchanges
POST   /api/exchanges
PUT    /api/exchanges/{id}
GET    /api/config
PUT    /api/config
POST   /api/bot/pause
POST   /api/bot/resume
GET    /api/bot/status
POST   /api/bot/scan-now
WS     /ws
```

---

## WebSocket Events

| Event | Data |
|-------|------|
| `signal:new` | New signal object |
| `position:update` | Array of open positions with live PNL |
| `position:closed` | Closed position + PNL |
| `bep:activated` | Position ID + new SL |
| `bot:status` | {paused: bool} |
