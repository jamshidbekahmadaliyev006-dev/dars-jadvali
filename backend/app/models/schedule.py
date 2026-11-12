from typing import Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin
from app.models.enums import DayOfWeek, LessonType, SubmissionStatus, WeekParity


class ScheduleSubmission(Base, TimestampMixin):
    """Talabalar yuborgan dars jadvali screenshotlari va AI tahlili navbati"""
    __tablename__ = "schedule_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id", ondelete="CASCADE"), index=True, nullable=False)
    faculty_id: Mapped[Optional[int]] = mapped_column(ForeignKey("faculties.id", ondelete="SET NULL"), nullable=True)
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"), nullable=True)

    image_file_id: Mapped[str] = mapped_column(String(255), nullable=False)  # Telegram file_id
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, native_enum=False, length=30),
        default=SubmissionStatus.PENDING,
        nullable=False,
        index=True,
    )
    
    ai_extracted_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # AI ajratgan xom JSON
    ai_confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    ai_warnings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="submissions", foreign_keys="[ScheduleSubmission.user_id]")
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys="[ScheduleSubmission.reviewer_id]")


class Schedule(Base, TimestampMixin):
    """Tasdiqlangan va faol dars jadvali"""
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id", ondelete="CASCADE"), index=True, nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True, nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False)
    teacher_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)
    room_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)

    day_of_week: Mapped[DayOfWeek] = mapped_column(
        Enum(DayOfWeek, native_enum=False, length=20),
        nullable=False,
        index=True,
    )
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "09:00"
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)    # "10:20"
    lesson_type: Mapped[LessonType] = mapped_column(
        Enum(LessonType, native_enum=False, length=20),
        default=LessonType.LECTURE,
        nullable=False,
    )
    week_parity: Mapped[WeekParity] = mapped_column(
        Enum(WeekParity, native_enum=False, length=10),
        default=WeekParity.ALL,
        server_default=WeekParity.ALL.value,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Fan kodi jadvalda yozilganidek to'liq (BGH001-3, PHY018-L2): talabaga fan nomi oldida ko'rsatiladi
    code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Relationships
    group: Mapped["Group"] = relationship("Group", back_populates="schedules")
    subject: Mapped["Subject"] = relationship("Subject", back_populates="schedules")
    teacher: Mapped[Optional["Teacher"]] = relationship("Teacher", back_populates="schedules")
    room: Mapped[Optional["Room"]] = relationship("Room", back_populates="schedules")


class ReminderSetting(Base, TimestampMixin):
    """Foydalanuvchining dars eslatmalari sozlamalari"""
    __tablename__ = "reminder_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    minutes_before: Mapped[int] = mapped_column(Integer, default=15, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="reminder_settings")
