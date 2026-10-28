"""Departures for the configured stops from ZTM Poznań GTFS (timetable) and GTFS-RT (delays)."""

import csv
import io
import logging
import threading
import time as monotonic
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

from google.transit import gtfs_realtime_pb2

from app.core.config import get_settings
from app.core.http import http_client

logger = logging.getLogger(__name__)

GTFS_URL = "https://www.ztm.poznan.pl/pl/dla-deweloperow/getGTFSFile"
TRIP_UPDATES_URL = (
    "https://www.ztm.poznan.pl/pl/dla-deweloperow/getGtfsRtFile/?file=trip_updates.pb"
)
REALTIME_MAX_AGE = timedelta(minutes=3)
HORIZON = timedelta(minutes=90)
STATIC_MAX_AGE_HOURS = 20
ROUTE_TYPES = {0: "tram", 3: "bus"}


@dataclass(frozen=True)
class StopTime:
    trip_id: str
    stop_code: str
    sequence: int
    seconds: int
    headsign: str


@dataclass(frozen=True)
class Trip:
    line: str
    vehicle: str
    service_id: str
    headsign: str


@dataclass(frozen=True)
class Service:
    weekdays: tuple[bool, ...]
    start: date
    end: date


@dataclass(frozen=True)
class Departure:
    stop_code: str
    line: str
    vehicle: str
    direction: str
    at: datetime
    realtime: bool

    def minutes(self, now: datetime) -> int:
        return max(0, int((self.at - now).total_seconds() // 60))


@dataclass(frozen=True)
class Delay:
    sequence: int
    seconds: int


@dataclass
class Timetable:
    stop_times: list[StopTime] = field(default_factory=list)
    trips: dict[str, Trip] = field(default_factory=dict)
    services: dict[str, Service] = field(default_factory=dict)
    exceptions: dict[tuple[str, date], int] = field(default_factory=dict)

    def runs_on(self, service_id: str, day: date) -> bool:
        exception = self.exceptions.get((service_id, day))
        if exception is not None:
            return exception == 1
        service = self.services.get(service_id)
        return (
            service is not None
            and service.start <= day <= service.end
            and service.weekdays[day.weekday()]
        )

    def departures(
        self, now: datetime, delays: dict[str, Delay], limit: int = 30
    ) -> list[Departure]:
        tz = now.tzinfo
        result: list[Departure] = []
        # Trips that started yesterday can still run after midnight (times like 24:30:00).
        for service_day in (now.date() - timedelta(days=1), now.date()):
            # GTFS times count from noon minus 12h, which stays correct across DST changes.
            base = datetime.combine(service_day, time(12), tz) - timedelta(hours=12)
            for stop_time in self.stop_times:
                trip = self.trips.get(stop_time.trip_id)
                if trip is None or not self.runs_on(trip.service_id, service_day):
                    continue
                at = base + timedelta(seconds=stop_time.seconds)
                if at > now + HORIZON + timedelta(minutes=30):
                    continue
                delay = delays.get(stop_time.trip_id)
                if delay is not None:
                    if delay.sequence > stop_time.sequence:
                        continue  # the vehicle has already passed this stop
                    at += timedelta(seconds=delay.seconds)
                if not now - timedelta(seconds=30) <= at <= now + HORIZON:
                    continue
                result.append(
                    Departure(
                        stop_code=stop_time.stop_code,
                        line=trip.line,
                        vehicle=trip.vehicle,
                        direction=stop_time.headsign.strip("! ") or trip.headsign,
                        at=at,
                        realtime=delay is not None,
                    )
                )
        result.sort(key=lambda d: (d.at, d.line))
        return result[:limit]


def _rows(archive: zipfile.ZipFile, name: str) -> Iterator[dict[str, str]]:
    if name not in archive.namelist():
        return
    with archive.open(name) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig"))


def _seconds(value: str) -> int:
    hours, minutes, seconds = (int(part) for part in value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def _date(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def parse_gtfs(path: Path, stop_name: str, stop_codes: set[str]) -> Timetable:
    timetable = Timetable()
    with zipfile.ZipFile(path) as archive:
        stops = {
            row["stop_id"]: row["stop_code"]
            for row in _rows(archive, "stops.txt")
            if row["stop_name"] == stop_name and (not stop_codes or row["stop_code"] in stop_codes)
        }
        routes = {
            row["route_id"]: (row["route_short_name"], int(row["route_type"]))
            for row in _rows(archive, "routes.txt")
        }
        for row in _rows(archive, "stop_times.txt"):
            stop_code = stops.get(row["stop_id"])
            if stop_code is None or row.get("pickup_type") == "1":
                continue
            timetable.stop_times.append(
                StopTime(
                    trip_id=row["trip_id"],
                    stop_code=stop_code,
                    sequence=int(row["stop_sequence"]),
                    seconds=_seconds(row["departure_time"]),
                    headsign=row.get("stop_headsign", ""),
                )
            )
        trip_ids = {st.trip_id for st in timetable.stop_times}
        for row in _rows(archive, "trips.txt"):
            if row["trip_id"] not in trip_ids:
                continue
            line, route_type = routes.get(row["route_id"], (row["route_id"], 3))
            timetable.trips[row["trip_id"]] = Trip(
                line=line,
                vehicle=ROUTE_TYPES.get(route_type, "bus"),
                service_id=row["service_id"],
                headsign=row.get("trip_headsign", ""),
            )
        for row in _rows(archive, "calendar.txt"):
            days = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
            timetable.services[row["service_id"]] = Service(
                weekdays=tuple(row[d] == "1" for d in days),
                start=_date(row["start_date"]),
                end=_date(row["end_date"]),
            )
        for row in _rows(archive, "calendar_dates.txt"):
            timetable.exceptions[(row["service_id"], _date(row["date"]))] = int(
                row["exception_type"]
            )
    logger.info("GTFS loaded: %d stops, %d stop times", len(stops), len(timetable.stop_times))
    return timetable


def parse_trip_updates(data: bytes, now: datetime) -> dict[str, Delay] | None:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(data)
    generated = datetime.fromtimestamp(feed.header.timestamp, now.tzinfo)
    if now - generated > REALTIME_MAX_AGE:
        logger.warning("GTFS-RT feed is stale (generated %s)", generated.isoformat())
        return None
    delays: dict[str, Delay] = {}
    for entity in feed.entity:
        if not entity.HasField("trip_update") or not entity.trip_update.stop_time_update:
            continue
        update = entity.trip_update.stop_time_update[0]
        event = update.arrival if update.HasField("arrival") else update.departure
        delays[entity.trip_update.trip.trip_id] = Delay(update.stop_sequence, event.delay)
    return delays


class DeparturesSource:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._timetable: Timetable | None = None
        self._delays: dict[str, Delay] = {}
        self._delays_fetched = 0.0

    @property
    def gtfs_path(self) -> Path:
        return Path(get_settings().data_dir) / "gtfs.zip"

    def refresh_timetable(self, force_download: bool = False) -> None:
        path = self.gtfs_path
        path.parent.mkdir(parents=True, exist_ok=True)
        fresh = path.exists() and (
            monotonic.time() - path.stat().st_mtime < STATIC_MAX_AGE_HOURS * 3600
        )
        if force_download or not fresh:
            try:
                response = http_client().get(GTFS_URL, timeout=120)
                response.raise_for_status()
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(response.content)
                tmp.replace(path)
            except Exception:
                logger.exception("GTFS download failed; keeping the previous timetable")
                if not path.exists():
                    return
        settings = get_settings()
        codes = {c.strip() for c in settings.stop_codes.split(",") if c.strip()}
        timetable = parse_gtfs(path, settings.stop_name, codes)
        with self._lock:
            self._timetable = timetable

    def refresh_delays(self, now: datetime) -> None:
        try:
            response = http_client().get(TRIP_UPDATES_URL)
            response.raise_for_status()
            delays = parse_trip_updates(response.content, now)
        except Exception:
            logger.exception("GTFS-RT download failed")
            delays = None
        with self._lock:
            self._delays = delays or {}
            self._delays_fetched = monotonic.monotonic() if delays is not None else 0.0

    def departures(self, now: datetime) -> list[Departure] | None:
        with self._lock:
            timetable = self._timetable
            stale = monotonic.monotonic() - self._delays_fetched > REALTIME_MAX_AGE.total_seconds()
            delays = {} if stale else self._delays
        if timetable is None:
            return None
        return timetable.departures(now, delays)


departures_source = DeparturesSource()
