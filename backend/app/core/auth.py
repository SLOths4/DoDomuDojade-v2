import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError, error_response
from app.users.models import Role, User

CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

_USER_KEY = "user_id"
_VERSION_KEY = "session_version"
_CSRF_KEY = "csrf"


def start_session(request: Request, user: User) -> None:
    request.session.clear()
    request.session[_USER_KEY] = user.id
    request.session[_VERSION_KEY] = user.session_version
    request.session[_CSRF_KEY] = secrets.token_urlsafe(32)


def end_session(request: Request) -> None:
    request.session.clear()
    request.session[_CSRF_KEY] = secrets.token_urlsafe(32)


async def csrf_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Double-submit check: the header must match the token kept in the signed session."""
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    if _CSRF_KEY not in request.session:
        request.session[_CSRF_KEY] = secrets.token_urlsafe(32)
    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not secrets.compare_digest(sent, request.session[_CSRF_KEY]):
            return error_response(request, "CSRF_INVALID", 403)
    response = await call_next(request)
    response.set_cookie(
        CSRF_COOKIE,
        request.session.get(_CSRF_KEY, ""),
        samesite="lax",
        secure=get_settings().cookie_secure,
        httponly=False,
    )
    return response


def get_current_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User:
    user_id = request.session.get(_USER_KEY)
    user = db.get(User, user_id) if isinstance(user_id, int) else None
    if (
        user is None
        or not user.is_active
        or user.session_version != request.session.get(_VERSION_KEY)
    ):
        end_session(request)
        raise AppError("UNAUTHENTICATED", 401)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_active_user(user: CurrentUser) -> User:
    if user.must_change_password:
        raise AppError("PASSWORD_CHANGE_REQUIRED", 403)
    return user


ActiveUser = Annotated[User, Depends(get_active_user)]


def get_admin(user: ActiveUser) -> User:
    if user.role != Role.ADMIN:
        raise AppError("FORBIDDEN", 403)
    return user


Admin = Annotated[User, Depends(get_admin)]
