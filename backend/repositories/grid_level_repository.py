from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.entities import GridLevel
from .base import BaseRepository


class GridLevelRepository(BaseRepository[GridLevel]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, GridLevel)

    def get_by_grid_id(self, grid_id: str) -> List[GridLevel]:
        stmt = select(GridLevel).where(GridLevel.grid_id == grid_id).order_by(GridLevel.level_index.asc())
        return list(self.session.execute(stmt).scalars().all())
