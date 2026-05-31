"""Exchange handler: supports ccxt (live) and DemoExchange (paper trading simulation).
DemoExchange uses OKX public API (no API key required) for price data.
"""
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)


def _to_okx_inst(symbol: str) -> str:
    """Convert 'BTC/USDT' → 'BTC-USDT-SWAP'."""
    base_quote = symbol.replace("/", "-")
    if base_quote.endswith("-SWAP"):
        return base_quote
    return f"{base_quote}-SWAP"


# ── Demo Exchange (paper trading, OKX data) ────────────────────────────────────
class DemoExchange:
    """Simulates exchange behavior using real market prices from OKX."""

    async def get_current_price(self, symbol: str) -> float:
        """Fetch price from OKX WS cache first, then REST."""
        from data_fetcher import get_current_price as okx_price
        return await okx_price(symbol)

    async def get_balance(self, db, exchange_name: str = "demo") -> float:
        config = await db.exchange_configs.find_one({"name": exchange_name})
        return float(config.get("demo_balance", 10000.0)) if config else 10000.0

    async def place_order(
        self, symbol: str, side: str, signal_id: str,
        risk_percent: float, leverage: int, max_margin: float, db
    ) -> Dict:
        balance = await self.get_balance(db)
        current_price = await self.get_current_price(symbol)
        if current_price <= 0:
            raise ValueError(f"Cannot get price for {symbol}")

        # Calculate margin (capped at max_margin)
        raw_margin = balance * (risk_percent / 100)
        margin = min(raw_margin, max_margin)
        position_size = (margin * leverage) / current_price

        order_id = f"DEMO-{uuid.uuid4().hex[:8].upper()}"
        logger.info(f"[DEMO] Order placed: {side} {symbol} @ {current_price:.4f} | margin={margin:.2f} USDT | lev={leverage}x | size={position_size:.6f}")

        return {
            "order_id": order_id,
            "fill_price": current_price,
            "position_size": position_size,
            "margin": margin,
            "leverage": leverage,
            "status": "filled",
        }

    async def close_position(self, signal_id: str, symbol: str, db) -> Dict:
        current_price = await self.get_current_price(symbol)
        return {"close_price": current_price, "status": "closed"}

    async def set_instant_tp(self, signal_id: str, symbol: str, tp_price: float, db) -> bool:
        """Set instant TP: close position immediately at market price (not limit)."""
        # In demo mode: update signal's current_tp and let monitor detect TP hit instantly
        await db.signals.update_one(
            {"id": signal_id},
            {"$set": {"current_tp": tp_price}}
        )
        logger.info(f"[DEMO] Instant TP set for {signal_id}: {tp_price}")
        return True

    async def set_instant_sl(self, signal_id: str, symbol: str, sl_price: float, db) -> bool:
        """Set instant SL: move stop loss to new price immediately (not limit)."""
        await db.signals.update_one(
            {"id": signal_id},
            {"$set": {"current_sl": sl_price}}
        )
        logger.info(f"[DEMO] Instant SL set for {signal_id}: {sl_price}")
        return True

    async def set_bep(self, signal_id: str, symbol: str, entry_price: float, db) -> bool:
        """Move SL to entry price (break even)."""
        await db.signals.update_one(
            {"id": signal_id},
            {"$set": {"current_sl": entry_price, "bep_activated": True, "bep_at": datetime.now(timezone.utc).isoformat()}}
        )
        logger.info(f"[DEMO] BEP set for {signal_id}: SL -> {entry_price}")
        return True


