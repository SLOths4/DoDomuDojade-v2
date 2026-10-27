from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.auth import Admin, CurrentUser, end_session, start_session
from app.core.db import get_db
from app.core.errors import AppError
from app.core.rate_limit import login_failures
from app.users import service
from app.users.schemas import (
    LoginRequest,
    PasswordChange,
    PasswordReset,
    ProfileUpdate,
    UserCreate,
    UserOut,
    UserUpdate,
)

Db = Annotated[Session, Depends(get_db)]

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


@auth_router.post("/login")
def login(request: Request, body: LoginRequest, db: Db) -> UserOut:
    client = request.client.host if request.client else "unknown"
    key = f"{client}:{body.username.lower()}"
    if login_failures.is_blocked(key):
        raise AppError("TOO_MANY_ATTEMPTS", 429)
    user = service.authenticate(db, body.username, body.password)
    if user is None:
        login_failures.hit(key)
        raise AppError("INVALID_CREDENTIALS", 401)
    login_failures.reset(key)
    start_session(request, user)
    return UserOut.model_validate(user)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    end_session(request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@auth_router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@auth_router.patch("/me")
def update_profile(user: CurrentUser, body: ProfileUpdate, db: Db) -> UserOut:
    user.locale = body.locale
    db.commit()
    return UserOut.model_validate(user)


@auth_router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(request: Request, user: CurrentUser, body: PasswordChange, db: Db) -> Response:
    service.change_own_password(db, user, body.current_password, body.new_password)
    start_session(request, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@users_router.get("")
def list_users(_: Admin, db: Db) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in service.list_users(db)]


@users_router.post("", status_code=status.HTTP_201_CREATED)
def create_user(_: Admin, body: UserCreate, db: Db) -> UserOut:
    return UserOut.model_validate(service.create_user(db, body))


@users_router.patch("/{user_id}")
def update_user(actor: Admin, user_id: int, body: UserUpdate, db: Db) -> UserOut:
    user = service.update_user(db, actor, service.get_user(db, user_id), body)
    return UserOut.model_validate(user)


@users_router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(_: Admin, user_id: int, body: PasswordReset, db: Db) -> Response:
    service.reset_password(db, service.get_user(db, user_id), body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(actor: Admin, user_id: int, db: Db) -> Response:
    service.delete_user(db, actor, service.get_user(db, user_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
