from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AnnouncementBase(BaseModel):
    title: str
    content: str
    university_id: int
    target_group_id: Optional[int] = None
    is_pinned: bool = False


class AnnouncementCreate(AnnouncementBase):
    pass


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    is_pinned: Optional[bool] = None
    target_group_id: Optional[int] = None


class AnnouncementResponse(AnnouncementBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
