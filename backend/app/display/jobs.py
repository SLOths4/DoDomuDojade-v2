"""Background refresh of display data; each job publishes the topic it changed."""

from app.core import clock
from app.core.db import get_sessionmaker
from app.core.events import broker
from app.integrations import live
from app.integrations.calendar import fetch_events
from app.integrations.daily import ensure_daily
from app.integrations.tram import departures_source
from app.integrations.weather import fetch_weather


def refresh_timetable(force_download: bool = False) -> None:
    departures_source.refresh_timetable(force_download)
    broker.publish("departures")


def refresh_delays() -> None:
    departures_source.refresh_delays(clock.now())
    broker.publish("departures")


def refresh_weather() -> None:
    live.weather.refresh(fetch_weather)


def refresh_calendar() -> None:
    live.calendar.refresh(lambda: fetch_events(clock.today()))


def refresh_daily() -> None:
    with get_sessionmaker()() as db:
        if ensure_daily(db, clock.today()):
            broker.publish("quote")
            broker.publish("word")


def minute_tick() -> None:
    """Module windows, countdowns and announcement expiry depend on the clock alone."""
    broker.publish("modules")


def restore_cached() -> None:
    live.weather.restore()
    live.calendar.restore()


def refresh_all() -> None:
    restore_cached()
    refresh_daily()
    refresh_weather()
    refresh_calendar()
    refresh_timetable()
    refresh_delays()
