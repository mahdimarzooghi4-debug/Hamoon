from contextvars import ContextVar
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def current_request_id() -> str | None:
    return _request_id.get()


def current_correlation_id() -> str | None:
    return _correlation_id.get()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get("X-Request-Id") or str(uuid4())
        correlation_id = request.headers.get("X-Correlation-Id") or request_id

        request_token = _request_id.set(request_id)
        correlation_token = _correlation_id.set(correlation_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-Id"] = request_id
            response.headers["X-Correlation-Id"] = correlation_id
            return response
        finally:
            _request_id.reset(request_token)
            _correlation_id.reset(correlation_token)
