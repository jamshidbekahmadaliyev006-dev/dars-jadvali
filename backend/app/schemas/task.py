from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.enums import TaskPriority


class PersonalTaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None
    is_completed: bool = False


class PersonalTaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None


class PersonalTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[datetime] = None
    is_completed: Optional[bool] = None


class PersonalTaskResponse(PersonalTaskBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Personal Event (Calendar) ---
class PersonalEventBase(BaseModel):
    title: str
    event_type: str = "exam"  # exam, deadline, homework, meeting, other
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None


class PersonalEventCreate(PersonalEventBase):
    pass


class PersonalEventUpdate(BaseModel):
    title: Optional[str] = None
    event_type: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class PersonalEventResponse(PersonalEventBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
