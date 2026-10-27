from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.maintenance import scheduled_cleanup


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=get_settings().tz)
    scheduler.add_job(scheduled_cleanup, "cron", hour=3, minute=30, id="cleanup", coalesce=True)
    return scheduler
