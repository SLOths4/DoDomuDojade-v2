"""Latest results of external integrations, kept in memory and mirrored to the database."""

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from app.core import clock
from app.core.db import get_sessionmaker
from app.core.events import broker
from app.integrations import cache

logger = logging.getLogger(__name__)


class LiveValue:
    def __init__(self, key: str, topic: str, max_age: timedelta) -> None:
        self.key = key
        self.topic = topic
        self.max_age = max_age
        self._value: Any = None
        self._fetched_at: datetime | None = None
        self._lock = threading.Lock()

    def get(self, now: datetime) -> Any:
        with self._lock:
            if self._fetched_at is None or now - self._fetched_at > self.max_age:
                return None
            return self._value

    def set(self, value: Any, fetched_at: datetime, persist: bool = True) -> None:
        with self._lock:
            self._value, self._fetched_at = value, fetched_at
        if persist:
            with get_sessionmaker()() as db:
                cache.remember(db, self.key, value, fetched_at)
        broker.publish(self.topic)

    def restore(self) -> None:
        with get_sessionmaker()() as db:
            stored = cache.recall(db, self.key)
        if stored is not None:
            with self._lock:
                self._value, self._fetched_at = stored

    def refresh(self, fetch: Callable[[], Any]) -> None:
        try:
            value = fetch()
        except Exception:
            logger.exception("Refreshing %s failed; keeping the last value", self.key)
            return
        if value is not None:
            self.set(value, clock.now())


weather = LiveValue("weather", "weather", max_age=timedelta(hours=3))
calendar = LiveValue("calendar", "calendar", max_age=timedelta(hours=1))
