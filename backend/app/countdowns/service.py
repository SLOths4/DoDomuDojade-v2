from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import AppError
from app.core.events import record_event
from app.countdowns.models import Countdown
from app.countdowns.schemas import CountdownCreate, CountdownUpdate
from app.users.models import User


def _check_future(count_to: datetime) -> None:
    if count_to <= clock.now():
        raise AppError("COUNT_TO_IN_PAST", 400)


def list_countdowns(db: Session) -> list[Countdown]:
    return list(db.scalars(select(Countdown).order_by(Countdown.count_to)))


def get_countdown(db: Session, countdown_id: int) -> Countdown:
    countdown = db.get(Countdown, countdown_id)
    if countdown is None:
        raise AppError("COUNTDOWN_NOT_FOUND", 404)
    return countdown


def create(db: Session, author: User, data: CountdownCreate) -> Countdown:
    _check_future(data.count_to)
    countdown = Countdown(title=data.title, count_to=data.count_to, author=author)
    db.add(countdown)
    db.flush()
    record_event(db, "countdown.created", id=countdown.id)
    db.commit()
    return countdown


def update(db: Session, countdown: Countdown, data: CountdownUpdate) -> Countdown:
    if data.count_to is not None and data.count_to != countdown.count_to:
        _check_future(data.count_to)
        countdown.count_to = data.count_to
    if data.title is not None:
        countdown.title = data.title
    record_event(db, "countdown.updated", id=countdown.id)
    db.commit()
    return countdown


def remove(db: Session, countdown: Countdown) -> None:
    record_event(db, "countdown.deleted", id=countdown.id)
    db.delete(countdown)
    db.commit()
