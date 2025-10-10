from __future__ import annotations

from typing import Any, Dict, Generic, Iterable, List, Optional, Sequence, Tuple, Type, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Generic repository wrapping common CRUD operations."""

    def __init__(self, session: Session, model: Type[T]):
        self.session = session
        self.model = model

    def find(self, identifier: Any) -> Optional[T]:
        return self.session.get(self.model, identifier)

    def find_all(self, *, filters: Optional[Dict[str, Any]] = None, order_by: Optional[Sequence[Any]] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> List[T]:
        stmt: Select[Any] = select(self.model)
        if filters:
            for field, value in filters.items():
                stmt = stmt.where(getattr(self.model, field) == value)
        if order_by:
            stmt = stmt.order_by(*order_by)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        result = self.session.execute(stmt)
        return list(result.scalars())

    def create(self, data: Dict[str, Any]) -> T:
        instance = self.model(**data)
        self.session.add(instance)
        self.session.flush()
        return instance

    def create_many(self, items: Iterable[Dict[str, Any]]) -> List[T]:
        instances = [self.model(**item) for item in items]
        self.session.add_all(instances)
        self.session.flush()
        return instances

    def update(self, identifier: Any, updates: Dict[str, Any]) -> T:
        instance = self.find(identifier)
        if not instance:
            raise ValueError(f"{self.model.__name__} with id {identifier} not found")
        for field, value in updates.items():
            setattr(instance, field, value)
        self.session.flush()
        return instance

    def delete(self, identifier: Any) -> None:
        instance = self.find(identifier)
        if instance:
            self.session.delete(instance)
            self.session.flush()

    def count(self, *, filters: Optional[Dict[str, Any]] = None) -> int:
        stmt: Select[Any] = select(func.count()).select_from(self.model)
        if filters:
            for field, value in filters.items():
                stmt = stmt.where(getattr(self.model, field) == value)
        result = self.session.execute(stmt)
        return int(result.scalar_one())
