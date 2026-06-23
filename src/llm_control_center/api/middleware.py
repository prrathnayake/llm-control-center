from __future__ import annotations

import asyncio
import secrets
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to every response."""

    async def dispatch(
        self, request: Request, call_next: Callable[..., Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response


_DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})


class DocsProtectionMiddleware(BaseHTTPMiddleware):
    """Protect /docs, /redoc, /openapi.json behind X-Admin-Token."""

    def __init__(self, app, *, admin_token: str) -> None:  # type: ignore[override]
        super().__init__(app)
        self.admin_token = admin_token

    async def dispatch(
        self, request: Request, call_next: Callable[..., Awaitable[Response]]
    ) -> Response:
        if request.url.path in _DOCS_PATHS:
            token = request.headers.get("X-Admin-Token", "")
            if not (token and secrets.compare_digest(token, self.admin_token)):
                return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiting middleware with per-route configurable limits.

    Adds standard rate-limit headers: X-RateLimit-Limit, X-RateLimit-Remaining,
    X-RateLimit-Reset.

    Set any limit to 0 to disable rate limiting for that group (useful in tests).
    """

    def __init__(
        self,
        app,
        *,
        admin_limit: int = 60,
        chat_limit: int = 30,
        models_limit: int = 120,
        window_seconds: int = 60,
        max_request_size_bytes: int = 1_048_576,
    ) -> None:
        super().__init__(app)
        self.admin_limit = admin_limit
        self.chat_limit = chat_limit
        self.models_limit = models_limit
        self.window_seconds = window_seconds
        self.max_request_size_bytes = max_request_size_bytes
        self._store: dict[str, deque[float]] = defaultdict(deque)
        self._cleanup_task: asyncio.Task | None = None

    def _get_limit(self, request: Request) -> int:
        path = request.url.path
        if path.startswith("/admin"):
            return self.admin_limit
        if path.startswith("/v1/chat/completions"):
            return self.chat_limit
        if path.startswith("/v1/models") or path == "/health":
            return self.models_limit
        return max(self.admin_limit, self.chat_limit, self.models_limit)

    def _get_key(self, request: Request) -> str:
        path = request.url.path
        if path.startswith("/v1/chat/completions"):
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                return f"chat:{auth.removeprefix('Bearer ').strip()[:32]}"
        client_ip = request.client.host if request.client else "unknown"
        return f"{path.split('/')[1] if '/' in path else 'default'}:{client_ip}"

    def _cleanup_old_entries(self) -> None:
        now = time.time()
        cutoff = now - self.window_seconds
        empty_keys = [k for k, v in self._store.items() if not v or v[-1] < cutoff]
        for k in empty_keys:
            del self._store[k]

    async def _start_cleanup(self) -> None:
        while True:
            await asyncio.sleep(300)
            self._cleanup_old_entries()

    def _add_rate_headers(
        self, response: Response, limit: int, remaining: int, reset: float
    ) -> None:
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        response.headers["X-RateLimit-Reset"] = str(int(reset))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.get_event_loop().create_task(self._start_cleanup())

        limit = self._get_limit(request)

        if limit == 0:
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_request_size_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request body too large (max {self.max_request_size_bytes} bytes)"
                },
            )

        key = self._get_key(request)
        now = time.time()
        window_start = now - self.window_seconds
        entries = self._store[key]

        while entries and entries[0] < window_start:
            entries.popleft()

        if len(entries) >= limit:
            reset_time = entries[0] + self.window_seconds
            retry_after = int(reset_time - now) + 1
            response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(retry_after)},
            )
            self._add_rate_headers(response, limit, 0, reset_time)
            return response

        entries.append(now)
        remaining = limit - len(entries)
        reset_time = now + self.window_seconds

        response = await call_next(request)
        self._add_rate_headers(response, limit, remaining, reset_time)
        return response
