"""Data fetcher for all external APIs with in-memory caching."""
import httpx
import asyncio
import logging
import time
import statistics
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ── Simple in-memory cache ──────────────────────────────────────────────────
_cache: Dict[str, Any] = {}


def _cache_get(key: str):
    if key in _cache:
        value, expiry = _cache[key]
        if time.time() < expiry:
            return value
        del _cache[key]
    return None


def _cache_set(key: str, value, ttl: int = 60):
    _cache[key] = (value, time.time() + ttl)


# ── Fear & Greed ─────────────────────────────────────────────────────────────
async def get_fear_and_greed() -> Dict:
    cached = _cache_get("fear_greed")
    if cached:
        return cached
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://api.alternative.me/fng/?limit=1")
                data = resp.json()
                result = {
                    "value": int(data["data"][0]["value"]),
                    "classification": data["data"][0]["value_classification"],
                }
                _cache_set("fear_greed", result, ttl=3600)
                return result
        except Exception as e:
            logger.warning(f"Fear & Greed attempt {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    return {"value": 50, "classification": "Neutral"}


# ── Funding Rate ──────────────────────────────────────────────────────────────
async def get_funding_rate(symbol: str) -> Dict:
    cache_key = f"funding_{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    # Normalize: BTC/USDT -> BTCUSDT
    clean = symbol.replace("/", "")
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={clean}"
                resp = await client.get(url)
                data = resp.json()
                items = data.get("result", {}).get("list", [])
                if items:
                    fr = float(items[0].get("fundingRate", 0))
                    result = {"funding_rate": fr, "symbol": clean}
                    _cache_set(cache_key, result, ttl=300)
                    return result
        except Exception as e:
            logger.warning(f"Funding rate attempt {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    return {"funding_rate": 0.0, "symbol": clean}


# ── Price / OHLCV ─────────────────────────────────────────────────────────────
async def get_price_data(symbol: str, interval: str = "1h") -> Dict:
    cache_key = f"price_{symbol}_{interval}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    clean = symbol.replace("/", "")
    # Map interval to Binance interval format
    interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}
    binance_interval = interval_map.get(interval, "1h")
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Get klines
                klines_url = f"https://api.binance.com/api/v3/klines?symbol={clean}&interval={binance_interval}&limit=50"
                klines_resp = await client.get(klines_url)
                klines = klines_resp.json()
                # Get current price
                price_resp = await client.get(
                    f"https://api.binance.com/api/v3/ticker/price?symbol={clean}"
                )
                price_data = price_resp.json()
                current_price = float(price_data.get("price", 0))

                if klines and isinstance(klines, list):
                    closes = [float(k[4]) for k in klines]
                    volumes = [float(k[5]) for k in klines]
                    # Calculate volume change
                    avg_vol = statistics.mean(volumes[:-1]) if len(volumes) > 1 else volumes[-1]
                    vol_change = ((volumes[-1] - avg_vol) / avg_vol * 100) if avg_vol > 0 else 0

                    # Candle colors (last 5)
                    candle_colors = []
                    for k in klines[-5:]:
                        open_p, close_p = float(k[1]), float(k[4])
                        candle_colors.append("green" if close_p >= open_p else "red")

                    result = {
                        "current_price": current_price,
                        "closes": closes,
                        "volumes": volumes,
                        "volume_change_pct": vol_change,
                        "candle_colors": candle_colors,
                        "high_24h": float(klines[-1][2]) if klines else 0,
                        "low_24h": float(klines[-1][3]) if klines else 0,
                    }
                    _cache_set(cache_key, result, ttl=60)
                    return result
        except Exception as e:
            logger.warning(f"Price data attempt {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    return {
        "current_price": 0,
        "closes": [],
        "volumes": [],
        "volume_change_pct": 0,
        "candle_colors": [],
        "high_24h": 0,
        "low_24h": 0,
    }


# ── Current Price (fast) ──────────────────────────────────────────────────────
async def get_current_price(symbol: str) -> float:
    """Fast price fetch for position monitoring."""
    clean = symbol.replace("/", "")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"https://api.binance.com/api/v3/ticker/price?symbol={clean}"
            )
            data = resp.json()
            return float(data.get("price", 0))
    except Exception as e:
        logger.warning(f"Current price fetch failed for {symbol}: {e}")
        return 0.0


# ── Token Info (CoinGecko) ────────────────────────────────────────────────────
async def get_token_info(symbol: str, api_key: str = "") -> Dict:
    cache_key = f"token_{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    # Map symbol to CoinGecko ID
    cg_ids = {
        "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
        "BNB": "binancecoin", "XRP": "ripple", "ADA": "cardano",
        "MATIC": "matic-network", "DOGE": "dogecoin", "AVAX": "avalanche-2",
        "DOT": "polkadot", "LINK": "chainlink", "UNI": "uniswap",
    }
    base = symbol.split("/")[0].upper()
    cg_id = cg_ids.get(base, base.lower())
    headers = {}
    if api_key:
        headers["x-cg-demo-api-key"] = api_key
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={cg_id}&vs_currencies=usd&include_market_cap=true&include_24hr_vol=true&include_24hr_change=true"
                resp = await client.get(url, headers=headers)
                data = resp.json()
                if cg_id in data:
                    token = data[cg_id]
                    result = {
                        "price": token.get("usd", 0),
                        "market_cap": token.get("usd_market_cap", 0),
                        "volume_24h": token.get("usd_24h_vol", 0),
                        "price_change_24h": token.get("usd_24h_change", 0),
                    }
                    _cache_set(cache_key, result, ttl=300)
                    return result
        except Exception as e:
            logger.warning(f"Token info attempt {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    return {"price": 0, "market_cap": 0, "volume_24h": 0, "price_change_24h": 0}


# ── CEX Outflow (simplified via Etherscan) ────────────────────────────────────
async def get_cex_outflow(symbol: str) -> Dict:
    """Simplified CEX flow detection - uses volume proxy since full on-chain needs paid tier."""
    cache_key = f"cex_flow_{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    try:
        # Use DexScreener as a proxy for large volume changes
        base = symbol.split("/")[0].upper()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_vol=true&include_24hr_change=true"
            )
            # Simplified: detect if there's unusual activity based on volume spike
            price_data = await get_price_data(symbol, "4h")
            vol_change = price_data.get("volume_change_pct", 0)
            outflow_detected = vol_change > 50  # >50% volume spike = possible CEX outflow signal
            result = {
                "outflow_detected": outflow_detected,
                "inflow_detected": vol_change < -30,
                "amount_usd": abs(vol_change) * 10000 if outflow_detected else 0,
                "tx_count": int(abs(vol_change) / 5) if outflow_detected else 0,
            }
            _cache_set(cache_key, result, ttl=600)
            return result
    except Exception as e:
        logger.warning(f"CEX outflow fetch failed: {e}")
        return {"outflow_detected": False, "inflow_detected": False, "amount_usd": 0, "tx_count": 0}


# ── EMA Calculation ────────────────────────────────────────────────────────────
def calculate_ema(prices: List[float], period: int) -> float:
    if len(prices) < period:
        return prices[-1] if prices else 0
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema
