from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime, timezone
from enum import Enum
import uuid


class TradingMode(str, Enum):
    SWING = "swing"
    SCALP = "scalp"
    HYBRID = "hybrid"


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class SignalStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class CloseReason(str, Enum):
    TP1 = "TP1"
    TP2 = "TP2"
    SL = "SL"
    MANUAL = "MANUAL"
    INSTANT_TP = "INSTANT_TP"
    INSTANT_SL = "INSTANT_SL"
    BEP_SL = "BEP_SL"


class Signal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pair: str
    side: str  # LONG or SHORT
    mode: str = "demo"  # demo or live
    trading_mode: str  # swing, scalp, hybrid
    exchange: str = "demo"
    entry_price: float
    tp1: float
    tp2: float
    sl: float
    current_sl: Optional[float] = None  # tracks modified SL (after BEP)
    current_tp: Optional[float] = None  # tracks modified TP
    score: int
    confidence: str
    signal_data: Dict[str, Any] = {}
    rr_ratio: str = "1:2"
    est_hold: str = ""
    auto_bep: bool = True
    partial_close: bool = True
    partial_percent: int = 50
    bep_activated: bool = False
    bep_at: Optional[str] = None
    status: str = "open"
    close_reason: Optional[str] = None
    telegram_message_id: Optional[int] = None
    notion_page_id: Optional[str] = None
    order_id: Optional[str] = None
    position_size: float = 0.0
    margin: float = 0.0
    leverage: int = 1
    signal_only: bool = False
    tp1_hit: bool = False
    partial_closed: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Position(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_id: str
    exchange: str
    order_id: str
    entry_price: float
    close_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    r_value: Optional[float] = None
    hold_duration_minutes: Optional[int] = None
    result: Optional[str] = None
    closed_at: Optional[str] = None
    margin: float = 0.0
    leverage: int = 1
    position_size: float = 0.0


class ExchangeConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    tag: str
    mode: str = "demo"
    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""
    is_active: bool = False
    demo_balance: float = 10000.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BotConfig(BaseModel):
    coins_to_scan: List[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
    swing_min_score: int = 4
    scalp_min_score: int = 3
    hybrid_min_score: int = 4
    swing_enabled: bool = True
    scalp_enabled: bool = False
    hybrid_enabled: bool = True
    scan_interval_swing: int = 300
    scan_interval_scalp: int = 30
    scan_interval_hybrid: int = 60
    auto_bep: bool = True
    partial_close: bool = True
    partial_percent: int = 50
    default_leverage: int = 5
    risk_percent: float = 1.0
    max_open_positions: int = 3
    max_margin: float = 500.0
    is_paused: bool = False
    active_mode: str = "demo"
    active_exchange: str = "demo"
    auto_trade_demo: bool = True
    auto_trade_live: bool = False
    telegram_token: str = ""
    telegram_chat_id: str = ""
    notion_api_key: str = ""
    notion_database_id: str = ""
    coingecko_api_key: str = ""


class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    password_hash: str
    role: str = "user"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PerformanceSummary(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    period: str
    exchange: str
    trading_mode: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    net_pnl: float = 0.0
    net_r: float = 0.0
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
