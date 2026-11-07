from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


# --- University ---
class UniversityBase(BaseModel):
    name: str
    short_name: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True


class UniversityCreate(UniversityBase):
    pass


class UniversityUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class UniversityResponse(UniversityBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Faculty ---
class FacultyBase(BaseModel):
    name: str
    short_name: Optional[str] = None
    university_id: int
    is_active: bool = True


class FacultyCreate(FacultyBase):
    pass


class FacultyUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    is_active: Optional[bool] = None


class FacultyResponse(FacultyBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Group ---
class GroupBase(BaseModel):
    name: str
    university_id: int
    faculty_id: int
    course_number: Optional[int] = 1
    field_of_study: Optional[str] = None
    is_active: bool = True


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    course_number: Optional[int] = None
    field_of_study: Optional[str] = None
    is_active: Optional[bool] = None


class GroupResponse(GroupBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Building ---
class BuildingBase(BaseModel):
    name: str
    university_id: int
    address: Optional[str] = None
    description: Optional[str] = None
    floors_count: Optional[int] = None
    is_active: bool = True


class BuildingCreate(BuildingBase):
    pass


class BuildingUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    floors_count: Optional[int] = None
    is_active: Optional[bool] = None


class BuildingResponse(BuildingBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Room ---
class RoomBase(BaseModel):
    number: str
    building_id: int
    floor: Optional[int] = None
    capacity: Optional[int] = None
    room_type: str = "lecture"
    is_active: bool = True


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    number: Optional[str] = None
    floor: Optional[int] = None
    capacity: Optional[int] = None
    room_type: Optional[str] = None
    is_active: Optional[bool] = None


class RoomResponse(RoomBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Subject ---
class SubjectBase(BaseModel):
    name: str
    university_id: int
    code: Optional[str] = None
    is_active: bool = True


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    is_active: Optional[bool] = None


class SubjectResponse(SubjectBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Teacher ---
class TeacherBase(BaseModel):
    full_name: str
    university_id: int
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True


class TeacherCreate(TeacherBase):
    pass


class TeacherUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class TeacherResponse(TeacherBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
