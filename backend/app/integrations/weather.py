"""Current weather from IMGW (temperature, pressure) and air quality from Airly (optional)."""

import logging
from typing import Any

from app.core.config import get_settings
from app.core.http import http_client

logger = logging.getLogger(__name__)

AIRLY_URL = "https://airapi.airly.eu/v2/measurements/location"


def _number(value: Any) -> float | None:
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def parse_imgw(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "station": data.get("stacja"),
        "temperature": _number(data.get("temperatura")),
        "pressure": _number(data.get("cisnienie")),
        "humidity": _number(data.get("wilgotnosc_wzgledna")),
        "windSpeed": _number(data.get("predkosc_wiatru")),
    }


def parse_airly(data: dict[str, Any]) -> dict[str, Any] | None:
    current = data.get("current") or {}
    values = {v.get("name"): v.get("value") for v in current.get("values", [])}
    index = next(iter(current.get("indexes") or []), None)
    if not index or index.get("value") is None:
        return None
    return {
        "caqi": _number(index.get("value")),
        "level": index.get("level"),
        "description": index.get("description"),
        "advice": index.get("advice"),
        "colour": index.get("color"),
        "pm25": _number(values.get("PM25")),
        "pm10": _number(values.get("PM10")),
    }


def fetch_weather() -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.imgw_weather_url:
        return None
    response = http_client().get(settings.imgw_weather_url)
    response.raise_for_status()
    weather = parse_imgw(response.json())
    weather["airQuality"] = None
    if settings.airly_api_key and settings.airly_location_id:
        try:
            airly = http_client().get(
                AIRLY_URL,
                params={"locationId": settings.airly_location_id.strip("/")},
                headers={"apikey": settings.airly_api_key, "Accept-Language": "pl"},
            )
            airly.raise_for_status()
            weather["airQuality"] = parse_airly(airly.json())
        except Exception:
            logger.exception("Airly request failed; showing weather without air quality")
    return weather
