from fastapi import FastAPI

from hamoon.app.api.router import api_router
from hamoon.app.config.settings import get_settings
from hamoon.app.observability.request_context import RequestContextMiddleware


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )
    application.add_middleware(RequestContextMiddleware)
    application.include_router(api_router)
    return application


app = create_app()
