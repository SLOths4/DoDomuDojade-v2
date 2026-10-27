from datetime import datetime
from typing import Annotated, Literal

from pydantic import StringConstraints

from app.core import limits
from app.core.schemas import ApiModel
from app.users.models import Role

Username = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=limits.USERNAME_MAX)
]
NewPassword = Annotated[
    str, StringConstraints(min_length=limits.PASSWORD_MIN, max_length=limits.PASSWORD_MAX)
]
AnyPassword = Annotated[str, StringConstraints(min_length=1, max_length=limits.PASSWORD_MAX)]
Locale = Literal["pl", "en"]


class UserRef(ApiModel):
    id: int
    username: str


class UserOut(ApiModel):
    id: int
    username: str
    role: Role
    locale: Locale
    is_active: bool
    must_change_password: bool
    created_at: datetime


class UserCreate(ApiModel):
    username: Username
    password: NewPassword
    role: Role = Role.MODERATOR


class UserUpdate(ApiModel):
    username: Username | None = None
    role: Role | None = None
    is_active: bool | None = None


class PasswordReset(ApiModel):
    new_password: NewPassword


class LoginRequest(ApiModel):
    username: Username
    password: AnyPassword


class PasswordChange(ApiModel):
    current_password: AnyPassword
    new_password: NewPassword


class ProfileUpdate(ApiModel):
    locale: Locale
