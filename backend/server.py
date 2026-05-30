from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

from auth import get_current_user, hash_password, verify_password, create_access_token, create_refresh_token, seed_admin
from models import BotConfig, ExchangeConfig, User
from telegram_bot import telegram_bot
from notion_sync import notion_sync
from scheduler import get_scheduler

ROOT_DIR = Path(__file__).parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ── MongoDB ────────────────────────────────────────────────────────────────────
mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]

# ── WebSocket Manager ──────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        msg = json.dumps(data)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()

# ── FastAPI App ────────────────────────────────────────────────────────────────
app = FastAPI(title="Signal Bot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")


# ── DB Initialization ──────────────────────────────────────────────────────────
async def init_db():
    # Indexes
    await db.users.create_index("username", unique=True)
    await db.signals.create_index("status")
    await db.signals.create_index("pair")
    await db.positions.create_index("signal_id")
    await db.performance_summary.create_index([("period", 1), ("exchange", 1), ("trading_mode", 1)], unique=True)
    # Default exchange config (demo)
    demo_exists = await db.exchange_configs.find_one({"name": "demo"})
    if not demo_exists:
        demo = ExchangeConfig(name="demo", tag="DEMO", mode="demo", is_active=True)
        await db.exchange_configs.insert_one(demo.model_dump())
    # Default bot config
    cfg_exists = await db.bot_config.find_one({})
    if not cfg_exists:
        cfg = BotConfig()
        await db.bot_config.insert_one(cfg.model_dump())
    else:
        # Migrate: add any new fields that don't exist yet
        new_fields = {}
        defaults = BotConfig().model_dump()
        for k, v in defaults.items():
            if k not in cfg_exists:
                new_fields[k] = v
        if new_fields:
            await db.bot_config.update_one({}, {"$set": new_fields})
            logger.info(f"Config migrated: added fields {list(new_fields.keys())}")
    await seed_admin(db)
    logger.info("Database initialized")


# ── Startup ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await init_db()
    sched = get_scheduler(db, ws_manager)
    asyncio.create_task(sched.start())
    # Reconfigure integrations from DB
    cfg = await db.bot_config.find_one({})
    if cfg:
        telegram_bot.reconfigure(cfg.get("telegram_token", ""), cfg.get("telegram_chat_id", ""))
        notion_sync.reconfigure(cfg.get("notion_api_key", ""), cfg.get("notion_database_id", ""))
    logger.info("Startup complete")


@app.on_event("shutdown")
async def shutdown():
    mongo_client.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ═══════════════════════════════════════════════════════════════════════════════
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


@api.post("/auth/login")
async def login(body: LoginRequest, response: Response):
    user = await db.users.find_one({"username": body.username})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access = create_access_token(user["id"], user["username"])
    refresh = create_refresh_token(user["id"])
    response.set_cookie("access_token", access, httponly=True, samesite="lax", max_age=86400)
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax", max_age=604800)
    user.pop("_id", None)
    user.pop("password_hash", None)
    return user


@api.post("/auth/register")
async def register(body: RegisterRequest, request: Request, response: Response):
    # Check if caller is admin for role assignment
    caller = None
    try:
        caller = await get_current_user(request, db)
    except Exception:
        pass
    role = "user"
    if caller and caller.get("role") == "admin" and body.role in ["admin", "user"]:
        role = body.role

    if await db.users.find_one({"username": body.username}):
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(username=body.username, password_hash=hash_password(body.password), role=role)
    await db.users.insert_one(user.model_dump())
    access = create_access_token(user.id, user.username)
    refresh = create_refresh_token(user.id)
    response.set_cookie("access_token", access, httponly=True, samesite="lax", max_age=86400)
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax", max_age=604800)
    return {"id": user.id, "username": user.username, "role": user.role}


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"ok": True}


@api.get("/auth/me")
async def me(request: Request):
    return await get_current_user(request, db)


