from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import TradeSide

if TYPE_CHECKING:
    from .grid import Grid
    from .order import Order


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    grid_id: Mapped[str] = mapped_column(String(36), ForeignKey("grids.id", ondelete="CASCADE"))
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(16))
    side: Mapped[TradeSide] = mapped_column(SAEnum(TradeSide))
    price: Mapped[float] = mapped_column(Numeric(20, 8))
    quantity: Mapped[float] = mapped_column(Numeric(20, 8))
    quote_quantity: Mapped[float] = mapped_column(Numeric(20, 8))
    commission: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    commission_asset: Mapped[str | None] = mapped_column(String(16), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_maker: Mapped[bool] = mapped_column(Boolean, default=False)

    grid: Mapped["Grid"] = relationship(back_populates="trades")
    order: Mapped["Order"] = relationship(back_populates="trades")
