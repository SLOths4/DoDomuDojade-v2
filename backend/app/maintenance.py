import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.announcements.service import delete_rejected_before
from app.core import clock, limits
from app.core.db import get_sessionmaker
from app.core.events import prune_events

logger = logging.getLogger(__name__)


def cleanup(db: Session) -> dict[str, int]:
    now = clock.now()
    result = {
        "rejected_announcements": delete_rejected_before(
            db, now - timedelta(days=limits.REJECTED_ANNOUNCEMENT_RETENTION_DAYS)
        ),
        "events": prune_events(db, now - timedelta(days=limits.EVENT_RETENTION_DAYS)),
    }
    db.commit()
    return result


def scheduled_cleanup() -> None:
    with get_sessionmaker()() as db:
        logger.info("Cleanup finished: %s", cleanup(db))
