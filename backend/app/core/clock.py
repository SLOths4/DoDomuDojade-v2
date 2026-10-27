from datetime import date, datetime

from app.core.config import get_settings


def now() -> datetime:
    return datetime.now(get_settings().tz)


def today() -> date:
    return now().date()


def add_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)
