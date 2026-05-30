"""Fetch top trading pairs by volume from exchange public APIs."""
import httpx
import asyncio
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


async def get_top_binance_pairs(quote="USDT", limit=50, min_volume_usd=10_000_000) -> List[Dict]:
    """Fetch top N USDT-M perpetual FUTURES pairs by 24h volume from Binance."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # fapi = USDT-M futures (perpetual). Filter only PERPETUAL contracts.
            resp = await client.get("https://fapi.binance.com/fapi/v1/ticker/24hr")
            tickers = resp.json()
        pairs = []
        for t in tickers:
            symbol = t.get("symbol", "")
            if not symbol.endswith(quote):
                continue
            # Skip dated futures (e.g. BTCUSDT_240927) — keep only PERPETUAL
            if "_" in symbol:
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
        # Sort by volume descending (highest transaction volume first)
        pairs.sort(key=lambda x: x["volume_24h_usdt"], reverse=True)
        return pairs[:limit]
    except Exception as e:
        logger.error(f"Binance futures top pairs fetch failed: {e}")
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


async def get_top_okx_pairs(quote="USDT", limit=50, min_volume_usd=1_000_000) -> List[Dict]:
    """Fetch top N USDT perpetual SWAP futures pairs by 24h volume from OKX."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # 1) Get all SWAP instruments (perpetual futures)
            inst_resp = await client.get(
                "https://www.okx.com/api/v5/public/instruments",
                params={"instType": "SWAP"},
            )
            instruments = inst_resp.json().get("data", [])
            usdt_swaps = {
                i["instId"]
                for i in instruments
                if i.get("settleCcy") == quote and i.get("state") == "live"
            }
            # 2) Get 24h tickers for all SWAPs
            tick_resp = await client.get(
                "https://www.okx.com/api/v5/market/tickers",
                params={"instType": "SWAP"},
            )
            tickers = tick_resp.json().get("data", [])
        pairs = []
        for t in tickers:
            inst_id = t.get("instId", "")  # e.g. "BTC-USDT-SWAP"
            if inst_id not in usdt_swaps:
                continue
            # For OKX SWAP: volCcy24h = number of contracts (NOT USDT).
            # Compute notional USD volume = vol24h (contracts) * last_price * contract_multiplier.
            # OKX has `volUsd24h` for USDT-margined swaps which is the cleanest.
            vol_usd_field = t.get("volUsd24h")
            if vol_usd_field is not None:
                volume_usdt = float(vol_usd_field or 0)
            else:
                # Fallback: contracts * price
                volume_usdt = float(t.get("vol24h", 0) or 0) * float(t.get("last", 0) or 0)
            if volume_usdt < min_volume_usd:
                continue
            last_price = float(t.get("last", 0) or 0)
            open_price = float(t.get("open24h", 0) or 0)
            price_change = ((last_price - open_price) / open_price * 100) if open_price else 0
            # OKX: BTC-USDT-SWAP → BTC/USDT
            base = inst_id.split("-")[0]
            pairs.append({
                "pair": f"{base}/{quote}",
                "symbol": inst_id,
                "volume_24h_usdt": round(volume_usdt / 1_000_000, 2),
                "price_change_24h": round(price_change, 2),
                "last_price": last_price,
                "exchange": "okx",
            })
        pairs.sort(key=lambda x: x["volume_24h_usdt"], reverse=True)
        return pairs[:limit]
    except Exception as e:
        logger.error(f"OKX futures top pairs fetch failed: {e}")
        return []


async def get_top_pairs(exchange: str = "okx", limit: int = 50) -> List[Dict]:
    """Unified top FUTURES pairs fetcher by 24h volume.
    Routes to the correct exchange. Demo / unknown → OKX (most permissive public API)."""
    ex = (exchange or "").lower()
    if ex.startswith("bybit"):
        return await get_top_bybit_pairs(limit=limit)
    if ex == "binance":
        return await get_top_binance_pairs(limit=limit)
    # okx / demo / bitget / unknown → OKX (default, no auth required, futures-native)
    return await get_top_okx_pairs(limit=limit)
