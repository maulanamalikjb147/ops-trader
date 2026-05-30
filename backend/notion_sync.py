"""Notion sync for trade logging with margin, leverage, and profit USDT fields."""
import logging
import httpx
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class NotionSync:
    def __init__(self, api_key: str = "", database_id: str = ""):
        self.api_key = api_key
        self.database_id = database_id
        self.enabled = bool(api_key and database_id)

    def reconfigure(self, api_key: str, database_id: str):
        self.api_key = api_key
        self.database_id = database_id
        self.enabled = bool(api_key and database_id)

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

    def _prop_title(self, text: str):
        return {"title": [{"text": {"content": text}}]}

    def _prop_select(self, name: str):
        return {"select": {"name": name}}

    def _prop_number(self, value):
        return {"number": value if value is not None else 0}

    def _prop_checkbox(self, val: bool):
        return {"checkbox": val}

    def _prop_date(self, iso: str):
        return {"date": {"start": iso}}

    def _prop_rich_text(self, text: str):
        return {"rich_text": [{"text": {"content": str(text)}}]}

    async def create_signal_page(self, signal: dict) -> str:
        """Create Notion page when signal is generated."""
        if not self.enabled:
            logger.info(f"[Notion disabled] Would create page for {signal.get('pair')}")
            return ""
        pair = signal.get("pair", "")
        side = signal.get("side", "")
        tm = signal.get("trading_mode", "swing")
        exchange = signal.get("exchange", "demo")
        entry = signal.get("entry_price", 0)
        tp1 = signal.get("tp1", 0)
        tp2 = signal.get("tp2", 0)
        sl = signal.get("sl", 0)
        score = signal.get("score", 0)
        margin = signal.get("margin", 0)
        leverage = signal.get("leverage", 1)
        now = datetime.now(timezone.utc).isoformat()

        properties = {
            "Pair": self._prop_title(f"{pair} {side}"),
            "Side": self._prop_select(side),
            "Trading Mode": self._prop_select(tm),
            "Exchange": self._prop_select(exchange),
            "Entry": self._prop_number(entry),
            "TP1": self._prop_number(tp1),
            "TP2": self._prop_number(tp2),
            "SL": self._prop_number(sl),
            "Score": self._prop_number(score),
            "Result": self._prop_select("OPEN"),
            "BEP Activated": self._prop_checkbox(False),
            "Date": self._prop_date(now),
            "Margin USDT": self._prop_number(round(margin, 2)),
            "Leverage": self._prop_number(leverage),
            "Profit USDT": self._prop_number(0),
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.notion.com/v1/pages",
                    headers=self._headers(),
                    json={"parent": {"database_id": self.database_id}, "properties": properties},
                )
                data = resp.json()
                if resp.status_code == 200:
                    return data.get("id", "")
                else:
                    logger.error(f"Notion create page failed: {data}")
        except Exception as e:
            logger.error(f"Notion create page error: {e}")
        return ""

    async def update_position_closed(self, signal: dict, position: dict):
        """Update Notion page when position is closed."""
        page_id = signal.get("notion_page_id")
        if not self.enabled or not page_id:
            logger.info(f"[Notion disabled/no page_id] Would update closed position for {signal.get('pair')}")
            return
        pnl = position.get("pnl", 0)
        is_win = pnl >= 0
        result = "WIN" if is_win else "LOSS"
        reason = position.get("result", "CLOSED")
        close_price = position.get("close_price", 0)
        pnl_pct = position.get("pnl_percent", 0)
        r_val = position.get("r_value", 0)
        hold = position.get("hold_duration_minutes", 0)
        margin = position.get("margin", 0)
        leverage = position.get("leverage", 1)

        properties = {
            "Result": self._prop_select(result),
            "Close Reason": self._prop_select(reason),
            "Close Price": self._prop_number(close_price),
            "PNL USDT": self._prop_number(round(pnl, 4)),
            "Profit USDT": self._prop_number(round(pnl, 4)),
            "PNL Percent": self._prop_number(round(pnl_pct, 2)),
            "R Value": self._prop_number(round(r_val, 2)),
            "Hold Duration": self._prop_rich_text(f"{hold}m"),
            "Margin USDT": self._prop_number(round(margin, 2)),
            "Leverage": self._prop_number(leverage),
            "BEP Activated": self._prop_checkbox(signal.get("bep_activated", False)),
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                await client.patch(
                    f"https://api.notion.com/v1/pages/{page_id}",
                    headers=self._headers(),
                    json={"properties": properties},
                )
        except Exception as e:
            logger.error(f"Notion update closed failed: {e}")

    async def update_bep_activated(self, signal: dict):
        page_id = signal.get("notion_page_id")
        if not self.enabled or not page_id:
            return
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                await client.patch(
                    f"https://api.notion.com/v1/pages/{page_id}",
                    headers=self._headers(),
                    json={"properties": {
                        "BEP Activated": self._prop_checkbox(True),
                        "Result": self._prop_select("BEP"),
                    }},
                )
        except Exception as e:
            logger.error(f"Notion BEP update failed: {e}")

    async def generate_monthly_summary(self, db, period: str) -> dict:
        """Generate monthly summary from database."""
        signals = await db.signals.find({
            "status": "closed",
            "created_at": {"$gte": f"{period}-01", "$lt": f"{period}-32"},
        }).to_list(1000)
        positions = await db.positions.find({"signal_id": {"$in": [s["id"] for s in signals]}}).to_list(1000)
        pos_map = {p["signal_id"]: p for p in positions}

        summary = {"period": period, "total": 0, "wins": 0, "losses": 0, "net_pnl": 0.0}
        for s in signals:
            p = pos_map.get(s["id"])
            if p:
                pnl = p.get("pnl", 0)
                summary["total"] += 1
                if pnl >= 0:
                    summary["wins"] += 1
                else:
                    summary["losses"] += 1
                summary["net_pnl"] += pnl
        summary["win_rate"] = round(summary["wins"] / summary["total"] * 100, 1) if summary["total"] > 0 else 0
        return summary


# Global instance
notion_sync = NotionSync()
