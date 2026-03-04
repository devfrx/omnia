"""O.M.N.I.A. — Database engine and session helpers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession


def create_engine_and_session(
    db_url: str,
) -> tuple[AsyncEngine, async_sessionmaker]:
    """Create an async engine and a session factory.

    Args:
        db_url: SQLAlchemy-style database URL
                (e.g. ``sqlite+aiosqlite:///data/omnia.db``).

    Returns:
        A tuple of ``(AsyncEngine, async_sessionmaker)`` where sessions
        are SQLModel-aware (supporting ``.exec()``).
    """
    engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=SQLModelAsyncSession,
        expire_on_commit=False,
    )
    return engine, session_factory


async def init_db(engine: AsyncEngine) -> None:
    """Create all tables defined by SQLModel metadata.

    Args:
        engine: The async engine to use for DDL execution.
    """
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
