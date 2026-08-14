from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.stdlib.get_logger(__name__)


def _get_client_ip(request: Request, *, trust_proxy_headers: bool = False) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if trust_proxy_headers and forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, trust_proxy_headers: bool = False) -> None:  # type: ignore[override]
        super().__init__(app)
        self.trust_proxy_headers = trust_proxy_headers

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        client_ip = _get_client_ip(
            request, trust_proxy_headers=self.trust_proxy_headers
        )
        logger.info(
            "request_received",
            method=request.method,
            path=str(request.url.path),
            client_ip=client_ip,
        )

        response = await call_next(request)
        response.headers["X-Request-ID"] = correlation_id
        return response
