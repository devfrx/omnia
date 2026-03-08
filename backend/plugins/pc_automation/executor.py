"""O.M.N.I.A. — PC Automation async execution wrappers.

Each function wraps a blocking Windows automation call in
``asyncio.to_thread()`` for async safety. All validation is
performed before execution via the security module.
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

from loguru import logger

from backend.plugins.pc_automation.constants import (
    CMD_BUILTINS,
    MAX_SCREENSHOT_PIXELS,
)
from backend.plugins.pc_automation.security import (
    ScreenshotLockout,
    validate_app_name,
    validate_command,
    validate_keys,
)
from backend.plugins.pc_automation.validators import (
    safe_subprocess,
    sanitize_text_input,
)

# -- Lazy imports for optional dependencies --------------------------------

try:
    import pyautogui
    pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    pyautogui.PAUSE = 0.1  # Small delay between actions
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    pyautogui = None  # type: ignore[assignment]
    _PYAUTOGUI_AVAILABLE = False

try:
    import pyperclip
    _PYPERCLIP_AVAILABLE = True
except ImportError:
    pyperclip = None  # type: ignore[assignment]
    _PYPERCLIP_AVAILABLE = False

try:
    import pywinauto
    _PYWINAUTO_AVAILABLE = True
except ImportError:
    pywinauto = None  # type: ignore[assignment]
    _PYWINAUTO_AVAILABLE = False

# Shared lockout instance (one per plugin lifecycle)
_lockout = ScreenshotLockout()


def get_lockout() -> ScreenshotLockout:
    """Return the shared screenshot lockout instance."""
    return _lockout


def check_dependencies() -> list[str]:
    """Return list of missing optional dependencies."""
    missing: list[str] = []
    if not _PYAUTOGUI_AVAILABLE:
        missing.append("pyautogui")
    if not _PYWINAUTO_AVAILABLE:
        missing.append("pywinauto")
    return missing


async def exec_open_app(app_name: str) -> str:
    """Open an application by name (must be in whitelist).

    Validates against ALLOWED_APPS whitelist, then uses subprocess to start.
    """
    valid, msg, executable = validate_app_name(app_name)
    if not valid:
        raise ValueError(msg)

    if _lockout.is_locked("open_application"):
        remaining = _lockout.get_remaining_s()
        raise RuntimeError(
            f"open_application is locked for {remaining:.0f}s "
            "due to recent screenshot (anti-exfiltration protection)"
        )

    def _open() -> str:
        import subprocess

        subprocess.Popen(
            [executable],
            shell=False,
            close_fds=True,
        )
        return f"Application '{app_name}' opened ({executable})"

    return await asyncio.to_thread(_open)


async def exec_close_app(app_name: str) -> str:
    """Close an application by name.

    Uses taskkill to terminate the process gracefully.
    """
    valid, msg, executable = validate_app_name(app_name)
    if not valid:
        raise ValueError(msg)

    try:
        output = await safe_subprocess("taskkill", ["/IM", executable, "/F"], timeout=10)
        return f"Closed '{app_name}': {output}"
    except Exception as e:
        raise RuntimeError(f"Failed to close '{app_name}': {e}")


async def exec_type_text(text: str) -> str:
    """Type text via clipboard paste (Ctrl+V).

    Uses clipboard instead of ``pyautogui.write()`` because:
    - ``write()`` drops non-ASCII / accented characters on Windows
    - ``write()`` types character-by-character (~0.02 s each) causing
      timeouts on long strings
    - On timeout the thread keeps typing uncontrollably

    Clipboard paste is instant, Unicode-safe and cancellation-safe.
    The original clipboard content is saved and restored afterward.
    """
    sanitized = sanitize_text_input(text)

    if _lockout.is_locked("type_text"):
        remaining = _lockout.get_remaining_s()
        raise RuntimeError(
            f"type_text is locked for {remaining:.0f}s "
            "due to recent screenshot (anti-exfiltration protection)"
        )

    if not _PYAUTOGUI_AVAILABLE:
        raise RuntimeError("pyautogui is not installed")

    def _type() -> str:
        import time as _time

        # Save current clipboard text (best-effort)
        try:
            old_clip = pyperclip.paste()
        except Exception:
            old_clip = None

        try:
            pyperclip.copy(sanitized)
            pyautogui.hotkey("ctrl", "v")
            # Small pause to let the target app process the paste
            _time.sleep(0.15)
        finally:
            # Restore previous clipboard content
            if old_clip is not None:
                try:
                    pyperclip.copy(old_clip)
                except Exception:
                    pass

        return f"Typed {len(sanitized)} characters"

    return await asyncio.to_thread(_type)


async def exec_press_keys(keys: list[str]) -> str:
    """Press a key combination using pyautogui."""
    valid, msg = validate_keys(keys)
    if not valid:
        raise ValueError(msg)

    if _lockout.is_locked("press_keys"):
        remaining = _lockout.get_remaining_s()
        raise RuntimeError(
            f"press_keys is locked for {remaining:.0f}s "
            "due to recent screenshot (anti-exfiltration protection)"
        )

    if not _PYAUTOGUI_AVAILABLE:
        raise RuntimeError("pyautogui is not installed")

    def _press() -> str:
        if len(keys) == 1:
            pyautogui.press(keys[0])
        else:
            pyautogui.hotkey(*keys)
        return f"Pressed keys: {' + '.join(keys)}"

    return await asyncio.to_thread(_press)


async def exec_take_screenshot() -> bytes:
    """Take a screenshot, downscale if > 2MP, return PNG bytes.

    Records the screenshot in the lockout manager to block
    dangerous tools for SCREENSHOT_LOCKOUT_S seconds.
    """
    if not _PYAUTOGUI_AVAILABLE:
        raise RuntimeError("pyautogui is not installed")

    def _screenshot() -> bytes:
        img = pyautogui.screenshot()
        # Record lockout IMMEDIATELY after capture (before any processing)
        # to prevent TOCTOU race with concurrent tool calls.
        _lockout.record_screenshot()

        # Downscale if > MAX_SCREENSHOT_PIXELS
        w, h = img.size
        pixels = w * h
        if pixels > MAX_SCREENSHOT_PIXELS:
            scale = (MAX_SCREENSHOT_PIXELS / pixels) ** 0.5
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = img.resize((new_w, new_h))
            logger.info(
                "Screenshot downscaled: {}x{} -> {}x{}",
                w, h, new_w, new_h,
            )

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    return await asyncio.to_thread(_screenshot)


async def exec_get_active_window() -> str:
    """Get the title of the currently active window."""
    if not _PYAUTOGUI_AVAILABLE:
        raise RuntimeError("pyautogui is not installed")

    def _get_window() -> str:
        try:
            win = pyautogui.getActiveWindow()
            if win:
                return win.title or "(no title)"
            return "(no active window)"
        except Exception:
            return "(could not detect active window)"

    return await asyncio.to_thread(_get_window)


async def exec_get_running_apps() -> list[dict[str, str]]:
    """Get list of running applications with visible windows.

    Uses PowerShell ``Get-Process`` which is significantly faster than
    ``tasklist /V`` because it reads window titles from the process handle
    directly rather than querying WMI for every process.

    Returns only processes whose window title is non-empty,
    deduplicated by name, limited to 50 entries.
    """
    ps_cmd = (
        "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} "
        "| Select-Object -First 50 Name,Id,MainWindowTitle "
        "| ForEach-Object { $_.Name + '|' + $_.Id + '|' + $_.MainWindowTitle }"
    )
    output = await safe_subprocess(
        "powershell",
        ["-NoProfile", "-NoLogo", "-Command", ps_cmd],
        timeout=10,
    )

    apps: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for line in output.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        name = parts[0].strip()
        pid = parts[1].strip()
        window_title = parts[2].strip()
        if not name or not window_title:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        apps.append({"name": name, "pid": pid, "window_title": window_title})

    return apps


async def exec_command(command: str) -> str:
    """Execute a whitelisted command safely.

    Checks the screenshot lockout before execution.
    """
    if _lockout.is_locked("execute_command"):
        remaining = _lockout.get_remaining_s()
        raise RuntimeError(
            f"Command execution is locked for {remaining:.0f}s "
            "due to recent screenshot (anti-exfiltration protection)"
        )

    valid, msg = validate_command(command)
    if not valid:
        raise ValueError(msg)

    base_cmd = command.strip().split()[0].lower()
    if base_cmd.endswith(".exe"):
        base_cmd = base_cmd[:-4]

    if base_cmd in CMD_BUILTINS:
        # CMD built-in commands must run through cmd.exe /c.
        # Split into individual tokens so cmd.exe cannot re-interpret
        # shell operators embedded in a single string argument.
        parts = command.strip().split()
        return await safe_subprocess("cmd.exe", ["/c"] + parts)

    # External executables: split into command + args
    parts = command.strip().split()
    cmd = parts[0]
    args = parts[1:] if len(parts) > 1 else []
    return await safe_subprocess(cmd, args)


async def exec_move_mouse(x: int, y: int) -> str:
    """Move mouse cursor to absolute position."""
    if _lockout.is_locked("move_mouse"):
        remaining = _lockout.get_remaining_s()
        raise RuntimeError(
            f"move_mouse is locked for {remaining:.0f}s "
            "due to recent screenshot (anti-exfiltration protection)"
        )

    if not _PYAUTOGUI_AVAILABLE:
        raise RuntimeError("pyautogui is not installed")

    def _move() -> str:
        screen_w, screen_h = pyautogui.size()
        if not (0 <= x <= screen_w and 0 <= y <= screen_h):
            raise ValueError(
                f"Coordinates ({x}, {y}) out of screen bounds "
                f"({screen_w}x{screen_h})"
            )
        pyautogui.moveTo(x, y, duration=0.3)
        return f"Mouse moved to ({x}, {y})"

    return await asyncio.to_thread(_move)


async def exec_click(x: int, y: int, button: str = "left") -> str:
    """Click at absolute screen position."""
    if button not in ("left", "right", "middle"):
        raise ValueError(f"Invalid button '{button}', must be left/right/middle")

    if _lockout.is_locked("click"):
        remaining = _lockout.get_remaining_s()
        raise RuntimeError(
            f"click is locked for {remaining:.0f}s "
            "due to recent screenshot (anti-exfiltration protection)"
        )

    if not _PYAUTOGUI_AVAILABLE:
        raise RuntimeError("pyautogui is not installed")

    def _click() -> str:
        screen_w, screen_h = pyautogui.size()
        if not (0 <= x <= screen_w and 0 <= y <= screen_h):
            raise ValueError(
                f"Coordinates ({x}, {y}) out of screen bounds "
                f"({screen_w}x{screen_h})"
            )
        pyautogui.click(x, y, button=button)
        return f"Clicked {button} at ({x}, {y})"

    return await asyncio.to_thread(_click)
