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

    # Verify a real chat model is available (not just embedding models).
    resolved_model = await ctx.llm_service._resolve_model()
    if "embed" in resolved_model.lower():
        raise RuntimeError(
            f"Cannot execute task: resolved model '{resolved_model}' is an "
            "embedding model, not a chat LLM. Load a chat model in LM Studio."
        )

    tools = await ctx.tool_registry.get_available_tools() if ctx.tool_registry else []

    # Tools that MUST NOT be available during headless task execution.
    # Blocking these structurally (not just via prompt instruction) prevents
    # the LLM from recursively spawning new tasks or cancelling unrelated ones.
    _HEADLESS_BLOCKED = frozenset({
        "agent_task_schedule_task",
        "agent_task_cancel_task",
    })
    tools = [t for t in tools if t["function"]["name"] not in _HEADLESS_BLOCKED]

    # Track tool executions for result summary when LLM gives no final text.
    executed_tools: list[str] = []

    # Collect tool names available for the prompt hint.
    tool_names = [t["function"]["name"] for t in tools]

    # Format tool list for the preamble — one per line for clarity.
    tool_list_str = "\n".join(f"  - {n}" for n in tool_names)

    logger.info(
        "Task {}: starting headless execution — {} tools available, prompt='{}'",
        task.id, len(tools), task.prompt[:120],
    )

    # Build messages with an autonomous-execution preamble so the LLM
    # knows it must ACT immediately (not schedule or describe the action).
    messages: list[dict[str, Any]] = ctx.llm_service.build_messages(
        user_content=(
            "[AUTONOMOUS TASK EXECUTION]\n"
            "You are executing a single run of a scheduled background task.\n"
            "Use the available tools as needed to complete the task.\n"
            "When finished, output a brief summary of what you did.\n\n"
            "RULES:\n"
            "2. Do NOT schedule new tasks.\n"
            "3. Do NOT ask for confirmation — act autonomously.\n\n"
            "4. Do NOT interrupt until you reached the task goal.\n\n"
            "5. Always finish the task in one single session.\n\n"
            f"AVAILABLE TOOLS:\n{tool_list_str}\n\n"
            f"TASK: {task.prompt}"
        ),
        history=None,
    )

    conversation_buf: list[dict[str, Any]] = list(messages)
    final_content = ""
    max_iterations = ctx.config.llm.max_tool_iterations

    # ── Main loop — mirrors _tool_loop.py logic ──────────────────────
    # No nudges: the LLM drives the conversation exactly as in a
    # normal chat.  When it returns tool calls → execute → re-query.
    # When it returns text only (no tool calls) → that is the final
    # answer, regardless of whether tools have been used or not.

    for iteration in range(max_iterations):
        tool_calls: list[dict[str, Any]] = []
        content_parts: list[str] = []
        thinking_parts: list[str] = []

        async for event in ctx.llm_service.chat(
            conversation_buf,
            tools=tools if tools else None,
        ):
            if event["type"] == "token":
                content_parts.append(event["content"])
            elif event["type"] == "thinking":
                thinking_parts.append(event["content"])
            elif event["type"] == "tool_call":
                tool_calls.append(event)
            elif event["type"] == "error":
                logger.error(
                    "Task {}: LLM error during iteration {}: {}",
                    task.id, iteration + 1, event.get("content", "unknown"),
                )
            elif event["type"] == "done":
                break

        final_content = "".join(content_parts)

        # No tool calls → LLM considers itself done.
        if not tool_calls:
            # Thinking-model edge case: summary composed entirely inside
            # <think> tags with zero content tokens.
            if not final_content and thinking_parts:
                final_content = "".join(thinking_parts).strip()
                logger.info(
                    "Task {}: model produced summary in thinking block "
                    "only (iteration {}) — using as final content "
                    "(length={}).",
                    task.id, iteration + 1, len(final_content),
                )
            break

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

            # Block dangerous/forbidden tools and task-management tools that
            # must never be called from a headless execution context.
            # Blocking at this level is a safety net even if the tool was
            # somehow not filtered from the initial tools list.
            RUNTIME_BLOCKED = frozenset({
                "agent_task_schedule_task",
                "agent_task_cancel_task",
            })
            if ctx.tool_registry is None:
                tool_content = "Error: no tools available"
                logger.warning(
                    "Task {}: tool_registry unavailable for '{}'",
                    task.id, name,
                )
            elif name in RUNTIME_BLOCKED:
                tool_content = (
                    f"Tool '{name}' is not permitted inside a task execution — "
                    "tasks cannot schedule or cancel other tasks."
                )
                logger.error(
                    "Task {}: BLOCKED forbidden tool call '{}' — recursive task spawn prevented.",
                    task.id, name,
                )
            elif (tool_def := ctx.tool_registry.get_tool_definition(name)) and (
                tool_def.risk_level in ("dangerous", "forbidden")
            ):
                tool_content = (
                    f"Tool '{name}' is classified as {tool_def.risk_level} — "
                    "not executable in autonomous tasks"
                )
                logger.warning(
                    "Task {}: blocked tool '{}' (risk={})",
                    task.id, name, tool_def.risk_level,
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
                    # Convert ToolResult to string — mirror _tool_loop
                    if isinstance(result.content, (dict, list)):
                        tool_content = json.dumps(result.content)
                    elif result.content is None:
                        tool_content = (
                            result.error_message or "No result"
                        )
                    else:
                        tool_content = str(result.content)

                    if result.success:
                        executed_tools.append(name)
                    logger.info(
                        "Task {}: tool '{}' {} — result length={}",
                        task.id, name,
                        "executed" if result.success else "FAILED",
                        len(tool_content),
                    )
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

        logger.info(
            "Task {}: iteration {}/{} completed ({} tool calls: {})",
            task.id, iteration + 1, max_iterations, len(tool_calls),
            ", ".join(tc["function"]["name"] for tc in tool_calls),
        )
    else:
        logger.warning(
            "Task {} hit max_iterations={}", task.id, max_iterations,
        )

    logger.info(
        "Task {}: execution finished — final_content length={}",
        task.id, len(final_content),
    )
    if final_content:
        return final_content
    if executed_tools:
        return f"Task executed {len(executed_tools)} tool(s): {', '.join(executed_tools)}"
    return "(no output)"
