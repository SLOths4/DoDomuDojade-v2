from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.display.models import CachedPayload


def remember(db: Session, key: str, payload: Any, fetched_at: datetime) -> None:
    db.merge(CachedPayload(key=key, payload={"value": payload}, fetched_at=fetched_at))
    db.commit()


def recall(db: Session, key: str) -> tuple[Any, datetime] | None:
    row = db.get(CachedPayload, key)
    if row is None:
        return None
    return row.payload.get("value"), row.fetched_at
