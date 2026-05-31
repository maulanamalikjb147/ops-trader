"""Fetch top trading pairs by volume from OKX public API (SWAP futures only)."""
import httpx
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


async def get_top_okx_pairs(quote="USDT", limit=50, min_volume_usd=1_000_000) -> List[Dict]:
    """Fetch top N USDT perpetual SWAP futures pairs by 24h volume from OKX."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
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
            tick_resp = await client.get(
                "https://www.okx.com/api/v5/market/tickers",
                params={"instType": "SWAP"},
            )
            tickers = tick_resp.json().get("data", [])
        pairs = []
        for t in tickers:
            inst_id = t.get("instId", "")
            if inst_id not in usdt_swaps:
                continue
            vol_usd_field = t.get("volUsd24h")
            if vol_usd_field is not None:
                volume_usdt = float(vol_usd_field or 0)
            else:
                volume_usdt = float(t.get("vol24h", 0) or 0) * float(t.get("last", 0) or 0)
            if volume_usdt < min_volume_usd:
                continue
            last_price = float(t.get("last", 0) or 0)
            open_price = float(t.get("open24h", 0) or 0)
            price_change = ((last_price - open_price) / open_price * 100) if open_price else 0
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
    """Unified top FUTURES pairs fetcher — always uses OKX."""
    return await get_top_okx_pairs(limit=limit)
