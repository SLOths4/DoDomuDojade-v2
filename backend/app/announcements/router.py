import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.announcements import service
from app.announcements.models import AnnouncementStatus
from app.announcements.schemas import (
    AnnouncementCreate,
    AnnouncementOut,
    AnnouncementUpdate,
    ProposalCreate,
)
from app.core.auth import ActiveUser
from app.core.db import get_db
from app.core.errors import AppError
from app.core.rate_limit import proposals

Db = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.get("")
def list_announcements(
    _: ActiveUser, db: Db, status: AnnouncementStatus | None = None
) -> list[AnnouncementOut]:
    return [AnnouncementOut.model_validate(a) for a in service.list_announcements(db, status)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create(user: ActiveUser, body: AnnouncementCreate, db: Db) -> AnnouncementOut:
    return AnnouncementOut.model_validate(service.create(db, user, body))


@router.post("/proposals", status_code=status.HTTP_201_CREATED)
def propose(request: Request, body: ProposalCreate, db: Db) -> AnnouncementOut:
    key = request.client.host if request.client else "unknown"
    if proposals.is_blocked(key):
        raise AppError("TOO_MANY_PROPOSALS", 429)
    announcement = service.propose(db, body)
    proposals.hit(key)
    return AnnouncementOut.model_validate(announcement)


@router.get("/{announcement_id}")
def get(_: ActiveUser, announcement_id: uuid.UUID, db: Db) -> AnnouncementOut:
    return AnnouncementOut.model_validate(service.get_announcement(db, announcement_id))


@router.patch("/{announcement_id}")
def update(
    _: ActiveUser, announcement_id: uuid.UUID, body: AnnouncementUpdate, db: Db
) -> AnnouncementOut:
    announcement = service.update(db, service.get_announcement(db, announcement_id), body)
    return AnnouncementOut.model_validate(announcement)


@router.post("/{announcement_id}/approve")
def approve(user: ActiveUser, announcement_id: uuid.UUID, db: Db) -> AnnouncementOut:
    announcement = service.get_announcement(db, announcement_id)
    return AnnouncementOut.model_validate(
        service.decide(db, announcement, user, AnnouncementStatus.APPROVED)
    )


@router.post("/{announcement_id}/reject")
def reject(user: ActiveUser, announcement_id: uuid.UUID, db: Db) -> AnnouncementOut:
    announcement = service.get_announcement(db, announcement_id)
    return AnnouncementOut.model_validate(
        service.decide(db, announcement, user, AnnouncementStatus.REJECTED)
    )


@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(_: ActiveUser, announcement_id: uuid.UUID, db: Db) -> Response:
    service.remove(db, service.get_announcement(db, announcement_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
