"""O.M.N.I.A. — LLM service for OpenAI-compatible APIs."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from backend.core.config import LLMConfig


class LLMService:
    """Communicate with any OpenAI-compatible API (LM Studio, Ollama, etc.).

    Args:
        config: The ``LLMConfig`` holding provider URL, model name, etc.
    """

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(timeout=120.0)
        self._system_prompt: str | None = None

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    def _load_system_prompt(self) -> str:
        """Read the system prompt from the configured file path.

        Returns:
            The system prompt text.

        Raises:
            FileNotFoundError: If the configured system prompt file is missing.
        """
        if self._system_prompt is not None:
            return self._system_prompt

        path = Path(self._config.system_prompt_file)
        if not path.exists():
            raise FileNotFoundError(
                f"System prompt file not found: {path}"
            )

        self._system_prompt = path.read_text(encoding="utf-8").strip()
        logger.debug("Loaded system prompt from {}", path)
        return self._system_prompt

    # ------------------------------------------------------------------
    # Message building
    # ------------------------------------------------------------------

    def build_messages(
        self,
        user_content: str,
        history: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Build a full message list with system prompt, history, and user msg.

        Args:
            user_content: The new user message text.
            history: Optional prior messages to include.

        Returns:
            A list of message dicts ready for the chat completions API.
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._load_system_prompt()},
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_content})
        return messages

    # ------------------------------------------------------------------
    # Streaming chat
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream a chat completion via SSE.

        Sends a POST to ``{base_url}/v1/chat/completions`` with
        ``stream=True`` and yields parsed event dicts.

        Yields:
            Dicts with a ``type`` key:
            - ``{"type": "token", "content": "..."}``
            - ``{"type": "tool_call", "id": "...", "function": {...}}``
            - ``{"type": "done"}``
        """
        url = f"{self._config.base_url}/v1/chat/completions"

        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        # Accumulator for tool calls that arrive across multiple chunks.
        # Keyed by index (int) → {"id": str, "name": str, "arguments": str}
        tool_calls_acc: dict[int, dict[str, str]] = {}

        async with self._client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()

            async for raw_line in resp.aiter_lines():
                line = raw_line.strip()
                if not line or not line.startswith("data: "):
                    continue

                data_str = line[len("data: "):]

                if data_str == "[DONE]":
                    # Flush any accumulated tool calls before finishing.
                    for _idx in sorted(tool_calls_acc):
                        tc = tool_calls_acc[_idx]
                        yield {
                            "type": "tool_call",
                            "id": tc["id"],
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["arguments"],
                            },
                        }
                    yield {"type": "done"}
                    return

                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed SSE chunk: {}", data_str)
                    continue

                choices = chunk.get("choices")
                if not choices:
                    continue

                delta = choices[0].get("delta", {})

                # --- content token ---
                content = delta.get("content")
                if content:
                    yield {"type": "token", "content": content}

                # --- tool calls (streamed in pieces) ---
                for tc_delta in delta.get("tool_calls", []):
                    idx: int = tc_delta.get("index", 0)

                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {
                            "id": "",
                            "name": "",
                            "arguments": "",
                        }

                    if tc_delta.get("id"):
                        tool_calls_acc[idx]["id"] = tc_delta["id"]

                    func = tc_delta.get("function", {})
                    if func.get("name"):
                        tool_calls_acc[idx]["name"] = func["name"]
                    if func.get("arguments"):
                        tool_calls_acc[idx]["arguments"] += func["arguments"]

        # If stream ended without [DONE], flush anyway.
        for _idx in sorted(tool_calls_acc):
            tc = tool_calls_acc[_idx]
            yield {
                "type": "tool_call",
                "id": tc["id"],
                "function": {
                    "name": tc["name"],
                    "arguments": tc["arguments"],
                },
            }
        yield {"type": "done"}

    # ------------------------------------------------------------------
    # Non-streaming chat
    # ------------------------------------------------------------------

    async def chat_sync(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a non-streaming chat completion request.

        Args:
            messages: The full list of messages.
            tools: Optional tool definitions.

        Returns:
            The raw JSON response dict from the API.
        """
        url = f"{self._config.base_url}/v1/chat/completions"

        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
        logger.debug("LLMService httpx client closed")
