"""O.M.N.I.A. — Plugin management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.core.context import AppContext

router = APIRouter()


def _ctx(request: Request) -> AppContext:
    return request.app.state.context


@router.get("/plugins")
async def list_plugins(request: Request) -> list[dict[str, Any]]:
    """Return all available plugins and their status.

    Reads the ``plugins.enabled`` list from the config and returns
    a basic info structure for each known plugin.
    """
    ctx = _ctx(request)
    enabled_list = ctx.config.plugins.enabled

    # All known plugin directories.
    known_plugins = [
        "system_info",
        "pc_automation",
        "web_search",
        "calendar",
        "home_automation",
    ]

    results: list[dict[str, Any]] = []
    for name in known_plugins:
        results.append(
            {
                "name": name,
                "version": "0.1.0",
                "description": f"Plugin: {name}",
                "author": "",
                "enabled": name in enabled_list,
                "tools": [],
            }
        )

    return results


@router.patch("/plugins/{plugin_name}")
async def toggle_plugin(
    plugin_name: str, request: Request
) -> dict[str, Any]:
    """Enable or disable a plugin by name.

    Body: ``{"enabled": true|false}``
    """
    ctx = _ctx(request)
    body = await request.json()
    enabled: bool = body.get("enabled", True)

    known_plugins = {
        "system_info",
        "pc_automation",
        "web_search",
        "calendar",
        "home_automation",
    }
    if plugin_name not in known_plugins:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")

    current = ctx.config.plugins.enabled
    if enabled and plugin_name not in current:
        current.append(plugin_name)
    elif not enabled and plugin_name in current:
        current.remove(plugin_name)

    return {
        "name": plugin_name,
        "enabled": plugin_name in current,
    }
