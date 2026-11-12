from typing import Optional
from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
from app.models.enums import DayOfWeek, LessonType, TeacherStatus, WeekParity


class TeacherProfile(Base, TimestampMixin):
    """
    O'qituvchi sifatida ro'yxatdan o'tgan foydalanuvchi. Admin tasdiqlaguncha PENDING:
    shunda talaba o'zini o'qituvchi deb ko'rsatib, o'qituvchi imkoniyatlaridan foydalana olmaydi.
    """
    __tablename__ = "teacher_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    university_id: Mapped[Optional[int]] = mapped_column(ForeignKey("universities.id", ondelete="SET NULL"), nullable=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # kafedra / fakultet
    status: Mapped[TeacherStatus] = mapped_column(
        Enum(TeacherStatus, native_enum=False, length=20),
        default=TeacherStatus.PENDING,
        nullable=False,
        index=True,
    )


class TeacherLesson(Base, TimestampMixin):
    """O'qituvchining o'z dars jadvali: har bir dars qaysi guruhda, qaysi xonada"""
    __tablename__ = "teacher_lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teacher_profiles.id", ondelete="CASCADE"), index=True, nullable=False)
    day_of_week: Mapped[DayOfWeek] = mapped_column(Enum(DayOfWeek, native_enum=False, length=20), nullable=False, index=True)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # to'liq fan kodi (BGH001-3)
    group_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    room: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lesson_type: Mapped[LessonType] = mapped_column(
        Enum(LessonType, native_enum=False, length=20), default=LessonType.OTHER, nullable=False
    )
    week_parity: Mapped[WeekParity] = mapped_column(
        Enum(WeekParity, native_enum=False, length=10), default=WeekParity.ALL, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
