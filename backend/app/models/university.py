from typing import List, Optional
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class University(Base, TimestampMixin):
    __tablename__ = "universities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    faculties: Mapped[List["Faculty"]] = relationship("Faculty", back_populates="university", cascade="all, delete-orphan")
    buildings: Mapped[List["Building"]] = relationship("Building", back_populates="university", cascade="all, delete-orphan")
    groups: Mapped[List["Group"]] = relationship("Group", back_populates="university", cascade="all, delete-orphan")
    users: Mapped[List["User"]] = relationship("User", back_populates="university")


class Faculty(Base, TimestampMixin):
    __tablename__ = "faculties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        UniqueConstraint("university_id", "name", name="uq_university_faculty_name"),
    )

    # Relationships
    university: Mapped["University"] = relationship("University", back_populates="faculties")
    groups: Mapped[List["Group"]] = relationship("Group", back_populates="faculty", cascade="all, delete-orphan")
    users: Mapped[List["User"]] = relationship("User", back_populates="faculty")


class Group(Base, TimestampMixin):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id", ondelete="CASCADE"), index=True, nullable=False)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculties.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    course_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("faculty_id", "name", name="uq_faculty_group_name"),
    )

    # Relationships
    university: Mapped["University"] = relationship("University", back_populates="groups")
    faculty: Mapped["Faculty"] = relationship("Faculty", back_populates="groups")
    users: Mapped[List["User"]] = relationship("User", back_populates="group")
    schedules: Mapped[List["Schedule"]] = relationship("Schedule", back_populates="group", cascade="all, delete-orphan")


class Building(Base, TimestampMixin):
    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # Masalan: "Bosh bino", "2-bino"
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    university: Mapped["University"] = relationship("University", back_populates="buildings")
    rooms: Mapped[List["Room"]] = relationship("Room", back_populates="building", cascade="all, delete-orphan")


class Room(Base, TimestampMixin):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id", ondelete="CASCADE"), index=True, nullable=False)
    number: Mapped[str] = mapped_column(String(50), nullable=False)  # Masalan: "305", "101-A"
    floor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("building_id", "number", name="uq_building_room_number"),
    )

    # Relationships
    building: Mapped["Building"] = relationship("Building", back_populates="rooms")
    schedules: Mapped[List["Schedule"]] = relationship("Schedule", back_populates="room")


class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    schedules: Mapped[List["Schedule"]] = relationship("Schedule", back_populates="subject")


class Teacher(Base, TimestampMixin):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id", ondelete="CASCADE"), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    schedules: Mapped[List["Schedule"]] = relationship("Schedule", back_populates="teacher")
