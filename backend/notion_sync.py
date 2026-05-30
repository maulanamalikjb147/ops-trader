"""Notion sync for trade logging with margin, leverage, and profit USDT fields."""
import logging
import re
import httpx
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def extract_notion_id(text: str) -> str:
    """Extract a 32-char hex Notion page/database ID from a URL or raw string.
    Accepts:
      - bare 32-char hex: '37056703e4a480e9954bf5f0d0fd935d'
      - hyphenated UUID:  '37056703-e4a4-80e9-954b-f5f0d0fd935d'
      - Notion URL:       'https://notion.so/Trading-journal-37056703e4a480e9954bf5f0d0fd935d?v=...'
    """
    if not text:
        return ""
    s = text.strip()
    # Strip hyphens then look for 32-char hex sequence
    cleaned = s.replace("-", "")
    m = re.search(r"([a-f0-9]{32})", cleaned, re.IGNORECASE)
    return m.group(1).lower() if m else ""


# Database schema used by the bot — all columns and their Notion types.
DATABASE_SCHEMA = {
    "Pair": {"title": {}},
    "Side": {"select": {"options": [
        {"name": "LONG", "color": "green"},
        {"name": "SHORT", "color": "red"},
    ]}},
    "Trading Mode": {"select": {"options": [
        {"name": "swing", "color": "blue"},
        {"name": "scalp", "color": "yellow"},
        {"name": "hybrid", "color": "purple"},
    ]}},
    "Exchange": {"select": {"options": [
        {"name": "demo", "color": "gray"},
        {"name": "okx", "color": "blue"},
        {"name": "binance", "color": "yellow"},
        {"name": "bybit", "color": "orange"},
        {"name": "bybit_testnet", "color": "orange"},
        {"name": "bitget", "color": "green"},
    ]}},
    "Entry": {"number": {"format": "number"}},
    "TP1": {"number": {"format": "number"}},
    "TP2": {"number": {"format": "number"}},
    "SL": {"number": {"format": "number"}},
    "Score": {"number": {"format": "number"}},
    "Result": {"select": {"options": [
        {"name": "OPEN", "color": "blue"},
        {"name": "WIN", "color": "green"},
        {"name": "LOSS", "color": "red"},
        {"name": "BEP", "color": "yellow"},
        {"name": "DAILY_SUMMARY", "color": "purple"},
    ]}},
    "Close Reason": {"select": {"options": [
        {"name": "TP1", "color": "green"},
        {"name": "TP2", "color": "green"},
        {"name": "SL", "color": "red"},
        {"name": "BEP", "color": "yellow"},
        {"name": "MANUAL", "color": "gray"},
    ]}},
    "BEP Activated": {"checkbox": {}},
    "Date": {"date": {}},
    "Margin USDT": {"number": {"format": "dollar"}},
    "Leverage": {"number": {"format": "number"}},
    "Profit USDT": {"number": {"format": "dollar"}},
    "PNL USDT": {"number": {"format": "dollar"}},
    "PNL Percent": {"number": {"format": "percent"}},
    "R Value": {"number": {"format": "number"}},
    "Close Price": {"number": {"format": "number"}},
    "Hold Duration": {"rich_text": {}},
}


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

    async def test_connection(self) -> dict:
        """Verify API key works and (if database_id is set) that database is accessible."""
        if not self.api_key:
            return {"ok": False, "error": "No API key configured"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # 1) Test API key by fetching bot user
                resp = await client.get("https://api.notion.com/v1/users/me", headers=self._headers())
                if resp.status_code != 200:
                    return {"ok": False, "error": f"Invalid API key: {resp.json().get('message', resp.text)}"}
                bot_info = resp.json()
                result = {
                    "ok": True,
                    "bot_name": bot_info.get("name", "Unknown"),
                    "bot_id": bot_info.get("id"),
                    "database_accessible": False,
                }
                # 2) If database_id is set, verify it
                if self.database_id:
                    db_resp = await client.get(
                        f"https://api.notion.com/v1/databases/{self.database_id}",
                        headers=self._headers(),
                    )
                    if db_resp.status_code == 200:
                        db_info = db_resp.json()
                        title_parts = db_info.get("title", [])
                        db_title = "".join([t.get("plain_text", "") for t in title_parts]) or "(untitled)"
                        result["database_accessible"] = True
                        result["database_title"] = db_title
                    else:
                        result["database_accessible"] = False
                        result["database_error"] = db_resp.json().get("message", db_resp.text)
                return result
        except Exception as e:
            logger.error(f"Notion test failed: {e}")
            return {"ok": False, "error": str(e)}

    async def auto_create_database(self, parent_page_id: str, title: str = "Trading Journal") -> dict:
        """Create a new database with the full bot schema inside the given parent page.
        Returns dict with 'database_id' on success or 'error' on failure."""
        if not self.api_key:
            return {"error": "No API key configured"}
        page_id = extract_notion_id(parent_page_id)
        if not page_id:
            return {"error": "Invalid parent page ID/URL — could not extract 32-char hex ID"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # First check parent page is accessible to the integration
                check = await client.get(
                    f"https://api.notion.com/v1/pages/{page_id}",
                    headers=self._headers(),
                )
                if check.status_code != 200:
                    err = check.json().get("message", check.text)
                    return {"error": f"Cannot access parent page: {err}. Did you share the page with your integration? Click '...' on the page → 'Add connections' → pick your integration."}
                # Create database
                payload = {
                    "parent": {"type": "page_id", "page_id": page_id},
                    "title": [{"type": "text", "text": {"content": title}}],
                    "properties": DATABASE_SCHEMA,
                }
                resp = await client.post(
                    "https://api.notion.com/v1/databases",
                    headers=self._headers(),
                    json=payload,
                )
                if resp.status_code != 200:
                    return {"error": f"Create failed: {resp.json().get('message', resp.text)}"}
                data = resp.json()
                new_db_id = data.get("id", "").replace("-", "")
                # Update self
                self.database_id = new_db_id
                self.enabled = bool(self.api_key and self.database_id)
                return {"database_id": new_db_id, "url": data.get("url", "")}
        except Exception as e:
            logger.error(f"Notion auto-create db failed: {e}")
            return {"error": str(e)}

    async def create_daily_summary(self, summary: dict) -> str:
        """Create a row in the database that represents the daily summary aggregate."""
        if not self.enabled:
            return ""
        date_str = summary.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        properties = {
            "Pair": self._prop_title(f"📊 DAILY SUMMARY — {date_str}"),
            "Result": self._prop_select("DAILY_SUMMARY"),
            "Date": self._prop_date(date_str),
            "Trading Mode": self._prop_select("hybrid"),
            "Score": self._prop_number(summary.get("total_signals", 0)),
            "Profit USDT": self._prop_number(round(summary.get("net_pnl", 0), 2)),
            "PNL USDT": self._prop_number(round(summary.get("net_pnl", 0), 2)),
            "PNL Percent": self._prop_number(round(summary.get("win_rate", 0) / 100.0, 4)),
            "Hold Duration": self._prop_rich_text(
                f"Total: {summary.get('total_signals', 0)} | "
                f"Win: {summary.get('wins', 0)} | "
                f"Loss: {summary.get('losses', 0)} | "
                f"Win Rate: {summary.get('win_rate', 0)}% | "
                f"Net PNL: ${round(summary.get('net_pnl', 0), 2)}"
            ),
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.notion.com/v1/pages",
                    headers=self._headers(),
                    json={"parent": {"database_id": self.database_id}, "properties": properties},
                )
                if resp.status_code == 200:
                    return resp.json().get("id", "")
                logger.error(f"Notion daily summary failed: {resp.json()}")
        except Exception as e:
            logger.error(f"Notion daily summary error: {e}")
        return ""

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
