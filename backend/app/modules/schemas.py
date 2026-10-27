from datetime import time

from pydantic import field_validator

from app.core.schemas import ApiModel
from app.modules.models import ModuleName


class ModuleOut(ApiModel):
    id: int
    name: ModuleName
    is_active: bool
    start_time: time
    end_time: time


class ModuleUpdate(ApiModel):
    is_active: bool | None = None
    start_time: time | None = None
    end_time: time | None = None

    @field_validator("start_time", "end_time")
    @classmethod
    def drop_seconds(cls, value: time | None) -> time | None:
        return value.replace(second=0, microsecond=0, tzinfo=None) if value else value
