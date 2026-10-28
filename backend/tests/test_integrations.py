import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from google.transit import gtfs_realtime_pb2
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.display.models import Quote, Word
from app.integrations import daily
from app.integrations.calendar import parse_event
from app.integrations.tram import Delay, parse_gtfs, parse_trip_updates
from app.integrations.weather import parse_airly, parse_imgw

TZ = ZoneInfo("Europe/Warsaw")
FIXTURES = Path(__file__).parent / "fixtures"


def write_gtfs(path: Path) -> Path:
    files = {
        "stops.txt": (
            "﻿stop_id,stop_code,stop_name,stop_lat,stop_lon,zone_id\n"
            '1,"AWF41","AWF",0,0,A\n2,"AWF05","AWF",0,0,A\n3,"RAT01","Rataje",0,0,A\n'
        ),
        "routes.txt": (
            "route_id,agency_id,route_short_name,route_long_name,route_desc,route_type\n"
            '6,2,"6","","",0\n222,2,"222","","",3\n'
        ),
        "trips.txt": (
            "route_id,service_id,trip_id,trip_headsign,direction_id\n"
            '6,WD,"t-day^A","Miłostowo",0\n'
            '222,WD,"t-night","Ławica",0\n'
            '6,SUN,"t-sunday","Junikowo",0\n'
        ),
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence,stop_headsign,pickup_type\n"
            '"t-day^A",12:10:00,12:10:00,1,5,"Miłostowo!",0\n'
            '"t-day^A",12:20:00,12:20:00,3,9,"Miłostowo",0\n'
            '"t-night",24:15:00,24:15:00,2,3,"",0\n'
            '"t-sunday",12:05:00,12:05:00,1,1,"",0\n'
            '"t-day^A",12:12:00,12:12:00,2,6,"",1\n'
        ),
        "calendar.txt": (
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            "WD,1,1,1,1,1,0,0,20261001,20261130\nSUN,0,0,0,0,0,0,1,20261001,20261130\n"
        ),
        "calendar_dates.txt": "service_id,date,exception_type\nSUN,20261028,1\n",
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


def test_timetable_selects_stops_by_name_and_skips_drop_off_only(tmp_path: Path) -> None:
    timetable = parse_gtfs(write_gtfs(tmp_path / "gtfs.zip"), "AWF", set())
    assert sorted((s.trip_id, s.stop_code) for s in timetable.stop_times) == [
        ("t-day^A", "AWF41"),
        ("t-night", "AWF05"),
        ("t-sunday", "AWF41"),
    ]
    only_41 = parse_gtfs(tmp_path / "gtfs.zip", "AWF", {"AWF41"})
    assert {s.stop_code for s in only_41.stop_times} == {"AWF41"}


def test_departures_apply_calendar_exceptions_and_delays(tmp_path: Path) -> None:
    timetable = parse_gtfs(write_gtfs(tmp_path / "gtfs.zip"), "AWF", set())
    now = datetime(2026, 10, 28, 12, 0, tzinfo=TZ)  # Wednesday with an extra Sunday service
    plain = timetable.departures(now, {})
    assert [(d.line, d.minutes(now), d.direction, d.vehicle) for d in plain] == [
        ("6", 5, "Junikowo", "tram"),
        ("6", 10, "Miłostowo", "tram"),
    ]
    delayed = timetable.departures(now, {"t-day^A": Delay(sequence=4, seconds=180)})
    assert [(d.line, d.minutes(now), d.realtime) for d in delayed][1] == ("6", 13, True)
    passed = timetable.departures(now, {"t-day^A": Delay(sequence=6, seconds=0)})
    assert [d.line for d in passed] == ["6"]


def test_trip_after_midnight_belongs_to_previous_service_day(tmp_path: Path) -> None:
    timetable = parse_gtfs(write_gtfs(tmp_path / "gtfs.zip"), "AWF", set())
    after_midnight = datetime(2026, 10, 29, 0, 5, tzinfo=TZ)
    departures = timetable.departures(after_midnight, {})
    assert [(d.line, d.minutes(after_midnight), d.direction) for d in departures] == [
        ("222", 10, "Ławica")
    ]


def test_trip_updates_parse_and_stale_feed_is_ignored() -> None:
    now = datetime(2026, 10, 28, 12, 0, tzinfo=TZ)
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "1.0"
    feed.header.timestamp = int((now - timedelta(seconds=20)).timestamp())
    entity = feed.entity.add(id="1")
    entity.trip_update.trip.trip_id = "t-day^A"
    update = entity.trip_update.stop_time_update.add(stop_sequence=4)
    update.arrival.delay = -60
    assert parse_trip_updates(feed.SerializeToString(), now) == {"t-day^A": Delay(4, -60)}

    feed.header.timestamp = int((now - timedelta(minutes=10)).timestamp())
    assert parse_trip_updates(feed.SerializeToString(), now) is None


