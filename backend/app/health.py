from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core import limits
from app.core.db import get_db
from app.core.errors import AppError
from app.core.i18n import LOCALES

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def health_db(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise AppError("DATABASE_UNAVAILABLE", 503) from exc
    return {"status": "ok"}


@router.get("/config")
def config() -> dict[str, object]:
    """Limits the panel forms use, so frontend and backend validate the same way."""
    return {
        "locales": list(LOCALES),
        "username": {"maxLength": limits.USERNAME_MAX},
        "password": {"minLength": limits.PASSWORD_MIN, "maxLength": limits.PASSWORD_MAX},
        "announcement": {
            "titleMinLength": limits.ANNOUNCEMENT_TITLE_MIN,
            "titleMaxLength": limits.ANNOUNCEMENT_TITLE_MAX,
            "textMinLength": limits.ANNOUNCEMENT_TEXT_MIN,
            "textMaxLength": limits.ANNOUNCEMENT_TEXT_MAX,
            "maxValidYears": limits.ANNOUNCEMENT_MAX_VALID_YEARS,
            "proposalDefaultValidDays": limits.PROPOSAL_DEFAULT_VALID_DAYS,
        },
        "countdown": {
            "titleMinLength": limits.COUNTDOWN_TITLE_MIN,
            "titleMaxLength": limits.COUNTDOWN_TITLE_MAX,
        },
    }
