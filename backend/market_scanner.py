"""Fetch top trading pairs by volume from exchange public APIs."""
import httpx
import asyncio
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


async def get_top_binance_pairs(quote="USDT", limit=50, min_volume_usd=50_000_000) -> List[Dict]:
    """Fetch top N USDT perpetual pairs by 24h volume from Binance."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://api.binance.com/api/v3/ticker/24hr")
            tickers = resp.json()
        pairs = []
        for t in tickers:
            symbol = t.get("symbol", "")
            if not symbol.endswith(quote):
                continue
            volume_usdt = float(t.get("quoteVolume", 0))
            if volume_usdt < min_volume_usd:
                continue
            price_change = float(t.get("priceChangePercent", 0))
            pairs.append({
                "pair": symbol[:-len(quote)] + "/" + quote,
                "symbol": symbol,
                "volume_24h_usdt": round(volume_usdt / 1_000_000, 2),  # in millions
                "price_change_24h": round(price_change, 2),
                "last_price": float(t.get("lastPrice", 0)),
                "exchange": "binance",
            })
        # Sort by volume descending
        pairs.sort(key=lambda x: x["volume_24h_usdt"], reverse=True)
        return pairs[:limit]
    except Exception as e:
        logger.error(f"Binance top pairs fetch failed: {e}")
        return []


async def get_top_bybit_pairs(quote="USDT", limit=50, min_volume_usd=10_000_000) -> List[Dict]:
    """Fetch top N USDT perpetual pairs by 24h volume from Bybit."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.bybit.com/v5/market/tickers?category=linear"
            )
            data = resp.json()
        items = data.get("result", {}).get("list", [])
        pairs = []
        for t in items:
            symbol = t.get("symbol", "")
            if not symbol.endswith(quote):
                continue
            volume_usdt = float(t.get("volume24h", 0)) * float(t.get("lastPrice", 1))
            if volume_usdt < min_volume_usd:
                continue
            price_change = float(t.get("price24hPcnt", 0)) * 100
            pairs.append({
                "pair": symbol[:-len(quote)] + "/" + quote,
                "symbol": symbol,
                "volume_24h_usdt": round(volume_usdt / 1_000_000, 2),
                "price_change_24h": round(price_change, 2),
                "last_price": float(t.get("lastPrice", 0)),
                "exchange": "bybit",
            })
        pairs.sort(key=lambda x: x["volume_24h_usdt"], reverse=True)
        return pairs[:limit]
    except Exception as e:
        logger.error(f"Bybit top pairs fetch failed: {e}")
        return []


async def get_top_pairs(exchange: str = "binance", limit: int = 50) -> List[Dict]:
    """Unified top pairs fetcher."""
    if exchange in ("bybit", "bybit_testnet"):
        return await get_top_bybit_pairs(limit=limit)
    return await get_top_binance_pairs(limit=limit)
