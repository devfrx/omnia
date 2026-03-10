"""O.M.N.I.A. — Headless agent task runner.

Executes a single :class:`AgentTask` autonomously without a WebSocket
connection. The LLM + tool loop runs until the model produces a final
text response or hits the iteration limit.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from backend.core.context import AppContext
    from backend.db.models import AgentTask

from backend.core.plugin_models import ExecutionContext


async def run_agent_task(ctx: AppContext, task: AgentTask) -> str:
    """Execute an agent task headlessly and return a result summary.

    Runs a full LLM + tool loop without a WebSocket. Results are
    returned as a natural-language summary string.

    Args:
        ctx: Application context with llm_service and tool_registry.
        task: The AgentTask to execute.

    Returns:
        Natural language summary of what the agent accomplished.

    Raises:
        RuntimeError: If LLM service is unavailable.
        asyncio.TimeoutError: Propagated from caller (TaskScheduler).
        asyncio.CancelledError: Propagated — never swallowed.
    """
    if ctx.llm_service is None:
        raise RuntimeError("LLM service not available")

    tools = await ctx.tool_registry.get_available_tools() if ctx.tool_registry else []

    messages: list[dict[str, Any]] = ctx.llm_service.build_messages(
        user_content=task.prompt,
        history=None,
    )

    conversation_buf: list[dict[str, Any]] = list(messages)
    final_content = ""
    max_iterations = ctx.config.llm.max_tool_iterations

    for iteration in range(max_iterations):
        tool_calls: list[dict[str, Any]] = []
        content_parts: list[str] = []

        async for event in ctx.llm_service.chat(
            conversation_buf,
            tools=tools if tools else None,
        ):
            if event["type"] == "token":
                content_parts.append(event["content"])
            elif event["type"] == "tool_call":
                tool_calls.append(event)
            elif event["type"] == "done":
                break

        final_content = "".join(content_parts)

        if not tool_calls:
            break  # LLM did not request tools → final answer

        # Normalize tool call IDs (same as _tool_loop.py)
        for tc in tool_calls:
            if not tc.get("id"):
                tc["id"] = f"call_{uuid.uuid4().hex[:24]}"

        # Append assistant message with tool_calls
        conversation_buf.append({
            "role": "assistant",
            "content": final_content,
            "tool_calls": [
                {"id": tc["id"], "type": "function", "function": tc["function"]}
                for tc in tool_calls
            ],
        })

        # Execute all tool calls
        for tc in tool_calls:
            tc_id = tc["id"]
            fn_data = tc["function"]
            name = fn_data["name"]
            raw_args = fn_data.get("arguments", "{}")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError as exc:
                tool_content = f"Error: invalid tool arguments: {exc}"
                conversation_buf.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": tool_content,
                })
                logger.warning(
                    "Task {}: bad JSON args for '{}': {}",
                    task.id, name, exc,
                )
                continue

            # Block dangerous/confirmation-required tools in headless mode
            if ctx.tool_registry is None:
                tool_content = "Error: no tools available"
                logger.warning(
                    "Task {}: tool_registry unavailable for '{}'",
                    task.id, name,
                )
            elif (tool_def := ctx.tool_registry.get_tool_definition(name)) and (
                tool_def.requires_confirmation
                or tool_def.risk_level in ("dangerous", "forbidden")
            ):
                tool_content = (
                    f"Tool '{name}' requires user confirmation — "
                    "not executable in autonomous tasks"
                )
                logger.warning(
                    "Task {}: blocked tool '{}' (risk={}, confirm={})",
                    task.id, name,
                    tool_def.risk_level, tool_def.requires_confirmation,
                )
            else:
                execution_ctx = ExecutionContext(
                    session_id=f"task-{task.id}",
                    conversation_id=str(task.id),
                    execution_id=str(uuid.uuid4()),
                )
                try:
                    result = await ctx.tool_registry.execute_tool(
                        name, args, execution_ctx,
                    )
                    if isinstance(result.content, str):
                        tool_content = result.content
                    else:
                        tool_content = json.dumps(result.content)
                except Exception as exc:
                    tool_content = f"Error: {exc}"
                    logger.warning(
                        "Task {}: tool '{}' failed: {}",
                        task.id, name, exc,
                    )

            conversation_buf.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": tool_content,
            })

        logger.debug(
            "Task {}: iteration {}/{} completed ({} tool calls)",
            task.id, iteration + 1, max_iterations, len(tool_calls),
        )
    else:
        logger.warning(
            "Task {} hit max_iterations={}", task.id, max_iterations,
        )

    return final_content or "(no output)"
