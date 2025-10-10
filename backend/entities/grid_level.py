from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import GridLevelStatus

if TYPE_CHECKING:
    from .grid import Grid


class GridLevel(Base):
    __tablename__ = "grid_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grid_id: Mapped[str] = mapped_column(String(36), ForeignKey("grids.id", ondelete="CASCADE"))
    level_index: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Numeric(20, 8))
    status: Mapped[GridLevelStatus] = mapped_column(SAEnum(GridLevelStatus), default=GridLevelStatus.IDLE)
    buy_order_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    sell_order_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    grid: Mapped["Grid"] = relationship(back_populates="levels")
