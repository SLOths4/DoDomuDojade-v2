"""Today's events from a Google Calendar shared with a service account."""

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.core.config import get_settings

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def parse_event(item: dict[str, Any], tz: ZoneInfo) -> dict[str, Any]:
    start, end = item.get("start", {}), item.get("end", {})
    all_day = "dateTime" not in start
    return {
        "summary": item.get("summary") or "",
        "description": item.get("description") or "",
        "allDay": all_day,
        "start": None
        if all_day
        else datetime.fromisoformat(start["dateTime"]).astimezone(tz).isoformat(),
        "end": None
        if all_day or "dateTime" not in end
        else datetime.fromisoformat(end["dateTime"]).astimezone(tz).isoformat(),
    }


def fetch_events(day: date) -> list[dict[str, Any]] | None:
    settings = get_settings()
    if not settings.google_service_account_file or not settings.google_calendar_id:
        return None
    credentials = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
        settings.google_service_account_file, scopes=SCOPES
    )
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    start = datetime.combine(day, time.min, settings.tz)
    response = (
        service.events()
        .list(
            calendarId=settings.google_calendar_id,
            timeMin=start.isoformat(),
            timeMax=(start + timedelta(days=1)).isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=50,
        )
        .execute()
    )
    events = [parse_event(item, settings.tz) for item in response.get("items", [])]
    # All-day events first, then by start time.
    return sorted(events, key=lambda e: (not e["allDay"], e["start"] or ""))
