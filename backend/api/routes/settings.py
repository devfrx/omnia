"""O.M.N.I.A. — Settings endpoints (runtime toggles)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.core.context import AppContext

router = APIRouter(prefix="/settings", tags=["settings"])


def _ctx(request: Request) -> AppContext:
    return request.app.state.context


class ToolConfirmationsRequest(BaseModel):
    """Body for the tool-confirmations toggle."""

    enabled: bool


class ToolConfirmationsResponse(BaseModel):
    """Response after updating tool confirmations."""

    confirmations_enabled: bool


@router.put("/tool-confirmations")
async def set_tool_confirmations(
    body: ToolConfirmationsRequest,
    request: Request,
) -> ToolConfirmationsResponse:
    """Toggle tool confirmations at runtime.

    Updates ``ctx.config.pc_automation.confirmations_enabled`` so that
    the frontend can sync its toggle with the backend state.
    """
    ctx = _ctx(request)
    ctx.config.pc_automation.confirmations_enabled = body.enabled
    return ToolConfirmationsResponse(
        confirmations_enabled=ctx.config.pc_automation.confirmations_enabled,
    )


@router.get("/tool-confirmations")
async def get_tool_confirmations(
    request: Request,
) -> ToolConfirmationsResponse:
    """Read the current tool confirmations state."""
    ctx = _ctx(request)
    return ToolConfirmationsResponse(
        confirmations_enabled=ctx.config.pc_automation.confirmations_enabled,
    )
