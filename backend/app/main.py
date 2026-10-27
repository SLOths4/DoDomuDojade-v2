import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.errors import register_error_handlers, request_id_middleware
from app.health import router as health_router


def create_app() -> FastAPI:
    logging.basicConfig(level=get_settings().log_level.upper())
    app = FastAPI(
        title="DoDomuDojadę",
        version="2.0.0.dev0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.middleware("http")(request_id_middleware)
    register_error_handlers(app)
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
