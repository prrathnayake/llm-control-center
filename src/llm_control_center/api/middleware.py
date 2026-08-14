from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from llm_control_center.middleware import _get_client_ip as _client_ip


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
        trust_proxy_headers: bool = False,
    ) -> None:
        super().__init__(app)
        self.admin_limit = admin_limit
        self.chat_limit = chat_limit
        self.models_limit = models_limit
        self.window_seconds = window_seconds
        self.max_request_size_bytes = max_request_size_bytes
        self.trust_proxy_headers = trust_proxy_headers
        self._store: dict[str, deque[float]] = defaultdict(deque)
        self._last_cleanup = 0.0

    def _get_limit(self, request: Request) -> int:
        path = request.url.path
        if path.startswith("/admin"):
            return self.admin_limit
        if path.startswith("/v1/chat/completions") or path.startswith("/v1/responses"):
            return self.chat_limit
        if path.startswith("/v1/models") or path == "/health":
            return self.models_limit
        return max(self.admin_limit, self.chat_limit, self.models_limit)

    async def _get_key(self, request: Request) -> str:
        path = request.url.path
        if path.startswith("/v1/chat/completions") or path.startswith("/v1/responses"):
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                raw_key = auth.removeprefix("Bearer ").strip()
                try:
                    key = await run_in_threadpool(
                        request.app.state.api_key_service.authenticate,
                        raw_key,
                    )
                except Exception:
                    pass
                else:
                    request.state.authenticated_api_key = key
                    return f"chat:key:{key['id']}"
            client_ip = _client_ip(
                request, trust_proxy_headers=self.trust_proxy_headers
            )
            return f"chat:unauthenticated:{client_ip}"
        if path.startswith("/admin"):
            bucket = "admin"
        elif path.startswith("/v1/models") or path == "/health":
            bucket = "models"
        else:
            bucket = "default"
        client_ip = _client_ip(
            request, trust_proxy_headers=self.trust_proxy_headers
        )
        return f"{bucket}:{client_ip}"

    def _cleanup_old_entries(self) -> None:
        now = time.time()
        cutoff = now - self.window_seconds
        empty_keys = [k for k, v in self._store.items() if not v or v[-1] < cutoff]
        for k in empty_keys:
            del self._store[k]

    def _add_rate_headers(
        self, response: Response, limit: int, remaining: int, reset: float
    ) -> None:
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        response.headers["X-RateLimit-Reset"] = str(int(reset))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        limit = self._get_limit(request)

        if limit == 0:
            return await call_next(request)

        content_length = request.headers.get("content-length")
        try:
            parsed_content_length = int(content_length) if content_length else None
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Content-Length header"},
            )
        if parsed_content_length is not None and parsed_content_length < 0:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Content-Length header"},
            )
        if (
            parsed_content_length is not None
            and parsed_content_length > self.max_request_size_bytes
        ):
            return JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request body too large (max {self.max_request_size_bytes} bytes)"
                },
            )

        body = await request.body()
        if len(body) > self.max_request_size_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request body too large (max {self.max_request_size_bytes} bytes)"
                },
            )

        key = await self._get_key(request)
        now = time.time()
        if now - self._last_cleanup >= 300:
            self._cleanup_old_entries()
            self._last_cleanup = now
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
