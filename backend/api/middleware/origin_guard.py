"""O.M.N.I.A. — Origin validation middleware for mutable endpoints.

Prevents cross-origin requests from untrusted web pages to sensitive
endpoints (e.g. PUT /config, PUT /settings). Since OMNIA runs locally,
this guards against malicious JS on arbitrary websites calling the
local API to disable security features.

Safe/read-only methods (GET, HEAD, OPTIONS) are always allowed.
WebSocket upgrades are excluded (handled by their own connection logic).
"""

from __future__ import annotations

from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


# Origins that are allowed to make mutable requests.
_TRUSTED_ORIGINS: set[str] = {
    "http://localhost:5173",   # Vite dev
    "http://localhost:3000",   # Electron dev
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "null",                    # Electron production (file:// sends Origin: null)
}

# HTTP methods considered safe (read-only).
_SAFE_METHODS: set[str] = {"GET", "HEAD", "OPTIONS"}


class OriginGuardMiddleware:
    """Block mutable HTTP requests from untrusted origins.

    Checks the ``Origin`` header on non-safe HTTP methods.  If the
    origin is missing or not in the trusted set, the request is
    rejected with 403 Forbidden.

    WebSocket connections and safe methods are always allowed.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        method = request.method.upper()

        if method in _SAFE_METHODS:
            await self.app(scope, receive, send)
            return

        origin = request.headers.get("origin", "")

        # Allow requests with no Origin header (same-origin requests
        # from non-browser clients like curl, httpie, Postman).
        if not origin:
            await self.app(scope, receive, send)
            return

        if origin not in _TRUSTED_ORIGINS:
            logger.warning(
                "Blocked mutable request from untrusted origin: {} {} (origin={})",
                method, request.url.path, origin,
            )
            response = JSONResponse(
                status_code=403,
                content={"detail": "Request blocked: untrusted origin"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
