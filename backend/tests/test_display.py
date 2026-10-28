import json
import threading
from collections.abc import Callable
from contextlib import nullcontext
from datetime import date, datetime, time

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.announcements.models import Announcement, AnnouncementStatus
from app.core import clock
from app.display.models import Quote
from app.integrations import live
from app.integrations.tram import departures_source
from app.modules.models import Module, ModuleName
from app.users.models import User
from tests.conftest import ApiClient, login

pytestmark = pytest.mark.db

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=clock.get_settings().tz)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now", lambda: NOW)
    monkeypatch.setattr(departures_source, "_timetable", None)
    monkeypatch.setattr(live.weather, "_fetched_at", None)
    monkeypatch.setattr(live.calendar, "_fetched_at", None)


def add_announcement(
    db: Session, title: str, valid_until: date, status: AnnouncementStatus
) -> None:
    db.add(
        Announcement(title=title, text="Treść ogłoszenia.", valid_until=valid_until, status=status)
    )
    db.commit()


def test_display_is_public_and_reports_empty_modules(api: ApiClient) -> None:
    snapshot = api.get("/api/display").json()
    assert set(snapshot) == {m.value for m in ModuleName}
    assert snapshot["departures"] == {
        "status": "empty",
        "data": None,
        "message": "Brak odjazdów w najbliższym czasie.",
    }


def test_only_approved_and_unexpired_announcements_are_shown(api: ApiClient, db: Session) -> None:
    add_announcement(db, "Aktualne", date(2026, 10, 28), AnnouncementStatus.APPROVED)
    add_announcement(db, "Wygasłe", date(2026, 10, 27), AnnouncementStatus.APPROVED)
    add_announcement(db, "Oczekujące", date(2026, 11, 28), AnnouncementStatus.PENDING)
    body = api.get("/api/display/announcement").json()
    assert body["status"] == "active"
    assert [a["title"] for a in body["data"]] == ["Aktualne"]


def test_inactive_and_out_of_window_modules(api: ApiClient, db: Session) -> None:
    db.add(Quote(day=NOW.date(), language="pl", text="Cytat", author="Autor", source="test"))
    db.execute(
        update(Module)
        .where(Module.name == ModuleName.QUOTE)
        .values(start_time=time(22), end_time=time(6))
    )
    db.commit()
    assert api.get("/api/display/quote").json()["status"] == "inactive"
    db.execute(
        update(Module)
        .where(Module.name == ModuleName.QUOTE)
        .values(start_time=time(0), end_time=time(0))
    )
    db.commit()
    assert api.get("/api/display/quote").json()["data"]["author"] == "Autor"


def test_weather_comes_from_live_value(api: ApiClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live.weather, "_value", {"temperature": 5.8})
    monkeypatch.setattr(live.weather, "_fetched_at", NOW)
    assert api.get("/api/display/weather").json()["data"] == {"temperature": 5.8}


def test_unknown_module_is_400(api: ApiClient) -> None:
    assert api.get("/api/display/tram").status_code == 400


def test_stream_sends_snapshot_then_changed_module(
    api: ApiClient, make_user: Callable[..., User], app_factory_client: Callable[[], ApiClient]
) -> None:
    make_user("moderator")
    editor = app_factory_client()
    login(editor, "moderator")

    events: list[tuple[str, dict[str, object]]] = []
    with api.stream("GET", "/api/display/stream") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        lines = response.iter_lines()
        event_name = None

        def next_event() -> None:
            nonlocal event_name
            for line in lines:
                if line.startswith("event: "):
                    event_name = line.removeprefix("event: ")
                elif line.startswith("data: ") and event_name:
                    events.append((event_name, json.loads(line.removeprefix("data: "))))
                    return

        next_event()
        writer = threading.Thread(
            target=editor.post,
            args=("/api/announcements",),
            kwargs={
                "json": {
                    "title": "Na żywo",
                    "text": "Ogłoszenie pojawia się od razu.",
                    "validUntil": "2026-11-01",
                }
            },
        )
        writer.start()
        next_event()
        writer.join()

    assert events[0][0] == "snapshot"
    assert events[0][1]["announcement"]["status"] == "empty"  # type: ignore[index]
    name, payload = events[1]
    assert name == "module"
    assert payload["name"] == "announcement"
    assert [a["title"] for a in payload["data"]] == ["Na żywo"]  # type: ignore[union-attr]


def test_module_change_sends_full_snapshot(db: Session) -> None:
    from app.display.router import _render

    db.execute(update(Module).where(Module.name == ModuleName.WORD).values(is_active=False))
    db.commit()
    assert db.scalar(select(Module.is_active).where(Module.name == ModuleName.WORD)) is False
    chunks = _render(lambda: nullcontext(db), {"modules"})
    assert len(chunks) == 1 and chunks[0].startswith("event: snapshot")
