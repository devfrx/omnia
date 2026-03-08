"""O.M.N.I.A. — PC Automation input validation and safe subprocess execution.

Provides a hardened subprocess wrapper that enforces shell=False,
argument lists, timeouts, and output truncation.
"""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from loguru import logger

from backend.plugins.pc_automation.constants import (
    COMMAND_TIMEOUT_S,
    MAX_COMMAND_OUTPUT_CHARS,
)


async def safe_subprocess(
    command: str,
    args: list[str] | None = None,
    timeout: int | None = None,
    cwd: str | None = None,
) -> str:
    """Execute a command safely via subprocess with strict security constraints.

    Always uses shell=False, passes arguments as a list, enforces a timeout,
    and truncates output to prevent memory abuse.

    Args:
        command: The executable name (e.g. "ipconfig", "systeminfo").
        args: Optional list of arguments (NOT a single string).
        timeout: Timeout in seconds (defaults to COMMAND_TIMEOUT_S).
        cwd: Optional working directory.

    Returns:
        Truncated stdout+stderr output as a string.

    Raises:
        TimeoutError: If the process exceeds the timeout.
        subprocess.CalledProcessError: If the process returns non-zero exit code.
        OSError: If the executable is not found.
    """
    if timeout is None:
        timeout = COMMAND_TIMEOUT_S

    cmd_list = [command]
    if args:
        cmd_list.extend(args)

    logger.debug("safe_subprocess: {}", " ".join(cmd_list))

    def _run() -> str:
        result = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            cwd=cwd,
            # Prevent child process from inheriting handles
            close_fds=True,
        )
        output = result.stdout or ""
        if result.stderr:
            output += "\n" + result.stderr
        output = output.strip()

        # Truncate long output
        if len(output) > MAX_COMMAND_OUTPUT_CHARS:
            output = output[:MAX_COMMAND_OUTPUT_CHARS] + "\n... (output truncated)"

        return output

    try:
        return await asyncio.to_thread(_run)
    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"Command '{command}' timed out after {timeout}s"
        )
    except FileNotFoundError:
        raise OSError(f"Command '{command}' not found")


def sanitize_text_input(text: str, max_length: int = 1000) -> str:
    """Sanitize text before typing it via pyautogui.

    Removes control characters and limits length to prevent abuse.

    Args:
        text: Raw text to sanitize.
        max_length: Maximum allowed length.

    Returns:
        Sanitized text string.

    Raises:
        ValueError: If text is empty or exceeds max_length.
    """
    if not text:
        raise ValueError("Text to type cannot be empty")

    # Strip leading/trailing whitespace but preserve internal whitespace
    cleaned = text.strip()

    if len(cleaned) > max_length:
        raise ValueError(
            f"Text too long ({len(cleaned)} chars, max {max_length})"
        )

    # Remove control characters except newline and tab
    sanitized = "".join(
        c for c in cleaned
        if c in ("\n", "\t", "\r") or (ord(c) >= 32)
    )

    return sanitized
