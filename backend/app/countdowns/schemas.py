from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, StringConstraints

from app.core import limits
from app.core.schemas import ApiModel
from app.users.schemas import UserRef

Title = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=limits.COUNTDOWN_TITLE_MIN,
        max_length=limits.COUNTDOWN_TITLE_MAX,
    ),
]


class CountdownOut(ApiModel):
    id: int
    title: str
    count_to: datetime
    author: UserRef | None


class CountdownCreate(ApiModel):
    title: Title
    count_to: AwareDatetime


class CountdownUpdate(ApiModel):
    title: Title | None = None
    count_to: AwareDatetime | None = None
