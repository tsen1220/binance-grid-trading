from __future__ import annotations

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SAEnum, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import GridStatus

if TYPE_CHECKING:
    from .grid_level import GridLevel
    from .order import Order
    from .trade import Trade


class Grid(Base):
    __tablename__ = "grids"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    trading_pair: Mapped[str] = mapped_column(String(16))
    upper_price: Mapped[float] = mapped_column(Numeric(20, 8))
    lower_price: Mapped[float] = mapped_column(Numeric(20, 8))
    grid_count: Mapped[int] = mapped_column(Integer)
    grid_spacing: Mapped[float] = mapped_column(Numeric(20, 8))
    total_investment: Mapped[float] = mapped_column(Numeric(20, 8))
    investment_per_grid: Mapped[float] = mapped_column(Numeric(20, 8))
    status: Mapped[GridStatus] = mapped_column(SAEnum(GridStatus), default=GridStatus.RUNNING)
    runtime_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    levels: Mapped[List["GridLevel"]] = relationship(back_populates="grid", cascade="all, delete-orphan")
    orders: Mapped[List["Order"]] = relationship(back_populates="grid", cascade="all, delete-orphan")
    trades: Mapped[List["Trade"]] = relationship(back_populates="grid", cascade="all, delete-orphan")
