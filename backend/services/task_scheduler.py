"""O.M.N.I.A. — Background task scheduler.

Periodically checks the database for due :class:`AgentTask` entries
and dispatches them for headless execution via :func:`run_agent_task`.

Pattern is identical to :class:`VRAMMonitor`: ``start()``/``stop()``
with an internal ``asyncio.Task`` running ``_scheduler_loop()``.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from loguru import logger
from sqlmodel import select

if TYPE_CHECKING:
    from backend.core.context import AppContext

from backend.core.config import TaskSchedulerConfig
from backend.core.event_bus import OmniaEvent
from backend.db.models import AgentTask
from backend.services.task_runner import run_agent_task


def _next_daily_at(time_utc: str, time_local: str | None = None) -> datetime:
    """Compute the next UTC datetime for a daily task.

    When *time_local* is provided (preferred), uses DST-aware conversion
    so the task always fires at the user's local clock time regardless of
    DST changes.  Falls back to a fixed-UTC calculation otherwise.

    Args:
        time_utc: Time string in "HH:MM" format (UTC).
        time_local: Optional time string in "HH:MM" (user's local time).

    Returns:
        Timezone-aware UTC datetime of the next occurrence.
    """
    if time_local:
        user_tz = ZoneInfo("Europe/Rome")
        hh, mm = int(time_local[:2]), int(time_local[3:5])
        now_local = datetime.now(user_tz)
        candidate_local = now_local.replace(
            hour=hh, minute=mm, second=0, microsecond=0,
        )
        if candidate_local <= now_local:
            candidate_local += timedelta(days=1)
        return candidate_local.astimezone(timezone.utc)

    # Fallback: fixed UTC time.
    hh, mm = int(time_utc[:2]), int(time_utc[3:5])
    now = datetime.now(timezone.utc)
    candidate = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


class TaskScheduler:
    """Background service that polls for due tasks and executes them.

    Attributes:
        _config: Scheduler configuration.
        _ctx: Application context (set lazily in :meth:`start`).
        _poll_task: The background asyncio task running the scheduler loop.
        _semaphore: Limits concurrent task execution.
        _queued_ids: Guard set preventing double-dispatch between ticks.
    """

    def __init__(self, config: TaskSchedulerConfig) -> None:
        self._config = config
        self._ctx: AppContext | None = None
        self._poll_task: asyncio.Task[None] | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._queued_ids: set[uuid.UUID] = set()

    async def start(self, ctx: AppContext) -> None:
        """Start the scheduler background loop.

        Args:
            ctx: The shared application context.
        """
        self._ctx = ctx
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent_tasks)
        self._poll_task = asyncio.create_task(
            self._scheduler_loop(), name="task-scheduler",
        )
        logger.info(
            "TaskScheduler started (poll={}s, max_concurrent={})",
            self._config.poll_interval_s, self._config.max_concurrent_tasks,
        )

    async def stop(self) -> None:
        """Stop the scheduler and cancel the background loop."""
        if self._poll_task is not None:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None
        logger.info("TaskScheduler stopped")

    async def schedule(self, task: AgentTask) -> str:
        """Persist a new task in the DB and return its ID.

        Args:
            task: The AgentTask to schedule.

        Returns:
            The task ID as a string.
        """
        assert self._ctx is not None  # noqa: S101
        async with self._ctx.db() as session:
            session.add(task)
            await session.commit()
            await session.refresh(task)

        await self._ctx.event_bus.emit(
            OmniaEvent.TASK_SCHEDULED,
            task_id=str(task.id),
            trigger_type=task.trigger_type,
            next_run_at=(
                task.next_run_at.replace(tzinfo=timezone.utc).isoformat()
                if task.next_run_at and task.next_run_at.tzinfo is None
                else (task.next_run_at.isoformat() if task.next_run_at else None)
            ),
        )
        return str(task.id)

    async def cancel(self, task_id: str) -> bool:
        """Cancel a scheduled task.

        Args:
            task_id: The UUID string of the task to cancel.

        Returns:
            True if the task was found and cancelled.
        """
        assert self._ctx is not None  # noqa: S101
        task_uuid = uuid.UUID(task_id)
        async with self._ctx.db() as session:
            task = await session.get(AgentTask, task_uuid)
            if task is None or task.status in ("completed", "cancelled"):
                return False
            task.status = "cancelled"
            task.updated_at = datetime.now(timezone.utc)
            await session.commit()

        await self._ctx.event_bus.emit(
            OmniaEvent.TASK_CANCELLED, task_id=task_id,
        )
        return True

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _scheduler_loop(self) -> None:
        """Check for due tasks and execute them, forever."""
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.opt(exception=True).error("TaskScheduler tick error")
            await asyncio.sleep(self._config.poll_interval_s)

    async def _tick(self) -> None:
        """Find all pending tasks due and dispatch them.

        SQLite stores datetimes as naive strings. The comparison
        ``next_run_at <= now`` works because both sides are UTC —
        but we use a naive ``now`` to match the DB representation.
        """
        assert self._ctx is not None  # noqa: S101
        # Use naive UTC so the SQL comparison matches SQLite's storage.
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        async with self._ctx.db() as session:
            result = await session.exec(
                select(AgentTask)
                .where(AgentTask.status == "pending")
                .where(AgentTask.next_run_at <= now)
                .order_by(AgentTask.next_run_at)
                .limit(self._config.max_concurrent_tasks * 2)
            )
            due_tasks = result.all()

        for task in due_tasks:
            if task.id in self._queued_ids:
                continue
            self._queued_ids.add(task.id)
            asyncio.create_task(
                self._execute_task(task),
                name=f"agent-task-{task.id}",
            )

    async def _execute_task(self, task: AgentTask) -> None:
        """Execute a single task with semaphore and timeout."""
        assert self._ctx is not None  # noqa: S101
        assert self._semaphore is not None  # noqa: S101

        async with self._semaphore:
            await self._update_status(task.id, "running")

            await self._ctx.event_bus.emit(
                OmniaEvent.TASK_STARTED,
                task_id=str(task.id),
                started_at=datetime.now(timezone.utc).isoformat(),
            )

            _final_status = "failed"
            _result_summary = ""
            _error_message = ""
            try:
                summary = await asyncio.wait_for(
                    run_agent_task(self._ctx, task),
                    timeout=self._config.task_timeout_s,
                )
                _final_status = "completed"
                _result_summary = summary
                await self._mark_done(
                    task, success=True, summary=summary,
                )
            except asyncio.TimeoutError:
                _error_message = f"Task timed out after {self._config.task_timeout_s}s"
                await self._mark_done(
                    task, success=False, error=_error_message,
                )
            except asyncio.CancelledError:
                _final_status = "cancelled"
                _error_message = "Task cancelled"
                await self._mark_done(
                    task, success=False, error=_error_message,
                )
                raise
            except Exception as exc:
                _error_message = str(exc)
                await self._mark_done(
                    task, success=False, error=_error_message,
                )
            finally:
                self._queued_ids.discard(task.id)
                _event_map = {
                    "completed": OmniaEvent.TASK_COMPLETED,
                    "failed": OmniaEvent.TASK_FAILED,
                    "cancelled": OmniaEvent.TASK_CANCELLED,
                }
                await self._ctx.event_bus.emit(
                    _event_map.get(_final_status, OmniaEvent.TASK_COMPLETED),
                    task_id=str(task.id),
                    status=_final_status,
                    result_summary=_result_summary or None,
                    error_message=_error_message or None,
                )

    async def _update_status(
        self, task_id: uuid.UUID, status: str,
    ) -> None:
        """Update a task's status in the DB."""
        assert self._ctx is not None  # noqa: S101
        async with self._ctx.db() as session:
            task = await session.get(AgentTask, task_id)
            if task:
                task.status = status
                task.updated_at = datetime.now(timezone.utc)
                await session.commit()

    async def _mark_done(
        self,
        task: AgentTask,
        *,
        success: bool,
        summary: str = "",
        error: str = "",
    ) -> None:
        """Update task in DB after execution and reschedule intervals."""
        assert self._ctx is not None  # noqa: S101
        async with self._ctx.db() as session:
            db_task = await session.get(AgentTask, task.id)
            if db_task is None or db_task.status == "cancelled":
                return

            db_task.status = "completed" if success else "failed"
            db_task.result_summary = summary if success else None
            db_task.error_message = error if not success else None
            db_task.last_run_at = datetime.now(timezone.utc)
            db_task.run_count += 1
            db_task.updated_at = datetime.now(timezone.utc)

            # Reschedule recurring tasks (regardless of success/failure).
            reschedule = False

            if (
                db_task.trigger_type == "interval"
                and db_task.interval_seconds is not None
            ):
                cap = self._config.max_runs_safety_cap
                if db_task.max_runs is None or db_task.run_count < db_task.max_runs:
                    if db_task.run_count < cap:
                        reschedule = True
                        # Anchor to previous next_run_at to avoid drift.
                        anchor = db_task.next_run_at or datetime.now(timezone.utc)
                        if anchor.tzinfo is None:
                            anchor = anchor.replace(tzinfo=timezone.utc)
                        db_task.next_run_at = (
                            anchor
                            + timedelta(seconds=db_task.interval_seconds)
                        )

            elif (
                db_task.trigger_type == "daily_at"
                and db_task.time_utc is not None
            ):
                cap = self._config.max_runs_safety_cap
                if db_task.max_runs is None or db_task.run_count < db_task.max_runs:
                    if db_task.run_count < cap:
                        reschedule = True
                        db_task.next_run_at = _next_daily_at(
                            db_task.time_utc,
                            time_local=db_task.time_local,
                        )

            if reschedule:
                db_task.status = "pending"
                logger.info(
                    "Task {} rescheduled — next_run_at={}",
                    db_task.id, db_task.next_run_at,
                )

            await session.commit()
