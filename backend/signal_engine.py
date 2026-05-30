"""Signal scoring engine for Swing, Scalp, and Hybrid trading modes."""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from data_fetcher import (
    get_fear_and_greed, get_funding_rate, get_price_data,
    get_cex_outflow, calculate_ema, get_token_info
)

logger = logging.getLogger(__name__)


# ── TP/SL Configuration ────────────────────────────────────────────────────────
TPSL_CONFIG = {
    "swing":  {"tp1": 0.025, "tp2": 0.050, "sl": 0.025},
    "scalp":  {"tp1": 0.005, "tp2": 0.010, "sl": 0.004},
    "hybrid": {"tp1": 0.015, "tp2": 0.050, "sl": 0.025},
}

EST_HOLD = {
    "swing": "2-5 hari",
    "scalp": "5-30 menit",
    "hybrid": "4-24 jam",
}


def calculate_tp_sl(entry: float, side: str, mode: str) -> Dict:
    cfg = TPSL_CONFIG.get(mode, TPSL_CONFIG["swing"])
    multiplier = 1 if side == "LONG" else -1
    tp1 = entry * (1 + multiplier * cfg["tp1"])
    tp2 = entry * (1 + multiplier * cfg["tp2"])
    sl  = entry * (1 - multiplier * cfg["sl"])
    risk = abs(entry - sl)
    reward = abs(tp2 - entry)
    rr = round(reward / risk, 1) if risk > 0 else 2.0
    return {
        "tp1": round(tp1, 6),
        "tp2": round(tp2, 6),
        "sl": round(sl, 6),
        "rr_ratio": f"1:{rr}",
    }


# ── Swing Mode ─────────────────────────────────────────────────────────────────
async def score_swing(symbol: str, side: str) -> Dict[str, Any]:
    fg = await get_fear_and_greed()
    fr = await get_funding_rate(symbol)
    pd = await get_price_data(symbol, "4h")
    cex = await get_cex_outflow(symbol)

    fg_val = fg["value"]
    funding = fr["funding_rate"]
    vol_change = pd.get("volume_change_pct", 0)
    closes = pd.get("closes", [])
    ema20 = calculate_ema(closes, 20) if len(closes) >= 20 else (closes[-1] if closes else 0)
    current_price = pd.get("current_price", 0)

    scores = {}
    if side == "LONG":
        scores["fear_greed"] = {"value": fg_val, "pass": fg_val < 40, "label": f"F&G {fg_val} < 40"}
        scores["funding_rate"] = {"value": funding, "pass": funding < -0.0001, "label": f"FR {funding:.4f} < -0.01%"}
        scores["volume_spike"] = {"value": vol_change, "pass": vol_change > 30, "label": f"Vol +{vol_change:.0f}% > 30%"}
        scores["ema_check"] = {"pass": current_price > ema20 if ema20 > 0 else False, "label": f"Price {current_price:.2f} > EMA20 {ema20:.2f}"}
        scores["cex_flow"] = {"outflow": cex["outflow_detected"], "pass": cex["outflow_detected"], "amount": cex["amount_usd"], "label": f"CEX outflow: {'YES' if cex['outflow_detected'] else 'NO'}"}
    else:  # SHORT
        scores["fear_greed"] = {"value": fg_val, "pass": fg_val > 70, "label": f"F&G {fg_val} > 70"}
        scores["funding_rate"] = {"value": funding, "pass": funding > 0.0003, "label": f"FR {funding:.4f} > 0.03%"}
        scores["volume_spike"] = {"value": vol_change, "pass": vol_change > 30, "label": f"Vol +{vol_change:.0f}% > 30%"}
        scores["ema_check"] = {"pass": current_price < ema20 if ema20 > 0 else False, "label": f"Price {current_price:.2f} < EMA20 {ema20:.2f}"}
        scores["cex_flow"] = {"inflow": cex["inflow_detected"], "pass": cex["inflow_detected"], "amount": cex["amount_usd"], "label": f"CEX inflow: {'YES' if cex['inflow_detected'] else 'NO'}"}

    total = sum(1 for v in scores.values() if v.get("pass"))
    return {"scores": scores, "total": total, "required": 4, "entry_price": current_price}


# ── Scalp Mode ─────────────────────────────────────────────────────────────────
async def score_scalp(symbol: str, side: str) -> Dict[str, Any]:
    fg = await get_fear_and_greed()
    fr = await get_funding_rate(symbol)
    pd5m = await get_price_data(symbol, "5m")

    funding = fr["funding_rate"]
    vol_change = pd5m.get("volume_change_pct", 0)
    candles = pd5m.get("candle_colors", [])
    current_price = pd5m.get("current_price", 0)
    fg_val = fg["value"]

    scores = {}
    if side == "LONG":
        scores["funding_extreme"] = {"value": funding, "pass": funding < -0.0002, "label": f"FR {funding:.4f} < -0.02%"}
        scores["volume_spike"] = {"value": vol_change, "pass": vol_change > 50, "label": f"Vol +{vol_change:.0f}% > 50%"}
        scores["momentum"] = {"pass": candles[-3:] == ["green", "green", "green"] if len(candles) >= 3 else False, "label": f"3 green candles: {candles[-3:]}"}
        scores["fg_ok"] = {"value": fg_val, "pass": fg_val < 75, "label": f"F&G {fg_val} not extreme bearish"}
        scores["liquidity"] = {"pass": vol_change > 20, "label": f"Volume adequate: {vol_change:.0f}%"}
    else:
        scores["funding_extreme"] = {"value": funding, "pass": funding > 0.0004, "label": f"FR {funding:.4f} > 0.04%"}
        scores["volume_spike"] = {"value": vol_change, "pass": vol_change > 50, "label": f"Vol +{vol_change:.0f}% > 50%"}
        scores["momentum"] = {"pass": candles[-3:] == ["red", "red", "red"] if len(candles) >= 3 else False, "label": f"3 red candles: {candles[-3:]}"}
        scores["fg_ok"] = {"value": fg_val, "pass": fg_val > 25, "label": f"F&G {fg_val} not extreme bullish"}
        scores["liquidity"] = {"pass": vol_change > 20, "label": f"Volume adequate: {vol_change:.0f}%"}

    total = sum(1 for v in scores.values() if v.get("pass"))
    return {"scores": scores, "total": total, "required": 3, "entry_price": current_price}


