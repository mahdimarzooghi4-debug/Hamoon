from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime

from fastapi import Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from hamoon.app.config.settings import get_settings
from hamoon.app.observability.heartbeats import (
    REQUIRED_WORKERS,
    read_operational_snapshot,
)

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
PROVIDER_DISPATCH_SUCCESS = Counter(
    "hamoon_provider_dispatch_success_total",
    "Successfully delivered provider referral dispatches.",
    ("provider_id",),
)
PROVIDER_DISPATCH_FAILURE = Counter(
    "hamoon_provider_dispatch_failure_total",
    "Failed provider referral dispatch attempts.",
    ("provider_id", "failure_class"),
)
PGOR_CALCULATIONS = Counter(
    "hamoon_pgor_calculations_total",
    "Deterministic PGOR calculation attempts.",
    ("mode", "status"),
)
AI_EXECUTIONS = Counter(
    "hamoon_ai_executions_total",
    "Structured AI gateway executions.",
    ("task_class", "provider", "status"),
)
SECURITY_DENIALS = Counter(
    "hamoon_security_denials_total",
    "Authorization and authentication denials.",
    ("boundary", "reason"),
)

DEPENDENCY_HEALTH = Gauge(
    "hamoon_dependency_health",
    "Dependency health where 1 is healthy and 0 is unavailable.",
    ("dependency",),
)
OUTBOX_PENDING = Gauge(
    "hamoon_outbox_pending_count",
    "Unpublished durable outbox messages.",
)
OUTBOX_OLDEST_AGE = Gauge(
    "hamoon_outbox_oldest_age_seconds",
    "Age in seconds of the oldest unpublished outbox message.",
)
WORKER_HEALTH = Gauge(
    "hamoon_worker_healthy",
    "Worker health for the current release where 1 is healthy and 0 is not healthy.",
    ("worker",),
)
WORKER_HEARTBEAT_AGE = Gauge(
    "hamoon_worker_heartbeat_age_seconds",
    "Age in seconds of the latest worker heartbeat.",
    ("worker",),
)
OPERATIONAL_METRICS_REFRESH_FAILURE = Counter(
    "hamoon_operational_metrics_refresh_failures_total",
    "Failures while refreshing DB-backed operational metrics.",
    ("dependency",),
)

_WORKER_HEARTBEAT_MAX_AGE_SECONDS = 45.0


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


async def refresh_operational_metrics() -> None:
    settings = get_settings()
    try:
        snapshot = await read_operational_snapshot()
    except Exception:
        DEPENDENCY_HEALTH.labels(dependency="postgresql").set(0)
        OPERATIONAL_METRICS_REFRESH_FAILURE.labels(
            dependency="postgresql"
        ).inc()
        return

    DEPENDENCY_HEALTH.labels(dependency="postgresql").set(1)
    OUTBOX_PENDING.set(snapshot.outbox_pending_count)
    OUTBOX_OLDEST_AGE.set(snapshot.outbox_oldest_age_seconds)

    now = datetime.now(UTC)
    by_name = {heartbeat.worker_name: heartbeat for heartbeat in snapshot.heartbeats}
    for worker_name in REQUIRED_WORKERS:
        heartbeat = by_name.get(worker_name)
        if heartbeat is None:
            WORKER_HEALTH.labels(worker=worker_name).set(0)
            WORKER_HEARTBEAT_AGE.labels(worker=worker_name).set(
                _WORKER_HEARTBEAT_MAX_AGE_SECONDS + 1
            )
            continue

        age = max(0.0, (now - heartbeat.observed_at).total_seconds())
        exact_release = (
            heartbeat.deployment_id == settings.deployment_id
            and heartbeat.git_commit == settings.git_commit
            and heartbeat.image_id == settings.image_id
        )
        healthy = (
            heartbeat.status == "READY"
            and exact_release
            and age <= _WORKER_HEARTBEAT_MAX_AGE_SECONDS
        )
        WORKER_HEALTH.labels(worker=worker_name).set(1 if healthy else 0)
        WORKER_HEARTBEAT_AGE.labels(worker=worker_name).set(age)


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

    await refresh_operational_metrics()
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
        headers={"Cache-Control": "no-store"},
    )
