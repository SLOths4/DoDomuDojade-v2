import logging
import secrets
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.i18n import locale_from_header, translate

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-Id"


class AppError(Exception):
    """Error returned as the standard envelope; message comes from `errors.<code>` in locales."""

    def __init__(self, code: str, status_code: int = 400, **context: Any) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.context = context


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", ""))


def error_response(
    request: Request, code: str, status_code: int, context: dict[str, Any] | None = None
) -> JSONResponse:
    context = context or {}
    locale = locale_from_header(request.headers.get("accept-language"))
    request_id = _request_id(request)
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "data": {"code": code, "context": context},
            "message": translate(f"errors.{code}", locale, **context),
            "request_id": request_id,
        },
        headers={REQUEST_ID_HEADER: request_id},
    )


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get(REQUEST_ID_HEADER) or secrets.token_hex(8)
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response


_HTTP_CODES = {
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(request, exc.code, exc.status_code, exc.context)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = {
            ".".join(str(part) for part in err["loc"] if part != "body"): err["type"]
            for err in exc.errors()
        }
        return error_response(request, "VALIDATION_ERROR", 400, {"fields": fields})

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        return error_response(request, code, exc.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", extra={"request_id": _request_id(request)})
        return error_response(request, "INTERNAL_SERVER_ERROR", 500)
