"""O.M.N.I.A. — Agent Task plugin.

Exposes four tools — ``schedule_task``, ``cancel_task``,
``list_tasks``, and ``get_task_result`` — for managing autonomous
background tasks via the TaskScheduler.
"""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from sqlmodel import func, select

from backend.core.plugin_base import BasePlugin
from backend.core.plugin_models import (
    ConnectionStatus,
    ExecutionContext,
    ToolDefinition,
    ToolResult,
)
from backend.db.models import AgentTask

if TYPE_CHECKING:
    from backend.core.context import AppContext


def _utc_iso(dt: datetime | None) -> str | None:
    """Serialize a datetime to ISO 8601 with explicit UTC suffix."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class AgentTaskPlugin(BasePlugin):
    """Manage autonomous background tasks via the TaskScheduler."""

    plugin_name: str = "agent_task"
    plugin_version: str = "1.0.0"
    plugin_description: str = (
        "Schedule, cancel, list and inspect autonomous background tasks. "
        "Use for recurring or deferred work the agent should do in the background."
    )
    plugin_dependencies: list[str] = []
    plugin_priority: int = 40

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self, ctx: AppContext) -> None:
        await super().initialize(ctx)
        if ctx.task_scheduler is None:
            self.logger.warning(
                "TaskScheduler is not available — task tools will return errors"
            )

    async def get_connection_status(self) -> ConnectionStatus:
        if self.ctx.task_scheduler is None:
            return ConnectionStatus.DISCONNECTED
        return ConnectionStatus.CONNECTED

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="schedule_task",
                description=(
                    "Schedule an autonomous background task. The agent will execute "
                    "the given prompt at the specified time or interval without user "
                    "interaction. Use for deferred or recurring work only.\n"
                    "TRIGGER TYPES:\n"
                    "- daily_at: repeat every day at a fixed time (most common). "
                    "Requires 'time_local' in HH:MM (user's local time, e.g. '09:03'). "
                    "The server converts to UTC automatically.\n"
                    "- once_at: execute once at a specific datetime. "
                    "Requires 'run_at' parameter.\n"
                    "- interval: repeat every N seconds starting immediately. "
                    "Requires 'interval_seconds'.\n"
                    "- manual: execute only on explicit user request.\n"
                    "NOTE: If the daily time has already passed today, the task "
                    "runs immediately for the first time, then daily at that time."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": (
                                "The SINGLE-RUN action to execute each time. "
                                "Write ONLY the direct action command — do NOT "
                                "include scheduling/timing instructions like "
                                "'every 60 seconds' (that is handled by "
                                "trigger_type). Example: 'Search the current "
                                "Bitcoin price using web_search_web_search, "
                                "then read C:\\\\file.json with "
                                "file_search_read_text_file, append the new "
                                "price entry, and write it back with "
                                "file_search_write_text_file.'"
                            ),
                            "maxLength": 2000,
                        },
                        "trigger_type": {
                            "type": "string",
                            "enum": ["once_at", "interval", "daily_at", "manual"],
                            "description": (
                                "daily_at: repeat every day at a fixed UTC time "
                                "(use for 'every day at X'). "
                                "once_at: execute once at a specific datetime. "
                                "interval: repeat every N seconds (starts immediately). "
                                "manual: execute only on explicit request."
                            ),
                        },
                        "run_at": {
                            "type": "string",
                            "description": (
                                "ISO 8601 UTC datetime. Required only if "
                                "trigger_type='once_at'. Example: "
                                "'2026-03-11T06:56:00Z'."
                            ),
                            "format": "date-time",
                        },
                        "time_local": {
                            "type": "string",
                            "description": (
                                "Time in HH:MM format in the user's LOCAL time. "
                                "Required for trigger_type='daily_at'. "
                                "Pass the user's time directly — the server "
                                "converts to UTC automatically. "
                                "Example: '09:03' for 9:03 Italian time."
                            ),
                            "pattern": "^([01]\\d|2[0-3]):[0-5]\\d$",
                        },
                        "interval_seconds": {
                            "type": "integer",
                            "description": (
                                "Repeat interval in seconds. Required only if "
                                "trigger_type='interval'. Minimum: 60."
                            ),
                            "minimum": 60,
                        },
                        "max_runs": {
                            "type": "integer",
                            "description": (
                                "Max executions for recurring tasks "
                                "(daily_at or interval). Null = unlimited."
                            ),
                            "minimum": 1,
                        },
                    },
                    "required": ["prompt", "trigger_type"],
                },
                risk_level="safe",
                requires_confirmation=False,
                result_type="json",
            ),
            ToolDefinition(
                name="cancel_task",
                description=(
                    "Cancel an active or scheduled background task by its ID."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "UUID of the task to cancel.",
                        },
                    },
                    "required": ["task_id"],
                },
                risk_level="medium",
                requires_confirmation=True,
            ),
            ToolDefinition(
                name="list_tasks",
                description=(
                    "List background tasks with optional status filter."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": [
                                "pending", "running", "completed",
                                "failed", "cancelled",
                            ],
                            "description": "Filter by task status.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results to return.",
                            "minimum": 1,
                            "maximum": 50,
                        },
                    },
                },
                risk_level="safe",
                requires_confirmation=False,
                result_type="json",
            ),
            ToolDefinition(
                name="get_task_result",
                description=(
                    "Get the result summary of a completed background task."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "UUID of the task.",
                        },
                    },
                    "required": ["task_id"],
                },
                risk_level="safe",
                requires_confirmation=False,
                result_type="json",
            ),
        ]

    async def execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        start = time.monotonic()

        handlers = {
            "schedule_task": self._schedule_task,
            "cancel_task": self._cancel_task,
            "list_tasks": self._list_tasks,
            "get_task_result": self._get_task_result,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return ToolResult.error(f"Unknown tool: {tool_name}")

        try:
            result = await handler(args, context)
            elapsed = (time.monotonic() - start) * 1000
            result.execution_time_ms = elapsed
            return result
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            self.logger.opt(exception=True).error(
                "Tool '{}' failed: {}", tool_name, exc,
            )
            return ToolResult.error(str(exc), execution_time_ms=elapsed)

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _schedule_task(
        self, args: dict[str, Any], context: ExecutionContext,
    ) -> ToolResult:
        if self.ctx.task_scheduler is None:
            return ToolResult.error(
                "Task scheduler is not active. "
                "Enable it in configuration (task_scheduler.enabled: true)."
            )

        prompt = args.get("prompt", "").strip()
        trigger_type = args.get("trigger_type", "")
        max_chars = self.ctx.config.task_scheduler.max_task_prompt_chars

        if not prompt:
            return ToolResult.error("Prompt is required.")
        if len(prompt) > max_chars:
            return ToolResult.error(
                f"Prompt too long ({len(prompt)} chars, max {max_chars})."
            )

        # Validate trigger-specific requirements
        run_at_str = args.get("run_at")
        interval_seconds = args.get("interval_seconds")
        time_local_str = args.get("time_local")
        # Legacy: also accept time_utc for backward compatibility
        time_utc_str = args.get("time_utc")
        max_runs = args.get("max_runs")
        run_at: datetime | None = None

        now = datetime.now(timezone.utc)
        next_run_at: datetime | None = None

        if trigger_type == "once_at":
            if not run_at_str:
                return ToolResult.error(
                    "run_at is required for trigger_type='once_at'."
                )
            try:
                run_at = datetime.fromisoformat(run_at_str)
                if run_at.tzinfo is None:
                    run_at = run_at.replace(tzinfo=timezone.utc)
            except ValueError:
                return ToolResult.error(
                    "Invalid run_at format. Use ISO 8601 UTC."
                )
            next_run_at = run_at

        elif trigger_type == "daily_at":
            # Accept time_local (preferred) or time_utc (legacy fallback).
            if not time_local_str and not time_utc_str:
                return ToolResult.error(
                    "time_local is required for trigger_type='daily_at'. "
                    "Format: 'HH:MM' in user's local time (e.g. '09:03')."
                )
            time_str = time_local_str or time_utc_str
            if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", time_str):
                return ToolResult.error(
                    f"Invalid time format: '{time_str}'. "
                    "Use HH:MM (24h), e.g. '09:03'."
                )
            cap = self.ctx.config.task_scheduler.max_runs_safety_cap
            if max_runs is not None and max_runs > cap:
                return ToolResult.error(
                    f"max_runs exceeds safety cap ({cap})."
                )

            hh, mm = int(time_str[:2]), int(time_str[3:5])
            user_tz = ZoneInfo("Europe/Rome")

            if time_local_str:
                # Convert local time → UTC for the next occurrence.
                now_local = datetime.now(user_tz)
                candidate_local = now_local.replace(
                    hour=hh, minute=mm, second=0, microsecond=0,
                )
                if candidate_local <= now_local:
                    # Time already passed today — run ASAP for first time.
                    next_run_at = now
                    self.logger.info(
                        "daily_at {}: time already passed today, "
                        "scheduling first run ASAP",
                        time_local_str,
                    )
                else:
                    # Convert today's local time to UTC.
                    next_run_at = candidate_local.astimezone(timezone.utc)
                # Compute the stable UTC time for storage and rescheduling.
                # Use tomorrow's date to get the correct UTC offset.
                tomorrow_local = (now_local + timedelta(days=1)).replace(
                    hour=hh, minute=mm, second=0, microsecond=0,
                )
                time_utc_str = tomorrow_local.astimezone(
                    timezone.utc,
                ).strftime("%H:%M")
            else:
                # Legacy: time_utc provided directly.
                candidate = now.replace(
                    hour=hh, minute=mm, second=0, microsecond=0,
                )
                if candidate <= now:
                    # Time already passed today — run ASAP for first time.
                    next_run_at = now
                else:
                    next_run_at = candidate

        elif trigger_type == "interval":
            if interval_seconds is None:
                return ToolResult.error(
                    "interval_seconds is required for trigger_type='interval'."
                )
            if interval_seconds < 60:
                return ToolResult.error(
                    "Minimum interval: 60 seconds."
                )
            cap = self.ctx.config.task_scheduler.max_runs_safety_cap
            if max_runs is not None and max_runs > cap:
                return ToolResult.error(
                    f"max_runs exceeds safety cap ({cap})."
                )
            next_run_at = now

        elif trigger_type == "manual":
            next_run_at = None

        else:
            return ToolResult.error(
                f"Invalid trigger_type: '{trigger_type}'. "
                "Must be 'once_at', 'daily_at', 'interval', or 'manual'."
            )

        task = AgentTask(
            prompt=prompt,
            trigger_type=trigger_type,
            run_at=run_at if trigger_type == "once_at" else None,
            interval_seconds=(
                interval_seconds if trigger_type == "interval" else None
            ),
            time_utc=time_utc_str if trigger_type == "daily_at" else None,
            time_local=time_local_str if trigger_type == "daily_at" else None,
            next_run_at=next_run_at,
            max_runs=max_runs,
            conversation_id=None,
        )

        task_id = await self.ctx.task_scheduler.schedule(task)

        return ToolResult.ok(
            {
                "task_id": task_id,
                "trigger_type": trigger_type,
                "next_run_at": _utc_iso(next_run_at),
                "message": f"Task scheduled successfully (ID: {task_id})",
            },
            content_type="application/json",
        )

    async def _cancel_task(
        self, args: dict[str, Any], context: ExecutionContext,
    ) -> ToolResult:
        if self.ctx.task_scheduler is None:
            return ToolResult.error("Task scheduler is not active.")

        task_id = args.get("task_id", "").strip()
        if not task_id:
            return ToolResult.error("task_id is required.")

        try:
            uuid.UUID(task_id)
        except ValueError:
            return ToolResult.error("Invalid task_id format.")

        cancelled = await self.ctx.task_scheduler.cancel(task_id)
        if cancelled:
            return ToolResult.ok(f"Task {task_id} cancelled successfully.")
        return ToolResult.error(
            f"Task {task_id} not found or already completed/cancelled."
        )

    async def _list_tasks(
        self, args: dict[str, Any], context: ExecutionContext,
    ) -> ToolResult:
        status_filter = args.get("status")
        limit = min(args.get("limit", 20), 50)

        async with self.ctx.db() as session:
            query = select(AgentTask).order_by(AgentTask.created_at.desc())

            if status_filter:
                query = query.where(AgentTask.status == status_filter)

            query = query.limit(limit)
            result = await session.exec(query)
            tasks = result.all()

        task_list = [
            {
                "id": str(t.id),
                "prompt": t.prompt[:100] + ("..." if len(t.prompt) > 100 else ""),
                "trigger_type": t.trigger_type,
                "status": t.status,
                "run_count": t.run_count,
                "time_utc": t.time_utc,
                "time_local": t.time_local,
                "next_run_at": _utc_iso(t.next_run_at),
                "created_at": _utc_iso(t.created_at),
            }
            for t in tasks
        ]

        return ToolResult.ok(
            {"tasks": task_list, "total": len(task_list)},
            content_type="application/json",
        )

    async def _get_task_result(
        self, args: dict[str, Any], context: ExecutionContext,
    ) -> ToolResult:
        task_id = args.get("task_id", "").strip()
        if not task_id:
            return ToolResult.error("task_id is required.")

        try:
            task_uuid = uuid.UUID(task_id)
        except ValueError:
            return ToolResult.error("Invalid task_id format.")

        async with self.ctx.db() as session:
            task = await session.get(AgentTask, task_uuid)

        if task is None:
            return ToolResult.error(f"Task {task_id} not found.")

        return ToolResult.ok(
            {
                "id": str(task.id),
                "prompt": task.prompt,
                "trigger_type": task.trigger_type,
                "status": task.status,
                "run_count": task.run_count,
                "result_summary": task.result_summary,
                "error_message": task.error_message,
                "next_run_at": _utc_iso(task.next_run_at),
                "last_run_at": _utc_iso(task.last_run_at),
                "created_at": _utc_iso(task.created_at),
            },
            content_type="application/json",
        )
