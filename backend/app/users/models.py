import enum

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAtMixin


class Role(enum.StrEnum):
    ADMIN = "admin"
    MODERATOR = "moderator"


class User(CreatedAtMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            name="user_role",
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    locale: Mapped[str] = mapped_column(String(2), server_default="pl")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    must_change_password: Mapped[bool] = mapped_column(Boolean, server_default="false")
    # Bumped on password change or deactivation; sessions carrying an older value are rejected.
    session_version: Mapped[int] = mapped_column(Integer, server_default="0")
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
