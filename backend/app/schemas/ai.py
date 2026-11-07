from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class AIStudentAssistantRequest(BaseModel):
    query: str


class AIStudentAssistantResponse(BaseModel):
    answer: str
    action_type: Optional[str] = None  # info, task_suggestion, schedule_view
    data: Optional[Dict[str, Any]] = None


class ExtractedLessonItem(BaseModel):
    day: str  # "Monday", "Dushanba" etc.
    subject: str
    teacher: Optional[str] = None
    start_time: str  # "09:00"
    end_time: str    # "10:20"
    building: Optional[str] = None
    room: Optional[str] = None
    lesson_type: Optional[str] = "LECTURE"


class ExtractedScheduleResult(BaseModel):
    lessons: List[ExtractedLessonItem]
    confidence: float = 0.9
    warnings: Optional[str] = None
    raw_response: Optional[str] = None
