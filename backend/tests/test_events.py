import asyncio
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.announcements.models import Announcement, AnnouncementStatus
from app.core import clock
from app.core.events import Broker, Event, broker, record_event
from app.maintenance import cleanup

APP_DIR = Path(__file__).resolve().parent.parent / "app"


def test_broker_delivers_to_every_subscriber() -> None:
    async def scenario() -> list[str]:
        local = Broker()
        local.bind(asyncio.get_running_loop())
        first, second = local.subscribe(), local.subscribe()
        local.publish(Event(id=1, type="countdown.created", payload={}))
        received = [await asyncio.wait_for(q.get(), 1) for q in (first, second)]
        local.unsubscribe(first)
        local.publish(Event(id=2, type="countdown.deleted", payload={}))
        assert first.empty()
        return [e.type for e in received] + [(await second.get()).type]

    assert asyncio.run(scenario()) == [
        "countdown.created",
        "countdown.created",
        "countdown.deleted",
    ]


@pytest.mark.db
def test_events_are_published_only_after_commit(db: Session) -> None:
    async def scenario() -> list[str]:
        broker.bind(asyncio.get_running_loop())
        queue = broker.subscribe()
        try:
            record_event(db, "module.updated", id=1)
            db.rollback()
            record_event(db, "module.updated", id=2)
            await asyncio.sleep(0)
            assert queue.empty()
            db.commit()
            item = await asyncio.wait_for(queue.get(), 1)
            return [item.type, str(item.payload["id"])]
        finally:
            broker.unsubscribe(queue)

    assert asyncio.run(scenario()) == ["module.updated", "2"]


@pytest.mark.db
def test_cleanup_removes_old_rejected_and_old_events(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 10, 28, 12, 0, tzinfo=clock.get_settings().tz)
    monkeypatch.setattr(clock, "now", lambda: now)
    old, recent = now - timedelta(days=40), now - timedelta(days=5)
    for decided_at, status in (
        (old, AnnouncementStatus.REJECTED),
        (recent, AnnouncementStatus.REJECTED),
        (old, AnnouncementStatus.APPROVED),
    ):
        db.add(
            Announcement(
                title="Stare",
                text="Stare ogłoszenie do testu.",
                valid_until=now.date(),
                status=status,
                decided_at=decided_at,
            )
        )
    db.add(Event(type="old", payload={}, created_at=old))
    db.add(Event(type="new", payload={}, created_at=recent))
    db.commit()

    assert cleanup(db) == {"rejected_announcements": 1, "events": 1}


def test_every_error_code_has_messages_in_both_languages() -> None:
    codes = {
        match
        for path in APP_DIR.rglob("*.py")
        for match in re.findall(r'AppError\(\s*"([A-Z_]+)"', path.read_text(encoding="utf-8"))
    }
    codes |= {"CSRF_INVALID", "VALIDATION_ERROR", "INTERNAL_SERVER_ERROR"}
    for locale in ("pl", "en"):
        messages = json.loads((APP_DIR / "locales" / f"{locale}.json").read_text(encoding="utf-8"))
        missing = {code for code in codes if f"errors.{code}" not in messages}
        assert not missing, f"{locale}: {missing}"