def test_weather_parsing() -> None:
    imgw = parse_imgw(
        {
            "stacja": "Poznań",
            "temperatura": "5.8",
            "cisnienie": "1022.3",
            "wilgotnosc_wzgledna": "80.9",
        }
    )
    assert imgw == {
        "station": "Poznań",
        "temperature": 5.8,
        "pressure": 1022.3,
        "humidity": 80.9,
        "windSpeed": None,
    }
    airly = parse_airly(
        {
            "current": {
                "values": [{"name": "PM10", "value": 21.37}, {"name": "PM25", "value": 12.04}],
                "indexes": [
                    {
                        "name": "AIRLY_CAQI",
                        "value": 23.1,
                        "level": "VERY_LOW",
                        "description": "Bardzo dobre powietrze!",
                        "advice": "Ruszaj na spacer!",
                        "color": "#6BC926",
                    }
                ],
            }
        }
    )
    assert airly == {
        "caqi": 23.1,
        "level": "VERY_LOW",
        "description": "Bardzo dobre powietrze!",
        "advice": "Ruszaj na spacer!",
        "colour": "#6BC926",
        "pm25": 12.0,
        "pm10": 21.4,
    }
    assert parse_airly({"current": {"values": [], "indexes": [{"value": None}]}}) is None


def test_calendar_marks_all_day_events() -> None:
    all_day = parse_event({"summary": "Dzień Edukacji", "start": {"date": "2026-10-14"}}, TZ)
    assert all_day == {
        "summary": "Dzień Edukacji",
        "description": "",
        "allDay": True,
        "start": None,
        "end": None,
    }
    timed = parse_event(
        {
            "summary": "Rada",
            "start": {"dateTime": "2026-10-28T14:00:00Z"},
            "end": {"dateTime": "2026-10-28T15:30:00Z"},
        },
        TZ,
    )
    assert (timed["start"], timed["end"]) == (
        "2026-10-28T15:00:00+01:00",
        "2026-10-28T16:30:00+01:00",
    )


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_wikimedia_parsers_on_saved_pages() -> None:
    assert daily.parse_wikicytaty(read("wikicytaty_qotd.txt")) == daily.DailyQuote(
        "Dla chcącego nie ma nic trudnego.", "Erazm z Rotterdamu", "Wikicytaty"
    )
    quote = daily.parse_wikiquote(read("wikiquote_qotd.txt"))
    assert quote is not None and quote.author == "Jonas Salk" and "[[" not in quote.text
    assert daily.parse_wikislownik(read("wikislownik_wotd.txt")) == daily.DailyWord(
        "nieboskłon", "/ɲɛˈbɔskwɔ̃n/", "kopuła nieba, zwłaszcza jej dolna część", "Wikisłownik"
    )
    assert daily.parse_wiktionary(read("wiktionary_wotd.txt")) == daily.DailyWord(
        "comity",
        None,
        "Courtesy and considerate behaviour towards others; social harmony.",
        "Wiktionary",
    )


def test_language_alternates_by_day() -> None:
    first = daily.language_for(date(2026, 10, 28))
    assert {first, daily.language_for(date(2026, 10, 29))} == {"pl", "en"}


@pytest.mark.db
def test_ensure_daily_falls_back_to_local_list(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def offline(*_: object) -> None:
        raise ConnectionError("no network")

    monkeypatch.setattr(daily, "fetch_quote", offline)
    monkeypatch.setattr(daily, "fetch_word", offline)
    day = date(2026, 10, 28)
    assert daily.ensure_daily(db, day) is True
    assert daily.ensure_daily(db, day) is False
    quote = db.scalar(select(Quote).where(Quote.day == day))
    word = db.scalar(select(Word).where(Word.day == day))
    assert quote is not None and word is not None
    assert quote.source == word.source == "lokalna lista"
    assert quote.language == word.language == daily.language_for(day)


def test_fallback_lists_are_complete() -> None:
    for language in ("pl", "en"):
        for kind, keys in (
            ("quotes", {"text", "author"}),
            ("words", {"word", "ipa", "definition"}),
        ):
            items = daily._fallback(kind, language)
            assert len(items) >= 10
            assert all(keys <= item.keys() and all(item[k] for k in keys) for item in items)