# ═══════════════════════════════════════════════════════════════════════════════
#  SIGNALS ROUTES
# ═══════════════════════════════════════════════════════════════════════════════
@api.get("/signals")
async def list_signals(
    request: Request,
    status: Optional[str] = None,
    exchange: Optional[str] = None,
    trading_mode: Optional[str] = None,
    mode: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
):
    await get_current_user(request, db)
    filt = {}
    if status: filt["status"] = status
    if exchange: filt["exchange"] = exchange
    if trading_mode: filt["trading_mode"] = trading_mode
    if mode: filt["mode"] = mode
    signals = await db.signals.find(filt, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return signals


@api.get("/signals/{signal_id}")
async def get_signal(signal_id: str, request: Request):
    await get_current_user(request, db)
    sig = await db.signals.find_one({"id": signal_id}, {"_id": 0})
    if not sig:
        raise HTTPException(404, "Signal not found")
    return sig


class PriceBody(BaseModel):
    price: float


@api.post("/signals/{signal_id}/close")
async def close_signal(signal_id: str, request: Request):
    await get_current_user(request, db)
    sig = await db.signals.find_one({"id": signal_id})
    if not sig or sig["status"] != "open":
        raise HTTPException(404, "Open signal not found")
    from exchange_handler import get_exchange
    from position_monitor import calc_pnl, hold_duration_str
    ex_config = await db.exchange_configs.find_one({"name": sig.get("exchange", "demo")}) or {}
    exchange = get_exchange(sig.get("exchange", "demo"), ex_config.get("api_key", ""), ex_config.get("api_secret", ""), ex_config.get("passphrase", ""))
    result = await exchange.close_position(signal_id, sig["pair"], db)
    close_price = result.get("close_price", sig["entry_price"])
    pnl = calc_pnl(sig["entry_price"], close_price, sig["side"], sig.get("position_size", 0), sig.get("margin", 0))
    now = datetime.now(timezone.utc).isoformat()
    await db.signals.update_one({"id": signal_id}, {"$set": {"status": "closed", "close_reason": "MANUAL"}})
    pos_doc = {
        "id": str(uuid.uuid4()),
        "signal_id": signal_id, "exchange": sig.get("exchange", "demo"),
        "order_id": sig.get("order_id", ""), "entry_price": sig["entry_price"],
        "close_price": close_price, "pnl": pnl["pnl_usd"], "pnl_percent": pnl["pnl_pct"],
        "r_value": pnl["r_value"], "result": "MANUAL", "closed_at": now,
        "margin": sig.get("margin", 0), "leverage": sig.get("leverage", 1),
        "position_size": sig.get("position_size", 0),
    }
    await db.positions.insert_one(pos_doc)
    await ws_manager.broadcast({"event": "position:closed", "data": {"id": signal_id, "reason": "MANUAL", "pnl_usd": pnl["pnl_usd"]}})
    await telegram_bot.send_close_notification(sig, pos_doc)
    await notion_sync.update_position_closed(sig, pos_doc)
    return {"ok": True, "pnl": pnl}


@api.post("/signals/{signal_id}/set-tp")
async def set_instant_tp(signal_id: str, body: PriceBody, request: Request):
    """Set instant TP (close at market if price reached, not limit order)."""
    await get_current_user(request, db)
    sig = await db.signals.find_one({"id": signal_id})
    if not sig or sig["status"] != "open":
        raise HTTPException(404, "Open signal not found")
    ex_config = await db.exchange_configs.find_one({"name": sig.get("exchange", "demo")}) or {}
    from exchange_handler import get_exchange
    exchange = get_exchange(sig.get("exchange", "demo"), ex_config.get("api_key", ""), ex_config.get("api_secret", ""))
    ok = await exchange.set_instant_tp(signal_id, sig["pair"], body.price, db)
    return {"ok": ok, "message": "Instant TP set - will trigger at market price when reached"}


@api.post("/signals/{signal_id}/set-sl")
async def set_instant_sl(signal_id: str, body: PriceBody, request: Request):
    """Set instant SL (close at market if price reached, not limit order)."""
    await get_current_user(request, db)
    sig = await db.signals.find_one({"id": signal_id})
    if not sig or sig["status"] != "open":
        raise HTTPException(404, "Open signal not found")
    ex_config = await db.exchange_configs.find_one({"name": sig.get("exchange", "demo")}) or {}
    from exchange_handler import get_exchange
    exchange = get_exchange(sig.get("exchange", "demo"), ex_config.get("api_key", ""), ex_config.get("api_secret", ""))
    ok = await exchange.set_instant_sl(signal_id, sig["pair"], body.price, db)
    return {"ok": ok, "message": "Instant SL set - will trigger at market price when reached"}


@api.post("/signals/{signal_id}/set-bep")
async def set_bep(signal_id: str, request: Request):
    """Set break even: move SL to entry price."""
    await get_current_user(request, db)
    sig = await db.signals.find_one({"id": signal_id})
    if not sig or sig["status"] != "open":
        raise HTTPException(404, "Open signal not found")
    ex_config = await db.exchange_configs.find_one({"name": sig.get("exchange", "demo")}) or {}
    from exchange_handler import get_exchange
    exchange = get_exchange(sig.get("exchange", "demo"), ex_config.get("api_key", ""), ex_config.get("api_secret", ""))
    ok = await exchange.set_bep(signal_id, sig["pair"], sig["entry_price"], db)
    await ws_manager.broadcast({"event": "bep:activated", "data": {"id": signal_id, "new_sl": sig["entry_price"]}})
    return {"ok": ok, "message": f"SL moved to entry price (BEP): {sig['entry_price']}"}


# ═══════════════════════════════════════════════════════════════════════════════
#  POSITIONS
# ═══════════════════════════════════════════════════════════════════════════════
@api.get("/positions")
async def list_positions(request: Request, limit: int = 50):
    await get_current_user(request, db)
    positions = await db.positions.find({}, {"_id": 0}).sort("closed_at", -1).limit(limit).to_list(limit)
    return positions


# ═══════════════════════════════════════════════════════════════════════════════
#  PERFORMANCE
# ═══════════════════════════════════════════════════════════════════════════════
@api.get("/performance")
async def get_performance(request: Request, period: Optional[str] = None, exchange: Optional[str] = None, trading_mode: Optional[str] = None):
    await get_current_user(request, db)
    filt = {}
    if period: filt["period"] = period
    if exchange: filt["exchange"] = exchange
    if trading_mode: filt["trading_mode"] = trading_mode
    summaries = await db.performance_summary.find(filt, {"_id": 0}).to_list(100)
    # Also compute totals directly from positions
    positions = await db.positions.find({}, {"_id": 0}).to_list(1000)
    total_trades = len(positions)
    wins = sum(1 for p in positions if (p.get("pnl") or 0) > 0)
    net_pnl = sum(p.get("pnl") or 0 for p in positions)
    win_rate = round(wins / total_trades * 100, 1) if total_trades > 0 else 0
    avg_hold = 0
    if positions:
        avg_hold = sum(p.get("hold_duration_minutes") or 0 for p in positions) / len(positions)
    open_count = await db.signals.count_documents({"status": "open"})
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_positions = [p for p in positions if p.get("closed_at", "").startswith(today)]
    today_pnl = sum(p.get("pnl") or 0 for p in today_positions)
    today_signals = await db.signals.count_documents({"created_at": {"$gte": today}})
    return {
        "summaries": summaries,
        "total_trades": total_trades,
        "wins": wins,
        "losses": total_trades - wins,
        "win_rate": win_rate,
        "net_pnl": round(net_pnl, 4),
        "avg_hold_minutes": round(avg_hold, 0),
        "active_positions": open_count,
        "today_pnl": round(today_pnl, 4),
        "today_signals": today_signals,
    }


@api.get("/performance/equity")
async def get_equity_curve(request: Request):
    await get_current_user(request, db)
    positions = await db.positions.find({}, {"_id": 0}).sort("closed_at", 1).to_list(1000)
    equity = []
    running_pnl = 0
    for p in positions:
        running_pnl += p.get("pnl") or 0
        equity.append({"date": p.get("closed_at", ""), "pnl": round(running_pnl, 4), "trade_pnl": round(p.get("pnl") or 0, 4)})
    return equity


# ═══════════════════════════════════════════════════════════════════════════════
#  EXCHANGES
# ═══════════════════════════════════════════════════════════════════════════════
@api.get("/exchanges")
async def list_exchanges(request: Request):
    await get_current_user(request, db)
    configs = await db.exchange_configs.find({}, {"_id": 0}).to_list(20)
    # Mask API keys
    for c in configs:
        if c.get("api_key"):
            c["api_key"] = c["api_key"][:4] + "***" + c["api_key"][-4:]
        if c.get("api_secret"):
            c["api_secret"] = "***"
    return configs


class ExchangeCreateBody(BaseModel):
    name: str
    tag: str
    mode: str = "live"
    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""
    demo_balance: float = 10000.0


@api.post("/exchanges")
async def create_exchange(body: ExchangeCreateBody, request: Request):
    await get_current_user(request, db)
    existing = await db.exchange_configs.find_one({"name": body.name})
    if existing:
        raise HTTPException(400, "Exchange already configured")
    cfg = ExchangeConfig(**body.model_dump())
    await db.exchange_configs.insert_one(cfg.model_dump())
    return {"ok": True, "id": cfg.id}


@api.put("/exchanges/{ex_id}")
async def update_exchange(ex_id: str, body: dict, request: Request):
    await get_current_user(request, db)
    # Don't override masked values
    update = {k: v for k, v in body.items() if v is not None and v != "***" and not str(v).endswith("***")}
    await db.exchange_configs.update_one({"id": ex_id}, {"$set": update})
    return {"ok": True}


@api.delete("/exchanges/{ex_id}")
async def delete_exchange(ex_id: str, request: Request):
    await get_current_user(request, db)
    cfg = await db.exchange_configs.find_one({"id": ex_id})
    if cfg and cfg.get("name") == "demo":
        raise HTTPException(400, "Cannot delete demo exchange")
    await db.exchange_configs.delete_one({"id": ex_id})
    return {"ok": True}


@api.get("/exchanges/{ex_id}/balance")
async def get_exchange_balance(ex_id: str, request: Request):
    await get_current_user(request, db)
    cfg = await db.exchange_configs.find_one({"id": ex_id})
    if not cfg:
        raise HTTPException(404, "Exchange not found")
    from exchange_handler import get_exchange
    exchange = get_exchange(cfg["name"], cfg.get("api_key", ""), cfg.get("api_secret", ""), cfg.get("passphrase", ""))
    balance = await exchange.get_balance(db, cfg["name"])
    return {"balance": balance, "currency": "USDT"}


# ═══════════════════════════════════════════════════════════════════════════════
#  BOT CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
@api.get("/config")
async def get_config(request: Request):
    await get_current_user(request, db)
    cfg = await db.bot_config.find_one({}, {"_id": 0})
    if not cfg:
        return BotConfig().model_dump()
    # Mask sensitive keys in response
    masked = {**cfg}
    for key in ["telegram_token", "notion_api_key", "coingecko_api_key"]:
        if masked.get(key):
            masked[key] = masked[key][:4] + "***"
    return masked


@api.put("/config")
async def update_config(body: dict, request: Request):
    await get_current_user(request, db)
    # Don't override masked values
    update = {k: v for k, v in body.items() if v is not None and not str(v).endswith("***")}
    await db.bot_config.update_one({}, {"$set": update}, upsert=True)
    # Reload integrations
    cfg = await db.bot_config.find_one({})
    if cfg:
        telegram_bot.reconfigure(cfg.get("telegram_token", ""), cfg.get("telegram_chat_id", ""))
        notion_sync.reconfigure(cfg.get("notion_api_key", ""), cfg.get("notion_database_id", ""))
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
#  BOT CONTROLS
# ═══════════════════════════════════════════════════════════════════════════════
@api.post("/bot/pause")
async def pause_bot(request: Request):
    await get_current_user(request, db)
    sched = get_scheduler(db, ws_manager)
    sched.pause()
    await db.bot_config.update_one({}, {"$set": {"is_paused": True}})
    await ws_manager.broadcast({"event": "bot:status", "data": {"paused": True}})
    return {"ok": True, "paused": True}


@api.post("/bot/resume")
async def resume_bot(request: Request):
    await get_current_user(request, db)
    sched = get_scheduler(db, ws_manager)
    sched.resume()
    await db.bot_config.update_one({}, {"$set": {"is_paused": False}})
    await ws_manager.broadcast({"event": "bot:status", "data": {"paused": False}})
    return {"ok": True, "paused": False}


@api.get("/bot/status")
async def bot_status(request: Request):
    await get_current_user(request, db)
    cfg = await db.bot_config.find_one({}, {"_id": 0})
    open_count = await db.signals.count_documents({"status": "open"})
    pipeline = [{"$match": {"status": "open"}}, {"$group": {"_id": None, "total": {"$sum": "$margin"}}}]
    res = await db.signals.aggregate(pipeline).to_list(1)
    total_margin = res[0]["total"] if res else 0
    return {
        "paused": cfg.get("is_paused", False) if cfg else False,
        "active_mode": cfg.get("active_mode", "demo") if cfg else "demo",
        "open_positions": open_count,
        "total_margin_used": round(total_margin, 2),
        "ws_clients": len(ws_manager.active),
        "telegram_enabled": telegram_bot.enabled,
        "notion_enabled": notion_sync.enabled,
    }


@api.post("/bot/scan-now")
async def scan_now(request: Request, mode: Optional[str] = None):
    await get_current_user(request, db)
    sched = get_scheduler(db, ws_manager)
    result = await sched.scan_now(mode)
    return result


@api.get("/market/top-pairs")
async def get_top_pairs(request: Request, exchange: str = "binance", limit: int = 50):
    """Fetch top trading pairs by 24h volume from exchange."""
    await get_current_user(request, db)
    from market_scanner import get_top_pairs
    pairs = await get_top_pairs(exchange, limit)
    return pairs


# ═══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD STATS
# ═══════════════════════════════════════════════════════════════════════════════
@api.get("/dashboard")
async def dashboard_stats(request: Request):
    await get_current_user(request, db)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_signals = await db.signals.count_documents({"created_at": {"$gte": today}})
    open_count = await db.signals.count_documents({"status": "open"})
    positions = await db.positions.find({}, {"_id": 0, "pnl": 1, "closed_at": 1}).to_list(1000)
    today_pos = [p for p in positions if p.get("closed_at", "").startswith(today)]
    today_pnl = sum(p.get("pnl") or 0 for p in today_pos)
    total_trades = len(positions)
    wins = sum(1 for p in positions if (p.get("pnl") or 0) > 0)
    win_rate = round(wins / total_trades * 100, 1) if total_trades > 0 else 0
    # Recent signals for signal log
    recent_signals = await db.signals.find({}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
    return {
        "today_signals": today_signals,
        "open_positions": open_count,
        "today_pnl": round(today_pnl, 4),
        "win_rate": win_rate,
        "total_trades": total_trades,
        "recent_signals": recent_signals,
    }


# ── Include router ─────────────────────────────────────────────────────────────
app.include_router(api)


# ── WebSocket endpoint ─────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)
