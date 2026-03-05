"""O.M.N.I.A. — API route registry."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.routes import chat, config, plugins

router = APIRouter(prefix="/api")

router.include_router(chat.router)
router.include_router(config.router)
router.include_router(plugins.router)


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness / readiness probe."""
    return {"status": "ok", "version": "0.1.0"}

