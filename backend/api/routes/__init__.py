"""O.M.N.I.A. — API route registry."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.routes import chat

router = APIRouter(prefix="/api")

router.include_router(chat.router)


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness / readiness probe."""
    return {"status": "ok", "version": "0.1.0"}

