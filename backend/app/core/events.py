import asyncio
import logging
import threading
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, String, delete, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base, CreatedAtMixin

logger = logging.getLogger(__name__)

_PENDING_KEY = "pending_events"


class Event(CreatedAtMixin, Base):
    """Change log written in the same transaction as the data; id doubles as the SSE event id."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Broker:
    """Fans committed events out to SSE subscribers; publish() is safe from worker threads."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=100)
        with self._lock:
            self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        with self._lock:
            self._subscribers.discard(queue)

    def publish(self, item: Event) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        with self._lock:
            queues = list(self._subscribers)
        for queue in queues:
            loop.call_soon_threadsafe(_offer, queue, item)


def _offer(queue: asyncio.Queue[Event], item: Event) -> None:
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull:
        logger.warning("Dropping event %s for a slow subscriber", item.id)


broker = Broker()


def record_event(db: Session, type_: str, **payload: Any) -> Event:
    item = Event(type=type_, payload=payload)
    db.add(item)
    db.info.setdefault(_PENDING_KEY, []).append(item)
    return item


@event.listens_for(Session, "after_commit")
def _publish_committed(session: Session) -> None:
    for item in session.info.pop(_PENDING_KEY, []):
        broker.publish(item)


@event.listens_for(Session, "after_rollback")
def _drop_rolled_back(session: Session) -> None:
    session.info.pop(_PENDING_KEY, None)


def prune_events(db: Session, older_than: datetime) -> int:
    result = db.execute(delete(Event).where(Event.created_at < older_than))
    return int(result.rowcount)  # type: ignore[attr-defined]
