from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, CreatedAtMixin
from app.users.models import User


class Countdown(CreatedAtMixin, Base):
    __tablename__ = "countdowns"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    count_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    author: Mapped[User | None] = relationship(lazy="joined")