# ── Hybrid Mode ────────────────────────────────────────────────────────────────
async def score_hybrid(symbol: str, side: str) -> Dict[str, Any]:
    cex = await get_cex_outflow(symbol)
    fr = await get_funding_rate(symbol)
    pd1h = await get_price_data(symbol, "1h")
    pd4h = await get_price_data(symbol, "4h")
    pd15m = await get_price_data(symbol, "15m")

    funding = fr["funding_rate"]
    vol_1h = pd1h.get("volume_change_pct", 0)
    candles_15m = pd15m.get("candle_colors", [])
    current_price = pd1h.get("current_price", 0)
    closes_4h = pd4h.get("closes", [])

    # Higher low / lower high detection (simplified)
    higher_low = False
    lower_high = False
    if len(closes_4h) >= 10:
        recent = closes_4h[-10:]
        lows = [min(recent[i:i+3]) for i in range(0, len(recent)-2, 3)]
        highs = [max(recent[i:i+3]) for i in range(0, len(recent)-2, 3)]
        if len(lows) >= 2:
            higher_low = lows[-1] > lows[-2]
            lower_high = highs[-1] < highs[-2] if len(highs) >= 2 else False

    scores = {}
    if side == "LONG":
        scores["cex_flow"] = {"pass": cex["outflow_detected"], "label": f"CEX outflow: {'YES' if cex['outflow_detected'] else 'NO'}"}
        scores["funding_rate"] = {"value": funding, "pass": funding < 0.0001, "label": f"FR {funding:.4f} aligned LONG"}
        scores["volume_spike"] = {"value": vol_1h, "pass": vol_1h > 25, "label": f"Vol 1H +{vol_1h:.0f}% > 25%"}
        scores["price_structure"] = {"pass": higher_low, "label": f"Higher low on 4H: {'YES' if higher_low else 'NO'}"}
        scores["ltf_pullback"] = {"pass": candles_15m[-1:] == ["green"] if candles_15m else False, "label": f"15m pullback green: {candles_15m[-1] if candles_15m else 'N/A'}"}
    else:
        scores["cex_flow"] = {"pass": cex["inflow_detected"], "label": f"CEX inflow: {'YES' if cex['inflow_detected'] else 'NO'}"}
        scores["funding_rate"] = {"value": funding, "pass": funding > 0.0001, "label": f"FR {funding:.4f} aligned SHORT"}
        scores["volume_spike"] = {"value": vol_1h, "pass": vol_1h > 25, "label": f"Vol 1H +{vol_1h:.0f}% > 25%"}
        scores["price_structure"] = {"pass": lower_high, "label": f"Lower high on 4H: {'YES' if lower_high else 'NO'}"}
        scores["ltf_pullback"] = {"pass": candles_15m[-1:] == ["red"] if candles_15m else False, "label": f"15m pullback red: {candles_15m[-1] if candles_15m else 'N/A'}"}

    total = sum(1 for v in scores.values() if v.get("pass"))
    return {"scores": scores, "total": total, "required": 4, "entry_price": current_price}


# ── Generate Signal ────────────────────────────────────────────────────────────
async def generate_signal(symbol: str, trading_mode: str, side: str = None) -> Optional[Dict]:
    """Generate signal for a symbol. If side is None, checks both LONG and SHORT."""
    sides = [side] if side else ["LONG", "SHORT"]
    
    for s in sides:
        try:
            if trading_mode == "swing":
                result = await score_swing(symbol, s)
            elif trading_mode == "scalp":
                result = await score_scalp(symbol, s)
            elif trading_mode == "hybrid":
                result = await score_hybrid(symbol, s)
            else:
                continue

            if result["total"] >= result["required"] and result["entry_price"] > 0:
                tp_sl = calculate_tp_sl(result["entry_price"], s, trading_mode)
                fg = await get_fear_and_greed()
                fr = await get_funding_rate(symbol)
                pd = await get_price_data(symbol, "4h")

                return {
                    "pair": symbol,
                    "side": s,
                    "trading_mode": trading_mode,
                    "entry_price": result["entry_price"],
                    "tp1": tp_sl["tp1"],
                    "tp2": tp_sl["tp2"],
                    "sl": tp_sl["sl"],
                    "current_sl": tp_sl["sl"],
                    "current_tp": tp_sl["tp1"],
                    "score": result["total"],
                    "confidence": f"{result['total']}/{len(result['scores'])}",
                    "signal_data": result["scores"],
                    "rr_ratio": tp_sl["rr_ratio"],
                    "est_hold": EST_HOLD.get(trading_mode, ""),
                    "fear_greed": fg,
                    "funding_rate": fr["funding_rate"],
                    "volume_spike": pd.get("volume_change_pct", 0),
                }
        except Exception as e:
            logger.error(f"Signal generation failed for {symbol} {s} {trading_mode}: {e}")

    return None


async def scan_all(symbols: List[str], trading_mode: str) -> List[Dict]:
    """Scan all symbols and return valid signals."""
    tasks = [generate_signal(sym, trading_mode) for sym in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if r and not isinstance(r, Exception)]
