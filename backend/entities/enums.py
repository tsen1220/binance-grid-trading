from enum import Enum


class GridStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"


class GridLevelStatus(str, Enum):
    IDLE = "idle"
    BUY_PENDING = "buy_pending"
    SELL_PENDING = "sell_pending"
    BOTH_PENDING = "both_pending"


class OrderStatus(str, Enum):
    NEW = "NEW"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
