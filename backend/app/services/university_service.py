from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.university import Building, Faculty, Group, Room, Subject, Teacher, University
from app.schemas.university import (
    BuildingCreate, BuildingUpdate,
    FacultyCreate, FacultyUpdate,
    GroupCreate, GroupUpdate,
    RoomCreate, RoomUpdate,
    SubjectCreate, SubjectUpdate,
    TeacherCreate, TeacherUpdate,
    UniversityCreate, UniversityUpdate,
)


class UniversityService:
    # --- University ---
    @staticmethod
    async def get_all_universities(session: AsyncSession, only_active: bool = True) -> List[University]:
        stmt = select(University)
        if only_active:
            stmt = stmt.where(University.is_active == True)
        stmt = stmt.order_by(University.name.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_university_by_id(session: AsyncSession, university_id: int) -> Optional[University]:
        stmt = select(University).where(University.id == university_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_university(session: AsyncSession, payload: UniversityCreate) -> University:
        univ = University(**payload.model_dump())
        session.add(univ)
        await session.commit()
        await session.refresh(univ)
        return univ

    @staticmethod
    async def update_university(session: AsyncSession, university_id: int, payload: UniversityUpdate) -> Optional[University]:
        univ = await UniversityService.get_university_by_id(session, university_id)
        if not univ:
            return None
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(univ, k, v)
        await session.commit()
        await session.refresh(univ)
        return univ

    @staticmethod
    async def delete_university(session: AsyncSession, university_id: int) -> bool:
        univ = await UniversityService.get_university_by_id(session, university_id)
        if not univ:
            return False
        await session.delete(univ)
        await session.commit()
        return True

    # --- Faculty ---
    @staticmethod
    async def get_faculties_by_university(session: AsyncSession, university_id: int) -> List[Faculty]:
        stmt = select(Faculty).where(Faculty.university_id == university_id, Faculty.is_active == True).order_by(Faculty.name.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_faculty(session: AsyncSession, payload: FacultyCreate) -> Faculty:
        faculty = Faculty(**payload.model_dump())
        session.add(faculty)
        await session.commit()
        await session.refresh(faculty)
        return faculty

    # --- Group ---
    @staticmethod
    async def get_groups(session: AsyncSession, university_id: int, faculty_id: Optional[int] = None) -> List[Group]:
        stmt = select(Group).where(Group.university_id == university_id, Group.is_active == True)
        if faculty_id:
            stmt = stmt.where(Group.faculty_id == faculty_id)
        stmt = stmt.order_by(Group.name.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_group_by_id(session: AsyncSession, group_id: int) -> Optional[Group]:
        stmt = select(Group).where(Group.id == group_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_group(session: AsyncSession, payload: GroupCreate) -> Group:
        group = Group(**payload.model_dump())
        session.add(group)
        await session.commit()
        await session.refresh(group)
        return group

    # --- Building & Room ---
    @staticmethod
    async def get_buildings(session: AsyncSession, university_id: int) -> List[Building]:
        stmt = select(Building).where(Building.university_id == university_id, Building.is_active == True)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_building(session: AsyncSession, payload: BuildingCreate) -> Building:
        building = Building(**payload.model_dump())
        session.add(building)
        await session.commit()
        await session.refresh(building)
        return building

    @staticmethod
    async def get_rooms(session: AsyncSession, building_id: int) -> List[Room]:
        stmt = select(Room).where(Room.building_id == building_id, Room.is_active == True).order_by(Room.number.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_room(session: AsyncSession, payload: RoomCreate) -> Room:
        room = Room(**payload.model_dump())
        session.add(room)
        await session.commit()
        await session.refresh(room)
        return room

    # --- Subject & Teacher ---
    @staticmethod
    async def get_subjects(session: AsyncSession, university_id: int) -> List[Subject]:
        stmt = select(Subject).where(Subject.university_id == university_id, Subject.is_active == True)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_subject(session: AsyncSession, payload: SubjectCreate) -> Subject:
        subject = Subject(**payload.model_dump())
        session.add(subject)
        await session.commit()
        await session.refresh(subject)
        return subject

    @staticmethod
    async def get_teachers(session: AsyncSession, university_id: int) -> List[Teacher]:
        stmt = select(Teacher).where(Teacher.university_id == university_id, Teacher.is_active == True)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_teacher(session: AsyncSession, payload: TeacherCreate) -> Teacher:
        teacher = Teacher(**payload.model_dump())
        session.add(teacher)
        await session.commit()
        await session.refresh(teacher)
        return teacher
