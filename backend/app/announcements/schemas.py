import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import StringConstraints

from app.announcements.models import AnnouncementStatus
from app.core import limits
from app.core.schemas import ApiModel
from app.users.schemas import UserRef

Title = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=limits.ANNOUNCEMENT_TITLE_MIN,
        max_length=limits.ANNOUNCEMENT_TITLE_MAX,
    ),
]
Text = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=limits.ANNOUNCEMENT_TEXT_MIN,
        max_length=limits.ANNOUNCEMENT_TEXT_MAX,
    ),
]


class AnnouncementOut(ApiModel):
    id: uuid.UUID
    title: str
    text: str
    valid_until: date
    status: AnnouncementStatus
    created_at: datetime
    author: UserRef | None
    decided_at: datetime | None
    decided_by: UserRef | None


class AnnouncementCreate(ApiModel):
    title: Title
    text: Text
    valid_until: date


class AnnouncementUpdate(ApiModel):
    title: Title | None = None
    text: Text | None = None
    valid_until: date | None = None


class ProposalCreate(ApiModel):
    title: Title
    text: Text
    valid_until: date | None = None
