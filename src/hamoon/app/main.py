from pathlib import Path

from fastapi import FastAPI

from hamoon.app.api.router import api_router
from hamoon.app.config.settings import get_settings
from hamoon.app.observability.json_logging import configure_structured_logging
from hamoon.app.observability.metrics import MetricsMiddleware, metrics_endpoint
from hamoon.app.observability.request_context import RequestContextMiddleware
from hamoon.app.observability.telemetry import configure_telemetry
from hamoon.infrastructure.ai.artifact_store import (
    build_internal_model_artifact_store,
)
from hamoon.infrastructure.ai.gemma4_baseline import (
    GEMMA4_BASELINE_PIPELINE_VERSION,
    GEMMA4_CONCRETE_MODEL_ID,
)
from hamoon.infrastructure.ai.gemma4_runtime import (
    Gemma4LoRAExecutor,
    Gemma4LoRATrainer,
)
from hamoon.infrastructure.ai.internal_model import (
    configure_internal_model_runtime,
)
from hamoon.infrastructure.db.session import engine


def create_app() -> FastAPI:
    settings = get_settings()
    checkpoint_root = (
        Path(settings.gemma4_base_checkpoint_root)
        if settings.gemma4_base_checkpoint_root
        else None
    )
    configure_internal_model_runtime(
        artifact_store=build_internal_model_artifact_store(settings),
        trainers={
            GEMMA4_BASELINE_PIPELINE_VERSION: Gemma4LoRATrainer(
                base_checkpoint_root=checkpoint_root,
                training_config_json=settings.gemma4_training_config_json,
            )
        },
        executors={
            GEMMA4_CONCRETE_MODEL_ID: Gemma4LoRAExecutor(
                base_checkpoint_root=checkpoint_root,
                generation_config_json=settings.gemma4_generation_config_json,
            )
        },
    )

    if settings.structured_logging:
        configure_structured_logging(
            service_name=settings.otel_service_name,
            environment=settings.environment,
        )
    application = FastAPI(
        title=settings.app_name,
        version=settings.application_version,
    )
    metrics_access_token = (
        settings.metrics_access_token.get_secret_value().strip()
        if settings.metrics_access_token is not None
        else ""
    )
    application.state.metrics_access_token = metrics_access_token or None
    if settings.metrics_enabled:
        application.add_middleware(MetricsMiddleware)
        application.add_route(
            "/metrics",
            metrics_endpoint,
            methods=["GET"],
            include_in_schema=False,
        )
    application.add_middleware(RequestContextMiddleware)
    application.include_router(api_router)
    configure_telemetry(
        application,
        settings=settings,
        engine=engine,
    )
    return application


app = create_app()
