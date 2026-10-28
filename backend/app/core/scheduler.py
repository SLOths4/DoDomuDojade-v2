from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.display import jobs
from app.maintenance import scheduled_cleanup


def create_scheduler() -> BackgroundScheduler:
    tz = get_settings().tz
    scheduler = BackgroundScheduler(
        timezone=tz, job_defaults={"coalesce": True, "max_instances": 1}
    )
    soon = datetime.now(tz) + timedelta(seconds=2)
    scheduler.add_job(jobs.refresh_all, "date", run_date=soon, id="startup")
    scheduler.add_job(jobs.refresh_delays, "interval", seconds=30, id="departures-realtime")
    scheduler.add_job(
        jobs.refresh_timetable, "cron", hour=3, minute=0, kwargs={"force_download": True}, id="gtfs"
    )
    scheduler.add_job(jobs.refresh_weather, "interval", minutes=15, id="weather")
    scheduler.add_job(jobs.refresh_calendar, "interval", minutes=5, id="calendar")
    scheduler.add_job(jobs.refresh_daily, "cron", minute=5, id="daily")
    scheduler.add_job(jobs.minute_tick, "cron", second=0, id="tick")
    scheduler.add_job(scheduled_cleanup, "cron", hour=3, minute=30, id="cleanup")
    return scheduler
