import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.announcements.router import router as announcements_router
from app.core.auth import csrf_middleware
from app.core.config import get_settings
from app.core.errors import register_error_handlers, request_id_middleware
from app.core.events import broker
from app.core.scheduler import create_scheduler
from app.countdowns.router import router as countdowns_router
from app.health import router as meta_router
from app.modules.router import router as modules_router
from app.users.router import auth_router, users_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    broker.bind(asyncio.get_running_loop())
    scheduler = create_scheduler() if get_settings().scheduler_enabled else None
    if scheduler:
        scheduler.start()
    try:
        yield
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    app = FastAPI(
        title="DoDomuDojadę",
        version="2.0.0.dev0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    # Middleware added later wraps earlier ones: request id → session → CSRF → routes.
    app.middleware("http")(csrf_middleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="ddd_session",
        max_age=settings.session_max_age_days * 24 * 3600,
        same_site="lax",
        https_only=settings.cookie_secure,
    )
    app.middleware("http")(request_id_middleware)
    register_error_handlers(app)
    for router in (
        meta_router,
        auth_router,
        users_router,
        announcements_router,
        countdowns_router,
        modules_router,
    ):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
