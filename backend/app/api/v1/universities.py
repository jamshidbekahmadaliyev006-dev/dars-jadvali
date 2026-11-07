from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.university import (
    BuildingCreate, BuildingResponse, BuildingUpdate,
    FacultyCreate, FacultyResponse, FacultyUpdate,
    GroupCreate, GroupResponse, GroupUpdate,
    RoomCreate, RoomResponse, RoomUpdate,
    SubjectCreate, SubjectResponse, SubjectUpdate,
    TeacherCreate, TeacherResponse, TeacherUpdate,
    UniversityCreate, UniversityResponse, UniversityUpdate,
)
from app.services.university_service import UniversityService

router = APIRouter(tags=["Universities & Academic Structures"])


# --- Universities ---
@router.get("/universities", response_model=List[UniversityResponse])
async def get_universities(
    session: AsyncSession = Depends(get_db),
):
    return await UniversityService.get_all_universities(session)


@router.post("/universities", response_model=UniversityResponse, status_code=status.HTTP_201_CREATED)
async def create_university(
    payload: UniversityCreate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await UniversityService.create_university(session, payload)


@router.put("/universities/{university_id}", response_model=UniversityResponse)
async def update_university(
    university_id: int,
    payload: UniversityUpdate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    univ = await UniversityService.update_university(session, university_id, payload)
    if not univ:
        raise HTTPException(status_code=404, detail="Universitet topilmadi")
    return univ


@router.delete("/universities/{university_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_university(
    university_id: int,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    ok = await UniversityService.delete_university(session, university_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Universitet topilmadi")
    return None


# --- Faculties ---
@router.get("/faculties", response_model=List[FacultyResponse])
async def get_faculties(
    university_id: int = Query(...),
    session: AsyncSession = Depends(get_db),
):
    return await UniversityService.get_faculties_by_university(session, university_id)


@router.post("/faculties", response_model=FacultyResponse, status_code=status.HTTP_201_CREATED)
async def create_faculty(
    payload: FacultyCreate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await UniversityService.create_faculty(session, payload)


# --- Groups ---
@router.get("/groups", response_model=List[GroupResponse])
async def get_groups(
    university_id: int = Query(...),
    faculty_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    return await UniversityService.get_groups(session, university_id, faculty_id)


@router.post("/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await UniversityService.create_group(session, payload)


# --- Buildings & Rooms ---
@router.get("/buildings", response_model=List[BuildingResponse])
async def get_buildings(
    university_id: int = Query(...),
    session: AsyncSession = Depends(get_db),
):
    return await UniversityService.get_buildings(session, university_id)


@router.post("/buildings", response_model=BuildingResponse, status_code=status.HTTP_201_CREATED)
async def create_building(
    payload: BuildingCreate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await UniversityService.create_building(session, payload)


@router.get("/rooms", response_model=List[RoomResponse])
async def get_rooms(
    building_id: int = Query(...),
    session: AsyncSession = Depends(get_db),
):
    return await UniversityService.get_rooms(session, building_id)


@router.post("/rooms", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    payload: RoomCreate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await UniversityService.create_room(session, payload)


# --- Subjects & Teachers ---
@router.get("/subjects", response_model=List[SubjectResponse])
async def get_subjects(
    university_id: int = Query(...),
    session: AsyncSession = Depends(get_db),
):
    return await UniversityService.get_subjects(session, university_id)


@router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    payload: SubjectCreate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await UniversityService.create_subject(session, payload)


@router.get("/teachers", response_model=List[TeacherResponse])
async def get_teachers(
    university_id: int = Query(...),
    session: AsyncSession = Depends(get_db),
):
    return await UniversityService.get_teachers(session, university_id)


@router.post("/teachers", response_model=TeacherResponse, status_code=status.HTTP_201_CREATED)
async def create_teacher(
    payload: TeacherCreate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await UniversityService.create_teacher(session, payload)
