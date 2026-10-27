import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.announcements.models import Announcement, AnnouncementStatus
from app.announcements.schemas import AnnouncementCreate, AnnouncementUpdate, ProposalCreate
from app.core import clock, limits
from app.core.errors import AppError
from app.core.events import record_event
from app.users.models import User


def _check_valid_until(valid_until: date) -> None:
    today = clock.today()
    latest = clock.add_years(today, limits.ANNOUNCEMENT_MAX_VALID_YEARS)
    if not today <= valid_until <= latest:
        raise AppError(
            "VALID_UNTIL_OUT_OF_RANGE", 400, min=today.isoformat(), max=latest.isoformat()
        )


def list_announcements(db: Session, status: AnnouncementStatus | None = None) -> list[Announcement]:
    query = select(Announcement).order_by(Announcement.created_at.desc())
    if status is not None:
        query = query.where(Announcement.status == status)
    return list(db.scalars(query))


def get_announcement(db: Session, announcement_id: uuid.UUID) -> Announcement:
    announcement = db.get(Announcement, announcement_id)
    if announcement is None:
        raise AppError("ANNOUNCEMENT_NOT_FOUND", 404)
    return announcement


def create(db: Session, author: User, data: AnnouncementCreate) -> Announcement:
    _check_valid_until(data.valid_until)
    announcement = Announcement(
        title=data.title,
        text=data.text,
        valid_until=data.valid_until,
        status=AnnouncementStatus.APPROVED,
        author=author,
        decided_at=clock.now(),
        decided_by=author,
    )
    db.add(announcement)
    db.flush()
    record_event(db, "announcement.created", id=str(announcement.id))
    db.commit()
    return announcement


def propose(db: Session, data: ProposalCreate) -> Announcement:
    valid_until = data.valid_until or clock.today() + timedelta(
        days=limits.PROPOSAL_DEFAULT_VALID_DAYS
    )
    _check_valid_until(valid_until)
    announcement = Announcement(
        title=data.title,
        text=data.text,
        valid_until=valid_until,
        status=AnnouncementStatus.PENDING,
    )
    db.add(announcement)
    db.flush()
    record_event(db, "announcement.proposed", id=str(announcement.id))
    db.commit()
    return announcement


def update(db: Session, announcement: Announcement, data: AnnouncementUpdate) -> Announcement:
    if data.valid_until is not None and data.valid_until != announcement.valid_until:
        _check_valid_until(data.valid_until)
        announcement.valid_until = data.valid_until
    if data.title is not None:
        announcement.title = data.title
    if data.text is not None:
        announcement.text = data.text
    record_event(db, "announcement.updated", id=str(announcement.id))
    db.commit()
    return announcement


def decide(
    db: Session, announcement: Announcement, actor: User, status: AnnouncementStatus
) -> Announcement:
    announcement.status = status
    announcement.decided_at = clock.now()
    announcement.decided_by = actor
    record_event(db, f"announcement.{status.value}", id=str(announcement.id))
    db.commit()
    return announcement


def remove(db: Session, announcement: Announcement) -> None:
    record_event(db, "announcement.deleted", id=str(announcement.id))
    db.delete(announcement)
    db.commit()


def delete_rejected_before(db: Session, before: datetime) -> int:
    result = db.execute(
        delete(Announcement).where(
            Announcement.status == AnnouncementStatus.REJECTED,
            Announcement.decided_at < before,
        )
    )
    return int(result.rowcount)  # type: ignore[attr-defined]
