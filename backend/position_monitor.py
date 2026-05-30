"""Position monitor: checks open positions every 10s for TP/SL/BEP hits."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from data_fetcher import get_current_price

logger = logging.getLogger(__name__)


def calc_pnl(entry: float, close: float, side: str, size: float, margin: float) -> dict:
    if side == "LONG":
        pnl_usd = (close - entry) * size
    else:
        pnl_usd = (entry - close) * size
    pnl_pct = (pnl_usd / margin * 100) if margin > 0 else 0
    risk = abs(entry - entry * 0.025)  # approximate risk
    r_val = (pnl_usd / (risk * size)) if risk > 0 and size > 0 else 0
    return {"pnl_usd": round(pnl_usd, 4), "pnl_pct": round(pnl_pct, 2), "r_value": round(r_val, 2)}


def hold_duration_str(created_at_str: str) -> str:
    try:
        opened = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - opened.replace(tzinfo=timezone.utc) if opened.tzinfo is None else datetime.now(timezone.utc) - opened
        total_minutes = int(delta.total_seconds() / 60)
        if total_minutes < 60:
            return f"{total_minutes}m"
        h = total_minutes // 60
        m = total_minutes % 60
        if h < 24:
            return f"{h}j {m}m"
        d = h // 24
        h = h % 24
        return f"{d}d {h}j"
    except Exception:
        return "0m"


class PositionMonitor:
    def __init__(self, db, ws_manager, telegram_bot, notion_sync):
        self.db = db
        self.ws = ws_manager
        self.tg = telegram_bot
        self.ns = notion_sync
        self._running = False

    async def start(self):
        self._running = True
        while self._running:
            try:
                await self.check_all_positions()
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
            await asyncio.sleep(10)

    def stop(self):
        self._running = False

    async def check_all_positions(self):
        signals = await self.db.signals.find({"status": "open", "signal_only": {"$ne": True}}).to_list(100)
        if not signals:
            return
        tasks = [self._check_signal(s) for s in signals]
        await asyncio.gather(*tasks, return_exceptions=True)
        # Broadcast live PNL
        await self._broadcast_positions(signals)

    async def _broadcast_positions(self, signals):
        updates = []
        for s in signals:
            price = await get_current_price(s["pair"])
            if price > 0:
                pnl = calc_pnl(s["entry_price"], price, s["side"], s.get("position_size", 0), s.get("margin", 0))
                updates.append({
                    "id": s["id"],
                    "pair": s["pair"],
                    "side": s["side"],
                    "exchange": s.get("exchange", "demo"),
                    "entry_price": s["entry_price"],
                    "current_price": price,
                    "pnl_usd": pnl["pnl_usd"],
                    "pnl_pct": pnl["pnl_pct"],
                    "tp1": s["tp1"],
                    "tp2": s["tp2"],
                    "sl": s.get("current_sl", s["sl"]),
                    "margin": s.get("margin", 0),
                    "leverage": s.get("leverage", 1),
                })
        if updates:
            await self.ws.broadcast({"event": "position:update", "data": updates})

    async def _check_signal(self, signal: dict):
        symbol = signal["pair"]
        side = signal["side"]
        current_price = await get_current_price(symbol)
        if current_price <= 0:
            return

        entry = signal["entry_price"]
        tp1 = signal["tp1"]
        tp2 = signal["tp2"]
        sl = signal.get("current_sl", signal["sl"])
        current_tp = signal.get("current_tp", tp2)
        auto_bep = signal.get("auto_bep", True)
        partial_close = signal.get("partial_close", True)
        margin = signal.get("margin", 0)
        size = signal.get("position_size", 0)
        leverage = signal.get("leverage", 1)
        tp1_hit = signal.get("tp1_hit", False)
        bep_activated = signal.get("bep_activated", False)

        tp1_reached = (current_price >= tp1 if side == "LONG" else current_price <= tp1)
        tp2_reached = (current_price >= tp2 if side == "LONG" else current_price <= tp2)
        sl_reached  = (current_price <= sl  if side == "LONG" else current_price >= sl)

        # Check instant TP/SL (modified values)
        custom_tp_reached = (current_price >= current_tp if side == "LONG" else current_price <= current_tp) if current_tp else False

        if not tp1_hit and tp1_reached:
            await self._on_tp1_hit(signal, current_price, auto_bep, partial_close, margin, size, leverage)
        elif tp2_reached or custom_tp_reached:
            reason = "INSTANT_TP" if (custom_tp_reached and current_tp != tp2) else "TP2"
            await self._on_close(signal, current_price, reason, margin, size, leverage)
        elif sl_reached:
            reason = "BEP_SL" if bep_activated else "SL"
            await self._on_close(signal, current_price, reason, margin, size, leverage)

    async def _on_tp1_hit(self, signal, price, auto_bep, partial_close, margin, size, leverage):
        now = datetime.now(timezone.utc).isoformat()
        updates = {"tp1_hit": True}
        if auto_bep:
            updates["bep_activated"] = True
            updates["bep_at"] = now
            updates["current_sl"] = signal["entry_price"]
        if partial_close:
            partial_pnl = calc_pnl(signal["entry_price"], price, signal["side"], size * 0.5, margin * 0.5)
            updates["partial_closed"] = True

        await self.db.signals.update_one({"id": signal["id"]}, {"$set": updates})
        await self.ws.broadcast({"event": "bep:activated", "data": {"id": signal["id"], "pair": signal["pair"], "tp1": price}})
        await self.tg.send_bep_notification(signal, price)
        if auto_bep:
            await self.ns.update_bep_activated(signal)
        logger.info(f"TP1 hit: {signal['pair']} {signal['side']} @ {price:.4f}")

    async def _on_close(self, signal, close_price, reason, margin, size, leverage):
        pnl = calc_pnl(signal["entry_price"], close_price, signal["side"], size, margin)
        now = datetime.now(timezone.utc).isoformat()
        hold = hold_duration_str(signal["created_at"])
        hold_min = 0
        try:
            opened = datetime.fromisoformat(signal["created_at"].replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - opened
            hold_min = int(delta.total_seconds() / 60)
        except Exception:
            pass

        await self.db.signals.update_one(
            {"id": signal["id"]},
            {"$set": {"status": "closed", "close_reason": reason}}
        )

        position_doc = {
            "id": str(uuid.uuid4()),
            "signal_id": signal["id"],
            "exchange": signal.get("exchange", "demo"),
            "order_id": signal.get("order_id", ""),
            "entry_price": signal["entry_price"],
            "close_price": close_price,
            "pnl": pnl["pnl_usd"],
            "pnl_percent": pnl["pnl_pct"],
            "r_value": pnl["r_value"],
            "hold_duration_minutes": hold_min,
            "result": reason,
            "closed_at": now,
            "margin": margin,
            "leverage": leverage,
            "position_size": size,
        }
        await self.db.positions.insert_one(position_doc)

        await self.ws.broadcast({"event": "position:closed", "data": {
            "id": signal["id"], "pair": signal["pair"],
            "reason": reason, "pnl_usd": pnl["pnl_usd"], "pnl_pct": pnl["pnl_pct"]
        }})
        await self.tg.send_close_notification(signal, position_doc)
        await self.ns.update_position_closed(signal, position_doc)
        await self._update_performance(signal, pnl, reason)
        logger.info(f"Position closed: {signal['pair']} {signal['side']} reason={reason} pnl={pnl['pnl_usd']:.2f} USDT")

    async def _update_performance(self, signal, pnl, reason):
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        is_win = pnl["pnl_usd"] > 0
        key = {"period": period, "exchange": signal.get("exchange", "demo"), "trading_mode": signal.get("trading_mode", "swing")}
        await self.db.performance_summary.update_one(
            key,
            {"$inc": {"total_trades": 1, "wins": 1 if is_win else 0, "losses": 0 if is_win else 1, "net_pnl": pnl["pnl_usd"], "net_r": pnl["r_value"]}},
            upsert=True
        )
