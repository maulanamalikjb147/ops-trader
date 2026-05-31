"""Telegram bot for signal notifications."""
import logging
import httpx
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token: str = "", chat_id: str = ""):
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)

    def reconfigure(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)

    async def _send(self, text: str, reply_to: int = None) -> int:
        if not self.enabled:
            logger.info(f"[Telegram disabled] {text[:80]}")
            return 0
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if reply_to:
            payload["reply_to_message_id"] = reply_to
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json=payload
                )
                data = resp.json()
                if data.get("ok"):
                    return data["result"]["message_id"]
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
        return 0

    def _exchange_tag(self, exchange: str) -> str:
        tags = {
            "demo": "DEMO",
            "bybit_testnet": "BYBIT TESTNET",
            "binance": "BINANCE",
            "bybit": "BYBIT",
            "okx": "OKX",
            "bitget": "BITGET",
        }
        return tags.get(exchange, exchange.upper())

    async def send_signal_card(self, signal: dict) -> int:
        side = signal["side"]
        pair = signal["pair"]
        tm = signal["trading_mode"].upper()
        entry = signal["entry_price"]
        tp1 = signal["tp1"]
        tp2 = signal["tp2"]
        sl = signal["sl"]
        score = signal["confidence"]
        rr = signal.get("rr_ratio", "1:2")
        hold = signal.get("est_hold", "")
        exchange_tag = self._exchange_tag(signal.get("exchange", "demo"))
        margin = signal.get("margin", 0)
        leverage = signal.get("leverage", 1)

        tp1_pct = abs(tp1 - entry) / entry * 100
        tp2_pct = abs(tp2 - entry) / entry * 100
        sl_pct = abs(sl - entry) / entry * 100
        fg = signal.get("fear_greed", {})
        fr = signal.get("funding_rate", 0)
        vol = signal.get("volume_spike", 0)

        side_arrow = "▲" if side == "LONG" else "▼"
        now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M WIB")

        text = (
            f"<b>⚡ {tm} SIGNAL</b>\n"
            f"──────────────────────\n"
            f"{side_arrow} <b>{side} ${pair}</b>\n"
            f"Mode: <code>{exchange_tag}</code>\n\n"
            f"📊 Entry  : <code>${entry:,.4f}</code>\n"
            f"🎯 TP1   : <code>${tp1:,.4f}</code> (+{tp1_pct:.1f}%)\n"
            f"🎯 TP2   : <code>${tp2:,.4f}</code> (+{tp2_pct:.1f}%)\n"
            f"🛑 SL    : <code>${sl:,.4f}</code> (-{sl_pct:.1f}%)\n"
            f"⚖️  RR    : {rr}\n"
            f"⏱️ Hold   : {hold}\n"
            f"📐 Margin : <code>${margin:.2f} USDT</code> ({leverage}x)\n\n"
            f"📡 <b>Signal Data:</b>\n"
            f"→ F&G    : {fg.get('value', 'N/A')} ({fg.get('classification', '')})\n"
            f"→ FR     : {fr:.4f}%\n"
            f"→ Vol    : {vol:+.0f}%\n\n"
            f"🔍 Confidence: <b>{score}</b>\n"
            f"⏰ {now}"
        )
        return await self._send(text)

    async def send_bep_notification(self, signal: dict, tp1_price: float):
        pair = signal["pair"]
        side = signal["side"]
        entry = signal["entry_price"]
        exchange_tag = self._exchange_tag(signal.get("exchange", "demo"))
        text = (
            f"<b>🔒 AUTO BEP ACTIVATED</b>\n"
            f"──────────────────────\n"
            f"📌 {pair} {side} | <code>{exchange_tag}</code>\n\n"
            f"TP1 hit @ <code>${tp1_price:,.4f}</code> ✅\n"
            f"SL moved → <code>${entry:,.4f}</code> (Break Even)\n"
            f"Posisi sekarang <b>risk-free!</b>"
        )
        reply_to = signal.get("telegram_message_id")
        await self._send(text, reply_to=reply_to)

    async def send_close_notification(self, signal: dict, position: dict):
        pair = signal["pair"]
        side = signal["side"]
        entry = signal["entry_price"]
        close = position["close_price"]
        pnl_usd = position.get("pnl", 0)
        pnl_pct = position.get("pnl_percent", 0)
        r_val = position.get("r_value", 0)
        hold = position.get("hold_duration_minutes", 0)
        reason = position.get("result", "CLOSED")
        margin = position.get("margin", 0)
        leverage = position.get("leverage", 1)
        exchange_tag = self._exchange_tag(signal.get("exchange", "demo"))
        tm = signal.get("trading_mode", "").upper()
        is_win = pnl_usd >= 0
        emoji = "✅" if is_win else "❌"
        pnl_emoji = "💰" if is_win else "💸"
        hold_str = f"{hold}m" if hold < 60 else f"{hold//60}j {hold%60}m"

        text = (
            f"<b>{emoji} CLOSED — {reason}</b>\n"
            f"────────────────────\n"
            f"<code>{exchange_tag}</code> | {tm}\n"
            f"📌 {pair} {side}\n\n"
            f"Entry  : <code>${entry:,.4f}</code>\n"
            f"Close  : <code>${close:,.4f}</code>\n"
            f"──────────────────────\n"
            f"{pnl_emoji} PNL    : <code>{'+' if pnl_usd >= 0 else ''}{pnl_usd:.2f} USDT</code> ({pnl_pct:+.1f}%)\n"
            f"📐 Margin : <code>${margin:.2f}</code> ({leverage}x)\n"
            f"📈 R      : <code>{r_val:+.2f}R</code>\n"
            f"⏱️ Hold   : {hold_str}\n\n"
            f"#{reason} #{'WIN' if is_win else 'LOSS'} #{exchange_tag.replace(' ', '_')} #{tm}"
        )
        reply_to = signal.get("telegram_message_id")
        await self._send(text, reply_to=reply_to)

    async def send_system_alert(self, message: str):
        text = f"<b>⚠️ SYSTEM ALERT</b>\n\n{message}"
        await self._send(text)

    async def send_test_message(self) -> dict:
        """Send a test message to verify token + chat_id are correct.
        Returns dict with success/error."""
        if not self.token:
            return {"ok": False, "error": "Bot token not configured"}
        if not self.chat_id:
            return {"ok": False, "error": "Chat ID not configured"}
        text = (
            "<b>✅ SIGNAL BOT — TEST MESSAGE</b>\n\n"
            "Connection working! Your bot can send notifications.\n\n"
            "<i>You will receive trade signals, BEP/TP/SL alerts, and daily summaries here.</i>"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
                )
                data = resp.json()
                if data.get("ok"):
                    return {"ok": True, "message_id": data["result"]["message_id"]}
                return {"ok": False, "error": data.get("description", "Unknown error")}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# Global instance (re-configured from DB settings)
telegram_bot = TelegramBot()
