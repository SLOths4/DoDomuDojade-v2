from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth import ActiveUser
from app.core.db import get_db
from app.countdowns import service
from app.countdowns.schemas import CountdownCreate, CountdownOut, CountdownUpdate

Db = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/countdowns", tags=["countdowns"])


@router.get("")
def list_countdowns(_: ActiveUser, db: Db) -> list[CountdownOut]:
    return [CountdownOut.model_validate(c) for c in service.list_countdowns(db)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create(user: ActiveUser, body: CountdownCreate, db: Db) -> CountdownOut:
    return CountdownOut.model_validate(service.create(db, user, body))


@router.get("/{countdown_id}")
def get(_: ActiveUser, countdown_id: int, db: Db) -> CountdownOut:
    return CountdownOut.model_validate(service.get_countdown(db, countdown_id))


@router.patch("/{countdown_id}")
def update(_: ActiveUser, countdown_id: int, body: CountdownUpdate, db: Db) -> CountdownOut:
    countdown = service.update(db, service.get_countdown(db, countdown_id), body)
    return CountdownOut.model_validate(countdown)


@router.delete("/{countdown_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(_: ActiveUser, countdown_id: int, db: Db) -> Response:
    service.remove(db, service.get_countdown(db, countdown_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
