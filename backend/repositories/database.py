from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.entities import Base

from backend.config import settings


def _make_engine(url: str):
    engine_kwargs: dict[str, Any] = {"echo": settings.database.echo, "future": True}
    if url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **engine_kwargs)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create database tables."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope for scripts or tests."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_test_session(database_url: str) -> Tuple[sessionmaker, Any]:
    """Create an isolated engine/session factory for testing."""
    test_engine = _make_engine(database_url)
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    session_factory = sessionmaker(bind=test_engine, autocommit=False, autoflush=False, expire_on_commit=False, future=True)
    return session_factory, test_engine
