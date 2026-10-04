from __future__ import annotations

import secrets
import time

from fastapi import Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

HTTP_REQUESTS = Counter(
    "hamoon_http_requests_total",
    "HTTP requests handled by Hamoon.",
    ("route", "method", "status_class"),
)
HTTP_ERRORS = Counter(
    "hamoon_http_request_errors_total",
    "HTTP 5xx responses emitted by Hamoon.",
    ("route", "method"),
)
HTTP_DURATION = Histogram(
    "hamoon_http_request_duration_seconds",
    "HTTP request duration.",
    ("route", "method"),
)
HTTP_ACTIVE = Gauge(
    "hamoon_http_active_requests",
    "Currently active HTTP requests.",
)
OUTBOX_PUBLISH_SUCCESS = Counter(
    "hamoon_outbox_publish_success_total",
    "Successfully acknowledged outbox publishes.",
    ("event_type",),
)
OUTBOX_PUBLISH_FAILURE = Counter(
    "hamoon_outbox_publish_failure_total",
    "Failed outbox publish attempts.",
    ("event_type",),
)


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else "unmatched"


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        started = time.perf_counter()
        HTTP_ACTIVE.inc()
        try:
            response = await call_next(request)
        finally:
            HTTP_ACTIVE.dec()

        route = _route_template(request)
        method = request.method
        status_class = f"{response.status_code // 100}xx"
        HTTP_REQUESTS.labels(
            route=route,
            method=method,
            status_class=status_class,
        ).inc()
        HTTP_DURATION.labels(route=route, method=method).observe(
            time.perf_counter() - started
        )
        if response.status_code >= 500:
            HTTP_ERRORS.labels(route=route, method=method).inc()
        return response


async def metrics_endpoint(request: Request) -> Response:
    expected_token = getattr(request.app.state, "metrics_access_token", None)
    if isinstance(expected_token, str) and expected_token:
        provided_token = request.headers.get("X-Hamoon-Metrics-Token", "")
        if not secrets.compare_digest(provided_token, expected_token):
            return Response(
                content="unauthorized\n",
                status_code=401,
                media_type="text/plain",
                headers={"Cache-Control": "no-store"},
            )

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
        headers={"Cache-Control": "no-store"},
    )
