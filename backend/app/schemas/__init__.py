from app.schemas.user import UserBase, UserCreate, UserUpdate, UserResponse, UserRoleUpdate
from app.schemas.auth import TelegramAuthRequest, TokenResponse, TokenPayload
from app.schemas.response import StandardResponse, HealthResponse
from app.schemas.university import (
    UniversityCreate, UniversityUpdate, UniversityResponse,
    FacultyCreate, FacultyUpdate, FacultyResponse,
    GroupCreate, GroupUpdate, GroupResponse,
    BuildingCreate, BuildingUpdate, BuildingResponse,
    RoomCreate, RoomUpdate, RoomResponse,
    SubjectCreate, SubjectUpdate, SubjectResponse,
    TeacherCreate, TeacherUpdate, TeacherResponse,
)
from app.schemas.schedule import (
    ScheduleCreate, ScheduleUpdate, ScheduleResponse, ScheduleDetailResponse,
    ScheduleSubmissionCreate, ScheduleSubmissionReview, ScheduleSubmissionResponse,
    ReminderSettingUpdate, ReminderSettingResponse,
)
from app.schemas.task import (
    PersonalTaskCreate, PersonalTaskUpdate, PersonalTaskResponse,
    PersonalEventCreate, PersonalEventUpdate, PersonalEventResponse,
)
from app.schemas.announcement import (
    AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse,
)
from app.schemas.ai import (
    AIStudentAssistantRequest, AIStudentAssistantResponse,
    ExtractedLessonItem, ExtractedScheduleResult,
)

__all__ = [
    "UserBase", "UserCreate", "UserUpdate", "UserResponse", "UserRoleUpdate",
    "TelegramAuthRequest", "TokenResponse", "TokenPayload",
    "StandardResponse", "HealthResponse",
    "UniversityCreate", "UniversityUpdate", "UniversityResponse",
    "FacultyCreate", "FacultyUpdate", "FacultyResponse",
    "GroupCreate", "GroupUpdate", "GroupResponse",
    "BuildingCreate", "BuildingUpdate", "BuildingResponse",
    "RoomCreate", "RoomUpdate", "RoomResponse",
    "SubjectCreate", "SubjectUpdate", "SubjectResponse",
    "TeacherCreate", "TeacherUpdate", "TeacherResponse",
    "ScheduleCreate", "ScheduleUpdate", "ScheduleResponse", "ScheduleDetailResponse",
    "ScheduleSubmissionCreate", "ScheduleSubmissionReview", "ScheduleSubmissionResponse",
    "ReminderSettingUpdate", "ReminderSettingResponse",
    "PersonalTaskCreate", "PersonalTaskUpdate", "PersonalTaskResponse",
    "PersonalEventCreate", "PersonalEventUpdate", "PersonalEventResponse",
    "AnnouncementCreate", "AnnouncementUpdate", "AnnouncementResponse",
    "AIStudentAssistantRequest", "AIStudentAssistantResponse",
    "ExtractedLessonItem", "ExtractedScheduleResult",
]
