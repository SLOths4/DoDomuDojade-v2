from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.events import record_event
from app.modules.models import Module
from app.modules.schemas import ModuleUpdate


def in_window(start: time, end: time, at: time) -> bool:
    """Equal bounds mean the whole day; start after end means the window spans midnight."""
    if start == end:
        return True
    if start < end:
        return start <= at <= end
    return at >= start or at <= end


def is_visible(module: Module, at: time) -> bool:
    return module.is_active and in_window(module.start_time, module.end_time, at)


def list_modules(db: Session) -> list[Module]:
    return list(db.scalars(select(Module).order_by(Module.id)))


def get_module(db: Session, module_id: int) -> Module:
    module = db.get(Module, module_id)
    if module is None:
        raise AppError("MODULE_NOT_FOUND", 404)
    return module


def update(db: Session, module: Module, data: ModuleUpdate) -> Module:
    if data.is_active is not None:
        module.is_active = data.is_active
    if data.start_time is not None:
        module.start_time = data.start_time
    if data.end_time is not None:
        module.end_time = data.end_time
    record_event(db, "module.updated", id=module.id, name=module.name.value)
    db.commit()
    return module
