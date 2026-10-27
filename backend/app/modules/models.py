import enum
from datetime import time

from sqlalchemy import Boolean, Enum, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ModuleName(enum.StrEnum):
    ANNOUNCEMENT = "announcement"
    CALENDAR = "calendar"
    COUNTDOWN = "countdown"
    DEPARTURES = "departures"
    WEATHER = "weather"
    QUOTE = "quote"
    WORD = "word"


class Module(Base):
    """Display widget; a window with start_time > end_time spans midnight."""

    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[ModuleName] = mapped_column(
        Enum(
            ModuleName,
            name="module_name",
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        unique=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
