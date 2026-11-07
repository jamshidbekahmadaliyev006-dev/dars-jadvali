from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.enums import DayOfWeek, LessonType, SubmissionStatus, WeekParity
from app.schemas.university import GroupResponse, RoomResponse, SubjectResponse, TeacherResponse, UniversityResponse


class ScheduleBase(BaseModel):
    university_id: int
    group_id: int
    subject_id: int
    teacher_id: Optional[int] = None
    room_id: Optional[int] = None
    day_of_week: DayOfWeek
    start_time: str  # "09:00"
    end_time: str    # "10:20"
    lesson_type: LessonType = LessonType.LECTURE
    week_parity: WeekParity = WeekParity.ALL
    is_active: bool = True


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(BaseModel):
    subject_id: Optional[int] = None
    teacher_id: Optional[int] = None
    room_id: Optional[int] = None
    day_of_week: Optional[DayOfWeek] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    lesson_type: Optional[LessonType] = None
    week_parity: Optional[WeekParity] = None
    is_active: Optional[bool] = None


class ScheduleResponse(ScheduleBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ScheduleDetailResponse(ScheduleResponse):
    subject: Optional[SubjectResponse] = None
    teacher: Optional[TeacherResponse] = None
    room: Optional[RoomResponse] = None
    group: Optional[GroupResponse] = None


# --- Schedule Submission (AI OCR workflow) ---
class ScheduleSubmissionCreate(BaseModel):
    university_id: int
    faculty_id: Optional[int] = None
    group_id: Optional[int] = None
    image_file_id: str
    image_url: Optional[str] = None


class ScheduleSubmissionReview(BaseModel):
    status: SubmissionStatus  # APPROVED, REJECTED, NEEDS_CORRECTION
    admin_notes: Optional[str] = None
    # Agar admin tasdiqlayotganda darslar ro'yxatini to'g'irlagan bo'lsa
    approved_schedules: Optional[List[Dict[str, Any]]] = None


class ScheduleSubmissionResponse(BaseModel):
    id: int
    user_id: int
    university_id: int
    faculty_id: Optional[int] = None
    group_id: Optional[int] = None
    image_file_id: str
    image_url: Optional[str] = None
    status: SubmissionStatus
    ai_extracted_json: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_warnings: Optional[str] = None
    admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Reminder Settings ---
class ReminderSettingUpdate(BaseModel):
    is_enabled: bool
    minutes_before: int = 15


class ReminderSettingResponse(BaseModel):
    id: int
    user_id: int
    is_enabled: bool
    minutes_before: int
    model_config = ConfigDict(from_attributes=True)
