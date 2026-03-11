"""O.M.N.I.A. — Database engine and session helpers."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession
from loguru import logger


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
    engine_kwargs: dict[str, Any] = {
        "echo": False,
        "pool_pre_ping": True,
    }

    is_sqlite = db_url.startswith("sqlite")
    is_memory_sqlite = db_url in (
        "sqlite+aiosqlite://",
        "sqlite+aiosqlite:///:memory:",
    )

    if is_sqlite and is_memory_sqlite:
        # In-memory SQLite MUST use StaticPool so all sessions share
        # the single underlying connection (data lives only in memory).
        engine_kwargs["poolclass"] = StaticPool
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    elif is_sqlite:
        # File-based SQLite with WAL mode supports concurrent readers
        # + one writer.  Use a regular pool (NullPool avoided — we want
        # connection reuse) so each session gets its own connection with
        # an independent transaction snapshot.  This prevents stale reads
        # when a long-lived WebSocket session holds an implicit read
        # transaction while plugin tools query the DB separately.
        engine_kwargs["pool_size"] = 5
        engine_kwargs["max_overflow"] = 3
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # Connection pool tuning for non-SQLite databases (e.g. PostgreSQL).
        engine_kwargs["pool_size"] = 5
        engine_kwargs["max_overflow"] = 10

    engine = create_async_engine(
        db_url,
        **engine_kwargs,
    )

    # Enable WAL journal mode and busy timeout for file-based SQLite.
    # WAL allows concurrent reads during writes and busy_timeout prevents
    # immediate "database is locked" errors under concurrent access.
    if is_sqlite and not is_memory_sqlite:
        from sqlalchemy import event

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    session_factory = async_sessionmaker(
        engine,
        class_=SQLModelAsyncSession,
        expire_on_commit=False,
    )
    return engine, session_factory


async def init_db(engine: AsyncEngine) -> None:
    """Create all tables defined by SQLModel metadata.

    Also applies lightweight schema migrations for columns added after
    initial table creation (SQLAlchemy ``create_all`` only creates
    *missing tables*, not missing columns).

    Args:
        engine: The async engine to use for DDL execution.
    """
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # -- Lightweight column migrations --------------------------------------
    _COLUMN_MIGRATIONS: list[tuple[str, str, str]] = [
        ("messages", "thinking_content", "TEXT"),
        ("messages", "tool_calls", "TEXT"),
        ("messages", "tool_call_id", "VARCHAR(64)"),
        ("agent_tasks", "time_utc", "VARCHAR(5)"),
        ("agent_tasks", "time_local", "VARCHAR(5)"),
    ]

    async with engine.begin() as conn:
        for table, column, col_type in _COLUMN_MIGRATIONS:
            exists = await conn.run_sync(
                lambda sync_conn, t=table, c=column: c
                in [
                    col["name"]
                    for col in sa.inspect(sync_conn).get_columns(t)
                ]
                if sa.inspect(sync_conn).has_table(t)
                else True
            )
            if not exists:
                await conn.execute(
                    sa.text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                )
                logger.info("Added missing column {}.{}", table, column)

    # -- SQLite CHECK constraint migration for agent_tasks ------------------
    # SQLite doesn't support ALTER TABLE DROP/ADD CONSTRAINT, so we must
    # recreate the table to update ck_task_trigger_type to include 'daily_at'.
    await _migrate_agent_tasks_trigger_constraint(engine)


async def _migrate_agent_tasks_trigger_constraint(
    engine: AsyncEngine,
) -> None:
    """Recreate agent_tasks table if CHECK constraint is outdated.

    SQLite CHECK constraints are embedded in the CREATE TABLE DDL and
    cannot be altered.  This migration detects the old constraint
    (missing 'daily_at') by inspecting the table's SQL definition,
    then rebuilds the table using SQLite's recommended 12-step process.
    """
    async with engine.begin() as conn:
        # Check if the table exists and has the old constraint
        result = await conn.execute(
            sa.text(
                "SELECT sql FROM sqlite_master "
                "WHERE type='table' AND name='agent_tasks'"
            )
        )
        row = result.first()
        if row is None:
            return  # Table doesn't exist yet; create_all will handle it

        table_sql: str = row[0]
        if "daily_at" in table_sql:
            return  # Already has the new constraint

        logger.info(
            "Migrating agent_tasks table to add 'daily_at' trigger type..."
        )

        # SQLite table rebuild: rename → create new → copy → drop old
        await conn.execute(sa.text(
            "ALTER TABLE agent_tasks RENAME TO _agent_tasks_old"
        ))

        # Let SQLModel create the new table with updated constraints
        await conn.run_sync(
            lambda sync_conn: SQLModel.metadata.tables["agent_tasks"].create(
                sync_conn,
            )
        )

        # Copy all existing data (time_utc will be NULL for old rows)
        await conn.execute(sa.text("""
            INSERT INTO agent_tasks (
                id, prompt, trigger_type, run_at, interval_seconds, time_utc,
                next_run_at, max_runs, status, run_count, last_run_at,
                result_summary, error_message, conversation_id,
                created_at, updated_at
            )
            SELECT
                id, prompt, trigger_type, run_at, interval_seconds, time_utc,
                next_run_at, max_runs, status, run_count, last_run_at,
                result_summary, error_message, conversation_id,
                created_at, updated_at
            FROM _agent_tasks_old
        """))

        await conn.execute(sa.text("DROP TABLE _agent_tasks_old"))
        logger.info("agent_tasks table migrated successfully")
