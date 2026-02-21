from datetime import datetime
from sqlalchemy import BigInteger, Integer, Text, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(20), default="other")
    status: Mapped[str] = mapped_column(String(20), default="pending")

    group_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    topic_id: Mapped[int] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reminded_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    overdue_count: Mapped[int] = mapped_column(Integer, default=0)
    snooze_reason: Mapped[str] = mapped_column(Text, nullable=True)
