import enum


class UserRole(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class SubmissionStatus(str, enum.Enum):
    PENDING = "PENDING"
    AI_PROCESSING = "AI_PROCESSING"
    AI_COMPLETED = "AI_COMPLETED"
    ADMIN_REVIEW = "ADMIN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_CORRECTION = "NEEDS_CORRECTION"


class DayOfWeek(str, enum.Enum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


class WeekParity(str, enum.Enum):
    ALL = "ALL"
    ODD = "ODD"
    EVEN = "EVEN"


class TaskPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class LessonType(str, enum.Enum):
    LECTURE = "LECTURE"
    PRACTICE = "PRACTICE"
    LAB = "LAB"
    SEMINAR = "SEMINAR"
    OTHER = "OTHER"


class NotificationType(str, enum.Enum):
    LESSON_REMINDER = "LESSON_REMINDER"
    TASK_REMINDER = "TASK_REMINDER"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    SYSTEM = "SYSTEM"
