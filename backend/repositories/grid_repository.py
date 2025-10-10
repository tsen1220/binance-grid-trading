from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.entities import Grid, GridStatus
from .base import BaseRepository


class GridRepository(BaseRepository[Grid]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Grid)

    def find_active_grid(self) -> Optional[Grid]:
        stmt: Select[Grid] = (
            select(Grid)
            .where(Grid.status == GridStatus.RUNNING)
            .order_by(Grid.created_at.desc())
            .limit(1)
        )
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def paginate_history(self, *, page: int, limit: int) -> Tuple[List[Grid], int]:
        offset = (page - 1) * limit
        stmt = (
            select(Grid)
            .where(Grid.status != GridStatus.RUNNING)
            .order_by(Grid.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        grids = self.session.execute(stmt).scalars().all()
        total_stmt = select(func.count()).select_from(Grid).where(Grid.status != GridStatus.RUNNING)
        total = int(self.session.execute(total_stmt).scalar_one())
        return grids, total
