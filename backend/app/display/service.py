from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.announcements.models import Announcement, AnnouncementStatus
from app.countdowns.models import Countdown
from app.display.models import Quote, Word
from app.integrations import live
from app.integrations.tram import departures_source
from app.modules.models import Module, ModuleName
from app.modules.service import is_visible

EMPTY_MESSAGES = {
    ModuleName.ANNOUNCEMENT: "Brak ogłoszeń.",
    ModuleName.CALENDAR: "Brak wydarzeń w kalendarzu na dziś.",
    ModuleName.COUNTDOWN: "Brak zaplanowanych odliczań.",
    ModuleName.DEPARTURES: "Brak odjazdów w najbliższym czasie.",
    ModuleName.WEATHER: "Brak danych o pogodzie.",
    ModuleName.QUOTE: "Brak cytatu na dziś.",
    ModuleName.WORD: "Brak słowa na dziś.",
}
INACTIVE_MESSAGE = "Moduł jest wyłączony."


def _announcements(db: Session, now: datetime) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Announcement)
        .where(
            Announcement.status == AnnouncementStatus.APPROVED,
            Announcement.valid_until >= now.date(),
        )
        .order_by(Announcement.created_at.desc())
    )
    return [
        {
            "id": str(a.id),
            "title": a.title,
            "text": a.text,
            "author": a.author.username if a.author else None,
        }
        for a in rows
    ]


def _countdown(db: Session, now: datetime) -> dict[str, Any] | None:
    countdown = db.scalar(
        select(Countdown).where(Countdown.count_to > now).order_by(Countdown.count_to).limit(1)
    )
    if countdown is None:
        return None
    return {"title": countdown.title, "countTo": countdown.count_to.isoformat()}


def _departures(now: datetime) -> list[dict[str, Any]] | None:
    departures = departures_source.departures(now)
    if departures is None:
        return None
    return [
        {
            "stopCode": d.stop_code,
            "line": d.line,
            "vehicle": d.vehicle,
            "minutes": d.minutes(now),
            "direction": d.direction,
            "realtime": d.realtime,
        }
        for d in departures
    ]


def _quote(db: Session, now: datetime) -> dict[str, Any] | None:
    quote = db.scalar(select(Quote).where(Quote.day == now.date()))
    if quote is None:
        return None
    return {
        "text": quote.text,
        "author": quote.author,
        "language": quote.language,
        "source": quote.source,
    }


def _word(db: Session, now: datetime) -> dict[str, Any] | None:
    word = db.scalar(select(Word).where(Word.day == now.date()))
    if word is None:
        return None
    return {
        "word": word.word,
        "ipa": word.ipa,
        "definition": word.definition,
        "language": word.language,
        "source": word.source,
    }


def module_data(db: Session, name: ModuleName, now: datetime) -> Any:
    match name:
        case ModuleName.ANNOUNCEMENT:
            return _announcements(db, now)
        case ModuleName.COUNTDOWN:
            return _countdown(db, now)
        case ModuleName.DEPARTURES:
            return _departures(now)
        case ModuleName.QUOTE:
            return _quote(db, now)
        case ModuleName.WORD:
            return _word(db, now)
        case ModuleName.WEATHER:
            return live.weather.get(now)
        case ModuleName.CALENDAR:
            return live.calendar.get(now)


def module_envelope(db: Session, name: ModuleName, now: datetime) -> dict[str, Any]:
    module = db.scalar(select(Module).where(Module.name == name))
    if module is None or not is_visible(module, now.time()):
        return {"status": "inactive", "data": None, "message": INACTIVE_MESSAGE}
    data = module_data(db, name, now)
    if data is None or data == []:
        return {"status": "empty", "data": None, "message": EMPTY_MESSAGES[name]}
    return {"status": "active", "data": data, "message": None}


def snapshot(db: Session, now: datetime) -> dict[str, Any]:
    return {name.value: module_envelope(db, name, now) for name in ModuleName}
