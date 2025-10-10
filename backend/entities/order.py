from __future__ import annotations

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import OrderSide, OrderStatus, OrderType

if TYPE_CHECKING:
    from .grid import Grid
    from .trade import Trade


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    grid_id: Mapped[str] = mapped_column(String(36), ForeignKey("grids.id", ondelete="CASCADE"))
    grid_level: Mapped[int] = mapped_column()
    symbol: Mapped[str] = mapped_column(String(16))
    side: Mapped[OrderSide] = mapped_column(SAEnum(OrderSide))
    type: Mapped[OrderType] = mapped_column(SAEnum(OrderType), default=OrderType.LIMIT)
    price: Mapped[float] = mapped_column(Numeric(20, 8))
    quantity: Mapped[float] = mapped_column(Numeric(20, 8))
    filled_quantity: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    status: Mapped[OrderStatus] = mapped_column(SAEnum(OrderStatus), default=OrderStatus.NEW)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    filled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    commission: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    commission_asset: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    binance_order_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    grid: Mapped["Grid"] = relationship(back_populates="orders")
    trades: Mapped[List["Trade"]] = relationship(back_populates="order", cascade="all, delete-orphan")
