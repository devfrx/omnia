"""O.M.N.I.A. — REST API for autonomous task management.

Provides CRUD endpoints for :class:`AgentTask` resources.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import func, select

from backend.core.context import AppContext
from backend.db.models import AgentTask

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _utc_iso(dt: datetime | None) -> str | None:
    """Serialize a datetime to ISO 8601 with explicit UTC suffix.

    SQLite strips timezone info, so naive datetimes read back from the
    DB must be annotated as UTC before serialization.  Without this,
    JavaScript's ``new Date()`` interprets the string as local time.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class TaskCreateRequest(BaseModel):
    """Request body for creating a new task."""

    prompt: str = Field(max_length=2000)
    trigger_type: Literal["once_at", "interval", "manual"]
    run_at: datetime | None = None
    interval_seconds: int | None = Field(default=None, ge=60)
    max_runs: int | None = Field(default=None, ge=1)


class TaskResponse(BaseModel):
    """Serialized AgentTask for API responses."""

    id: str
    prompt: str
    trigger_type: str
    status: str
    run_at: str | None
    interval_seconds: int | None
    next_run_at: str | None
    max_runs: int | None
    run_count: int
    last_run_at: str | None
    result_summary: str | None
    error_message: str | None
    conversation_id: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, task: AgentTask) -> TaskResponse:
        return cls(
            id=str(task.id),
            prompt=task.prompt,
            trigger_type=task.trigger_type,
            status=task.status,
            run_at=_utc_iso(task.run_at),
            interval_seconds=task.interval_seconds,
            next_run_at=_utc_iso(task.next_run_at),
            max_runs=task.max_runs,
            run_count=task.run_count,
            last_run_at=_utc_iso(task.last_run_at),
            result_summary=task.result_summary,
            error_message=task.error_message,
            conversation_id=str(task.conversation_id) if task.conversation_id else None,
            created_at=_utc_iso(task.created_at) or '',
            updated_at=_utc_iso(task.updated_at) or '',
        )


class TaskListResponse(BaseModel):
    """Paginated task list response."""

    tasks: list[TaskResponse]
    total: int


class TaskStatsResponse(BaseModel):
    """Task count by status."""

    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _get_ctx(request: Request) -> AppContext:
    """Extract AppContext from request state."""
    return request.app.state.context


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=TaskStatsResponse)
async def get_task_stats(request: Request) -> TaskStatsResponse:
    """Get task count grouped by status."""
    ctx = _get_ctx(request)
    async with ctx.db() as session:
        result = await session.exec(
            select(AgentTask.status, func.count(AgentTask.id))
            .group_by(AgentTask.status)
        )
        counts = {row[0]: row[1] for row in result.all()}
    return TaskStatsResponse(**counts)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    request: Request,
    status: str | None = None,
    trigger_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> TaskListResponse:
    """List tasks with optional filters."""
    ctx = _get_ctx(request)
    async with ctx.db() as session:
        query = select(AgentTask).order_by(AgentTask.created_at.desc())
        count_query = select(func.count(AgentTask.id))

        if status:
            query = query.where(AgentTask.status == status)
            count_query = count_query.where(AgentTask.status == status)
        if trigger_type:
            query = query.where(AgentTask.trigger_type == trigger_type)
            count_query = count_query.where(AgentTask.trigger_type == trigger_type)

        total_result = await session.exec(count_query)
        total = total_result.one()

        query = query.offset(offset).limit(min(limit, 100))
        result = await session.exec(query)
        tasks = result.all()

    return TaskListResponse(
        tasks=[TaskResponse.from_model(t) for t in tasks],
        total=total,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(request: Request, task_id: str) -> TaskResponse:
    """Get a single task by ID."""
    ctx = _get_ctx(request)
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid task ID") from exc

    async with ctx.db() as session:
        task = await session.get(AgentTask, task_uuid)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskResponse.from_model(task)


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(request: Request, body: TaskCreateRequest) -> TaskResponse:
    """Create a new task (manual creation via REST)."""
    ctx = _get_ctx(request)
    now = datetime.now(timezone.utc)

    next_run_at: datetime | None = None
    if body.trigger_type == "once_at":
        if body.run_at is None:
            raise HTTPException(
                status_code=400,
                detail="run_at is required for once_at triggers",
            )
        next_run_at = body.run_at
    elif body.trigger_type == "interval":
        if body.interval_seconds is None:
            raise HTTPException(
                status_code=400,
                detail="interval_seconds is required for interval triggers",
            )
        next_run_at = now

    task = AgentTask(
        prompt=body.prompt,
        trigger_type=body.trigger_type,
        run_at=body.run_at if body.trigger_type == "once_at" else None,
        interval_seconds=body.interval_seconds if body.trigger_type == "interval" else None,
        next_run_at=next_run_at,
        max_runs=body.max_runs,
    )

    # Use TaskScheduler if available (emits events), fall back to direct DB
    if ctx.task_scheduler is not None:
        await ctx.task_scheduler.schedule(task)
    else:
        async with ctx.db() as session:
            session.add(task)
            await session.commit()
            await session.refresh(task)

    return TaskResponse.from_model(task)


@router.delete("/{task_id}", status_code=204)
async def delete_task(request: Request, task_id: str) -> None:
    """Cancel/delete a task."""
    ctx = _get_ctx(request)
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid task ID") from exc

    # Use TaskScheduler if available (emits TASK_CANCELLED event)
    if ctx.task_scheduler is not None:
        cancelled = await ctx.task_scheduler.cancel(task_id)
        if not cancelled:
            raise HTTPException(
                status_code=404, detail="Task not found or already completed/cancelled",
            )
        return

    async with ctx.db() as session:
        task = await session.get(AgentTask, task_uuid)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        task.status = "cancelled"
        task.updated_at = datetime.now(timezone.utc)
        await session.commit()


@router.patch("/{task_id}/run", response_model=TaskResponse)
async def trigger_manual_run(request: Request, task_id: str) -> TaskResponse:
    """Trigger immediate execution of a manual task."""
    ctx = _get_ctx(request)
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid task ID") from exc

    async with ctx.db() as session:
        task = await session.get(AgentTask, task_uuid)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Task cannot be triggered (status={task.status})",
            )
        task.next_run_at = datetime.now(timezone.utc)
        task.status = "pending"
        task.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(task)

    return TaskResponse.from_model(task)
