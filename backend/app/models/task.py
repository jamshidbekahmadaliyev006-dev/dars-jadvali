from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, false, true
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin
from app.models.enums import TaskPriority


class PersonalTask(Base, TimestampMixin):
    """Talabaning shaxsiy vazifalari"""
    __tablename__ = "personal_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, native_enum=False, length=20),
        default=TaskPriority.MEDIUM,
        nullable=False,
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="tasks")


class PersonalEvent(Base, TimestampMixin):
    """Talabaning shaxsiy kalendar tadbirlari (imtihon, deadline, shaxsiy reja)"""
    __tablename__ = "personal_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), default="exam", nullable=False)  # exam, deadline, homework, meeting, other
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Bot "Mening rejalarim": boshqa foydalanuvchilar ham muhim uchrashuv, kun tartibi va h.k. uchun foydalanadi.
    # start_time naive UTC; has_time=False - faqat sana yozilgan (eslatma soat 09:00 ga qo'yiladi)
    place: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    has_time: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    remind1_sent: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    remind2_sent: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="events")
