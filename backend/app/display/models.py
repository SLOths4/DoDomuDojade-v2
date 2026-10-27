from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date, unique=True)
    language: Mapped[str] = mapped_column(String(2))
    text: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(64))


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date, unique=True)
    language: Mapped[str] = mapped_column(String(2))
    word: Mapped[str] = mapped_column(String(255))
    ipa: Mapped[str | None] = mapped_column(String(255))
    definition: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64))


class CachedPayload(Base):
    """Last successful result of an external integration, kept across restarts."""

    __tablename__ = "cached_payloads"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
