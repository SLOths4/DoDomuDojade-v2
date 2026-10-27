"""Imports every model so Alembic sees the complete metadata."""

from app.announcements.models import Announcement, AnnouncementStatus
from app.core.db import Base
from app.core.events import Event
from app.countdowns.models import Countdown
from app.display.models import CachedPayload, Quote, Word
from app.modules.models import Module, ModuleName
from app.users.models import Role, User

__all__ = [
    "Announcement",
    "AnnouncementStatus",
    "Base",
    "CachedPayload",
    "Countdown",
    "Event",
    "Module",
    "ModuleName",
    "Quote",
    "Role",
    "User",
    "Word",
]
