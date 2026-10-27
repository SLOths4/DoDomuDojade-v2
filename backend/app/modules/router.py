from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import ActiveUser, Admin
from app.core.db import get_db
from app.modules import service
from app.modules.schemas import ModuleOut, ModuleUpdate

Db = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/modules", tags=["modules"])


@router.get("")
def list_modules(_: ActiveUser, db: Db) -> list[ModuleOut]:
    return [ModuleOut.model_validate(m) for m in service.list_modules(db)]


@router.patch("/{module_id}")
def update(_: Admin, module_id: int, body: ModuleUpdate, db: Db) -> ModuleOut:
    return ModuleOut.model_validate(service.update(db, service.get_module(db, module_id), body))