# ── Real Exchange (ccxt) ───────────────────────────────────────────────────────
class RealExchange:
    EXCHANGE_MAP = {
        "bybit_testnet": "bybit",
        "binance": "binance",
        "bybit": "bybit",
        "okx": "okx",
        "bitget": "bitget",
    }

    def __init__(self, name: str, api_key: str, api_secret: str, passphrase: str = ""):
        self.name = name
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self._exchange = None

    def _get_exchange(self):
        if self._exchange:
            return self._exchange
        import ccxt
        exchange_id = self.EXCHANGE_MAP.get(self.name, self.name)
        ExchangeClass = getattr(ccxt, exchange_id)
        config = {
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "options": {"defaultType": "future"},
        }
        if self.passphrase:
            config["password"] = self.passphrase
        if self.name == "bybit_testnet":
            config["testnet"] = True
            config["urls"] = {"api": {"public": "https://api-testnet.bybit.com", "private": "https://api-testnet.bybit.com"}}
        self._exchange = ExchangeClass(config)
        return self._exchange

    async def get_balance(self, db=None, exchange_name: str = None) -> float:
        try:
            ex = self._get_exchange()
            balance = await asyncio.get_event_loop().run_in_executor(None, ex.fetch_balance)
            return float(balance.get("USDT", {}).get("free", 0))
        except Exception as e:
            logger.error(f"Balance fetch failed: {e}")
            return 0.0

    async def get_current_price(self, symbol: str) -> float:
        try:
            ex = self._get_exchange()
            ticker = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ex.fetch_ticker(symbol)
            )
            return float(ticker["last"])
        except Exception as e:
            logger.warning(f"Price fetch failed ({symbol}): {e}")
            return 0.0

    async def place_order(
        self, symbol: str, side: str, signal_id: str,
        risk_percent: float, leverage: int, max_margin: float, db
    ) -> Dict:
        try:
            ex = self._get_exchange()
            balance = await self.get_balance()
            current_price = await self.get_current_price(symbol)
            raw_margin = balance * (risk_percent / 100)
            margin = min(raw_margin, max_margin)
            position_size = (margin * leverage) / current_price

            # Set leverage first
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: ex.set_leverage(leverage, symbol)
            )

            ccxt_side = "buy" if side == "LONG" else "sell"
            order = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ex.create_market_order(symbol, ccxt_side, position_size)
            )
            return {
                "order_id": str(order["id"]),
                "fill_price": float(order.get("average", current_price)),
                "position_size": position_size,
                "margin": margin,
                "leverage": leverage,
                "status": "filled",
            }
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            raise

    async def close_position(self, signal_id: str, symbol: str, db) -> Dict:
        try:
            ex = self._get_exchange()
            position = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ex.fetch_position(symbol)
            )
            if position and position.get("contracts", 0) > 0:
                close_side = "sell" if position["side"] == "long" else "buy"
                size = abs(float(position["contracts"]))
                order = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ex.create_market_order(symbol, close_side, size)
                )
                return {"close_price": float(order.get("average", 0)), "status": "closed"}
        except Exception as e:
            logger.error(f"Close position failed: {e}")
        return {"close_price": 0, "status": "error"}

    async def set_instant_tp(self, signal_id: str, symbol: str, tp_price: float, db) -> bool:
        """Close position immediately at market price (instant, not limit)."""
        try:
            result = await self.close_position(signal_id, symbol, db)
            return result["status"] == "closed"
        except Exception as e:
            logger.error(f"Instant TP failed: {e}")
            return False

    async def set_instant_sl(self, signal_id: str, symbol: str, sl_price: float, db) -> bool:
        """Close position immediately at market price (instant, not limit)."""
        try:
            result = await self.close_position(signal_id, symbol, db)
            return result["status"] == "closed"
        except Exception as e:
            logger.error(f"Instant SL failed: {e}")
            return False

    async def set_bep(self, signal_id: str, symbol: str, entry_price: float, db) -> bool:
        """Move SL to entry price (break even)."""
        await db.signals.update_one(
            {"id": signal_id},
            {"$set": {"current_sl": entry_price, "bep_activated": True, "bep_at": datetime.now(timezone.utc).isoformat()}}
        )
        return True


# ── Factory ────────────────────────────────────────────────────────────────────
demo_exchange = DemoExchange()


def get_exchange(name: str, api_key: str = "", api_secret: str = "", passphrase: str = ""):
    if name == "demo" or not api_key:
        return demo_exchange
    return RealExchange(name, api_key, api_secret, passphrase)
