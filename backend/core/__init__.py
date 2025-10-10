from importlib import import_module
from typing import TYPE_CHECKING

__all__ = [
    "Balance",
    "BinanceClient",
    "SymbolInfo",
    "GridEngine",
    "GridInitializationResult",
    "GridCalculationResult",
    "GridLevelPlan",
    "GridStrategy",
    "OrderManager",
    "OrderPlan",
]

_lazy_exports = {
    "Balance": ("binance_client", "Balance"),
    "BinanceClient": ("binance_client", "BinanceClient"),
    "SymbolInfo": ("binance_client", "SymbolInfo"),
    "GridEngine": ("grid_engine", "GridEngine"),
    "GridInitializationResult": ("grid_engine", "GridInitializationResult"),
    "GridCalculationResult": ("grid_strategy", "GridCalculationResult"),
    "GridLevelPlan": ("grid_strategy", "GridLevelPlan"),
    "GridStrategy": ("grid_strategy", "GridStrategy"),
    "OrderManager": ("order_manager", "OrderManager"),
    "OrderPlan": ("order_manager", "OrderPlan"),
}


def __getattr__(name: str):
    if name not in _lazy_exports:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _lazy_exports[name]
    module = import_module(f"{__name__}.{module_name}")
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


if TYPE_CHECKING:
    from .binance_client import Balance, BinanceClient, SymbolInfo
    from .grid_engine import GridEngine, GridInitializationResult
    from .grid_strategy import GridCalculationResult, GridLevelPlan, GridStrategy
    from .order_manager import OrderManager, OrderPlan
