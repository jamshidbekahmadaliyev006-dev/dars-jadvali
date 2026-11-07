from typing import List, Optional
from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin
from app.models.enums import UserRole


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(String(150), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20),
        default=UserRole.USER,
        nullable=False,
        index=True,
    )
    language_code: Mapped[str] = mapped_column(String(10), default="uz", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Universitet bog'lanishlari (ixtiyoriy, keyingi bosqichlarda to'ldiriladi)
    university_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("universities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    faculty_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("faculties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    university: Mapped[Optional["University"]] = relationship("University", back_populates="users")
    faculty: Mapped[Optional["Faculty"]] = relationship("Faculty", back_populates="users")
    group: Mapped[Optional["Group"]] = relationship("Group", back_populates="users")

    tasks: Mapped[List["PersonalTask"]] = relationship("PersonalTask", back_populates="user", cascade="all, delete-orphan")
    events: Mapped[List["PersonalEvent"]] = relationship("PersonalEvent", back_populates="user", cascade="all, delete-orphan")
    reminder_settings: Mapped[Optional["ReminderSetting"]] = relationship("ReminderSetting", back_populates="user", uselist=False, cascade="all, delete-orphan")
    submissions: Mapped[List["ScheduleSubmission"]] = relationship(
        "ScheduleSubmission",
        back_populates="user",
        foreign_keys="[ScheduleSubmission.user_id]",
    )
