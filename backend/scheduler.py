"""Scheduler: orchestrates signal scanning and position monitoring."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from signal_engine import scan_all
from exchange_handler import get_exchange
from telegram_bot import telegram_bot
from notion_sync import notion_sync

logger = logging.getLogger(__name__)


class SignalBotScheduler:
    def __init__(self, db, ws_manager):
        self.db = db
        self.ws = ws_manager
        self._running = False
        self._paused = False
        self._tasks = []
        self.position_monitor = None

    def setup_monitor(self, monitor):
        self.position_monitor = monitor

    async def start(self):
        from position_monitor import PositionMonitor
        if self.position_monitor is None:
            self.position_monitor = PositionMonitor(self.db, self.ws, telegram_bot, notion_sync)
        self._running = True
        self._tasks = [
            asyncio.create_task(self._swing_loop()),
            asyncio.create_task(self._scalp_loop()),
            asyncio.create_task(self._hybrid_loop()),
            asyncio.create_task(self._daily_summary_loop()),
            asyncio.create_task(self.position_monitor.start()),
        ]
        logger.info("Scheduler started")
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def pause(self):
        self._paused = True
        logger.info("Bot paused")

    def resume(self):
        self._paused = False
        logger.info("Bot resumed")

    async def _get_config(self):
        cfg = await self.db.bot_config.find_one({})
        if not cfg:
            return {}
        cfg.pop("_id", None)
        return cfg

    async def _check_limits(self, config: dict) -> bool:
        """Check if we can open new positions."""
        max_pos = config.get("max_open_positions", 3)
        max_margin = config.get("max_margin", 500.0)
        open_count = await self.db.signals.count_documents({"status": "open"})
        if open_count >= max_pos:
            logger.info(f"Max open positions reached ({open_count}/{max_pos})")
            return False
        # Check total margin
        pipeline = [
            {"$match": {"status": "open"}},
            {"$group": {"_id": None, "total_margin": {"$sum": "$margin"}}},
        ]
        result = await self.db.signals.aggregate(pipeline).to_list(1)
        total_margin = result[0]["total_margin"] if result else 0
        if total_margin >= max_margin:
            logger.info(f"Max margin reached ({total_margin:.2f}/{max_margin:.2f})")
            return False
        return True

    async def _process_signal(self, sig_data: dict, config: dict):
        pair = sig_data["pair"]
        # Avoid duplicate signal for same pair that's already open
        existing = await self.db.signals.find_one({"pair": pair, "status": "open"})
        if existing:
            return

        mode = config.get("active_mode", "demo")
        auto_trade_demo = config.get("auto_trade_demo", True)
        auto_trade_live = config.get("auto_trade_live", False)

        # Determine if this is signal-only (no order placement)
        signal_only = (mode == "demo" and not auto_trade_demo) or \
                      (mode == "live" and not auto_trade_live)

        if not signal_only and not await self._check_limits(config):
            return

        exchange_name = config.get("active_exchange", "demo")
        leverage = config.get("default_leverage", 5)
        risk_percent = config.get("risk_percent", 1.0)
        max_margin = config.get("max_margin", 500.0)
        auto_bep = config.get("auto_bep", True)
        partial_close = config.get("partial_close", True)
        partial_pct = config.get("partial_percent", 50)

        # Signal-only mode: no real order, just broadcast + notify
        if signal_only:
            from models import Signal
            signal = Signal(
                pair=pair,
                side=sig_data["side"],
                mode=mode,
                trading_mode=sig_data["trading_mode"],
                exchange=exchange_name,
                entry_price=sig_data["entry_price"],
                tp1=sig_data["tp1"],
                tp2=sig_data["tp2"],
                sl=sig_data["sl"],
                current_sl=sig_data["sl"],
                current_tp=sig_data["tp2"],
                score=sig_data["score"],
                confidence=sig_data["confidence"],
                signal_data=sig_data.get("signal_data", {}),
                rr_ratio=sig_data.get("rr_ratio", "1:2"),
                est_hold=sig_data.get("est_hold", ""),
                auto_bep=auto_bep,
                partial_close=partial_close,
                partial_percent=partial_pct,
                order_id="SIGNAL_ONLY",
                position_size=0,
                margin=0,
                leverage=leverage,
                signal_only=True,
            )
            signal_dict = signal.model_dump()
            sig_data_for_notify = {**signal_dict, **sig_data}
            await self.db.signals.insert_one(signal_dict)
            tg_msg_id = await telegram_bot.send_signal_card(sig_data_for_notify)
            if tg_msg_id:
                await self.db.signals.update_one({"id": signal.id}, {"$set": {"telegram_message_id": tg_msg_id}})
            notion_page_id = await notion_sync.create_signal_page(sig_data_for_notify)
            if notion_page_id:
                await self.db.signals.update_one({"id": signal.id}, {"$set": {"notion_page_id": notion_page_id}})
            await self.ws.broadcast({"event": "signal:new", "data": {**signal_dict, "signal_only": True}})
            logger.info(f"Signal only (no order): {pair} {sig_data['side']} {sig_data['trading_mode']} @ {sig_data['entry_price']:.4f}")
            return

        # Get exchange config
        ex_config = await self.db.exchange_configs.find_one({"name": exchange_name}) or {}
        api_key = ex_config.get("api_key", "")
        api_secret = ex_config.get("api_secret", "")
        passphrase = ex_config.get("passphrase", "")
        exchange = get_exchange(exchange_name, api_key, api_secret, passphrase)

        try:
            order = await exchange.place_order(
                pair, sig_data["side"], "", risk_percent, leverage, max_margin, self.db
            )
        except Exception as e:
            logger.error(f"Order placement failed for {pair}: {e}")
            return

        from models import Signal
        signal = Signal(
            pair=pair,
            side=sig_data["side"],
            mode=mode,
            trading_mode=sig_data["trading_mode"],
            exchange=exchange_name,
            entry_price=order.get("fill_price", sig_data["entry_price"]),
            tp1=sig_data["tp1"],
            tp2=sig_data["tp2"],
            sl=sig_data["sl"],
            current_sl=sig_data["sl"],
            current_tp=sig_data["tp2"],
            score=sig_data["score"],
            confidence=sig_data["confidence"],
            signal_data=sig_data.get("signal_data", {}),
            rr_ratio=sig_data.get("rr_ratio", "1:2"),
            est_hold=sig_data.get("est_hold", ""),
            auto_bep=auto_bep,
            partial_close=partial_close,
            partial_percent=partial_pct,
            order_id=order.get("order_id", ""),
            position_size=order.get("position_size", 0),
            margin=order.get("margin", 0),
            leverage=leverage,
        )

        # Remove extra fields not in model
        signal_dict = signal.model_dump()
        signal_dict.pop("fear_greed", None)
        signal_dict.pop("funding_rate", None)
        signal_dict.pop("volume_spike", None)
        # Store for Telegram/Notion
        sig_data_for_notify = {**signal_dict, **sig_data}

        await self.db.signals.insert_one(signal_dict)

        # Telegram
        tg_msg_id = await telegram_bot.send_signal_card(sig_data_for_notify)
        if tg_msg_id:
            await self.db.signals.update_one({"id": signal.id}, {"$set": {"telegram_message_id": tg_msg_id}})

        # Notion
        notion_page_id = await notion_sync.create_signal_page(sig_data_for_notify)
        if notion_page_id:
            await self.db.signals.update_one({"id": signal.id}, {"$set": {"notion_page_id": notion_page_id}})

        # WebSocket broadcast
        await self.ws.broadcast({"event": "signal:new", "data": signal_dict})
        logger.info(f"New signal: {pair} {sig_data['side']} {sig_data['trading_mode']} @ {signal.entry_price:.4f}")

    async def _swing_loop(self):
        while self._running:
            try:
                config = await self._get_config()
                interval = config.get("scan_interval_swing", 300)
                if not self._paused and config.get("swing_enabled", True):
                    coins = config.get("coins_to_scan", ["BTC/USDT", "ETH/USDT"])
                    signals = await scan_all(coins, "swing")
                    for sig in signals:
                        await self._process_signal(sig, config)
            except Exception as e:
                logger.error(f"Swing scan error: {e}")
            await asyncio.sleep(interval if not self._paused else 60)

    async def _scalp_loop(self):
        while self._running:
            try:
                config = await self._get_config()
                interval = config.get("scan_interval_scalp", 30)
                if not self._paused and config.get("scalp_enabled", False):
                    coins = config.get("coins_to_scan", ["BTC/USDT"])
                    signals = await scan_all(coins, "scalp")
                    for sig in signals:
                        await self._process_signal(sig, config)
            except Exception as e:
                logger.error(f"Scalp scan error: {e}")
            await asyncio.sleep(interval if not self._paused else 60)

    async def _hybrid_loop(self):
        while self._running:
            try:
                config = await self._get_config()
                interval = config.get("scan_interval_hybrid", 60)
                if not self._paused and config.get("hybrid_enabled", True):
                    coins = config.get("coins_to_scan", ["BTC/USDT", "ETH/USDT"])
                    signals = await scan_all(coins, "hybrid")
                    for sig in signals:
                        await self._process_signal(sig, config)
            except Exception as e:
                logger.error(f"Hybrid scan error: {e}")
            await asyncio.sleep(interval if not self._paused else 60)

    async def scan_now(self, mode: str = None):
        """Manual trigger for immediate scan."""
        config = await self._get_config()
        coins = config.get("coins_to_scan", ["BTC/USDT", "ETH/USDT", "SOL/USDT"])
        modes = [mode] if mode else ["swing", "hybrid"]
        for m in modes:
            signals = await scan_all(coins, m)
            for sig in signals:
                await self._process_signal(sig, config)
        return {"scanned": len(coins), "modes": modes}

    async def _daily_summary_loop(self):
        """Background task: emit a daily summary at 23:59 UTC every day.
        Sends row to Notion (if configured) and message to Telegram."""
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                # Compute seconds until next 23:59:00 UTC
                target = now.replace(hour=23, minute=59, second=0, microsecond=0)
                if target <= now:
                    # Already past today's 23:59 → schedule for tomorrow
                    from datetime import timedelta
                    target = target + timedelta(days=1)
                wait_s = max(60, (target - now).total_seconds())
                logger.info(f"Daily summary will run in {wait_s/3600:.2f}h")
                await asyncio.sleep(wait_s)
                if not self._running:
                    break
                await compute_and_send_daily_summary(self.db)
            except Exception as e:
                logger.error(f"Daily summary loop error: {e}")
                await asyncio.sleep(3600)  # Retry in 1h on error


async def compute_and_send_daily_summary(db) -> dict:
    """Compute today's trading stats and push them to Notion + Telegram."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Pull closed signals from today
    start = f"{today}T00:00:00+00:00"
    end = f"{today}T23:59:59+00:00"
    closed = await db.signals.find({
        "status": "closed",
        "closed_at": {"$gte": start, "$lte": end},
    }).to_list(1000)
    total = len(closed)
    wins = sum(1 for s in closed if (s.get("pnl") or 0) >= 0)
    losses = total - wins
    net_pnl = sum((s.get("pnl") or 0) for s in closed)
    win_rate = round(wins / total * 100, 1) if total > 0 else 0
    summary = {
        "date": today,
        "total_signals": total,
        "wins": wins,
        "losses": losses,
        "net_pnl": round(net_pnl, 2),
        "win_rate": win_rate,
    }
    # Save to DB
    await db.daily_summaries.update_one({"date": today}, {"$set": summary}, upsert=True)
    # Push to Notion
    notion_page_id = ""
    if notion_sync.enabled:
        notion_page_id = await notion_sync.create_daily_summary(summary)
    # Push to Telegram
    if telegram_bot.enabled:
        emoji = "🟢" if net_pnl >= 0 else "🔴"
        msg = (
            f"📊 *DAILY SUMMARY — {today}*\n\n"
            f"Total trades: *{total}*\n"
            f"Wins: *{wins}* | Losses: *{losses}*\n"
            f"Win Rate: *{win_rate}%*\n"
            f"Net PNL: {emoji} *${round(net_pnl, 2)}*"
        )
        try:
            await telegram_bot.send_system_alert(msg)
        except Exception as e:
            logger.error(f"Telegram daily summary send failed: {e}")
    logger.info(f"Daily summary: {summary}")
    return {**summary, "notion_page_id": notion_page_id}


# Global scheduler instance
scheduler = None


def get_scheduler(db, ws_manager):
    global scheduler
    if scheduler is None:
        scheduler = SignalBotScheduler(db, ws_manager)
    return scheduler
