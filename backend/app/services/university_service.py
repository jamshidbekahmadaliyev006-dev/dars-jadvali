from difflib import SequenceMatcher
import re
from typing import List, Optional
from sqlalchemy import func, select
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

# Ro'yxatdan o'tishda fakultet so'ralmaydi: yangi guruhlar shu umumiy fakultetga yoziladi
GENERAL_FACULTY_NAME = "Umumiy"

_GROUP_NOISE_WORDS = re.compile(r"\b(guruh|guruhi|gr|group|группа|гр)\b", re.IGNORECASE)


# Bir universitetning boshqa tildagi / boshqa qisqartmadagi nomlari (kalit -> asosiy qisqartma)
UNIVERSITY_ALIASES = {
    "tuit": "tatu", "туит": "tatu", "тату": "tatu",
    "tatumuhammadalxorazmiy": "tatu", "muhammadalxorazmiy": "tatu",
    "ташкентскийуниверситетинформационныхтехнологий": "tatu",
    "tdtu": "tdtu", "тгту": "tdtu",
    "milliyuniversitet": "ozmu", "nuu": "ozmu", "нууз": "ozmu", "узму": "ozmu",
}


def name_key(value: str) -> str:
    """Taqqoslash kaliti: katta-kichik harf, tire, pastki chiziq, bo'shliq va belgilar e'tiborsiz"""
    value = (value or "").lower().replace("ʻ", "'").replace("ʼ", "'").replace("`", "'").replace("‘", "'")
    return "".join(ch for ch in value if ch.isalnum())


def group_key(value: str) -> str:
    """712-24, 712_24, '712 24', '712-24 guruh' - hammasi bir xil kalit beradi"""
    return name_key(_GROUP_NOISE_WORDS.sub(" ", value or ""))


def acronym(value: str) -> str:
    """'Toshkent Axborot Texnologiyalari Universiteti' -> 'tatu'"""
    words = re.findall(r"\w+", (value or "").lower())
    return "".join(w[0] for w in words) if len(words) >= 2 else ""


def pretty_university_name(value: str) -> str:
    """'tatu' / 'Tatu' -> 'TATU'; 'toshkent davlat universiteti' -> 'Toshkent Davlat Universiteti'"""
    words = (value or "").split()
    if len(words) == 1 and len(words[0]) <= 8 and words[0].isalpha():
        return words[0].upper()
    return " ".join(w if any(ch.isupper() for ch in w[1:]) else w[:1].upper() + w[1:] for w in words)


def pretty_faculty_name(value: str) -> str:
    """'kiberxavfsizlik' -> 'Kiberxavfsizlik', 'kx' -> 'KX'"""
    text = " ".join((value or "").split())
    if len(text) <= 4 and text.isalpha():
        return text.upper()
    return text[:1].upper() + text[1:]


def pretty_group_name(value: str) -> str:
    """Yangi guruh nomini bir xil ko'rinishga keltiradi: '712_24' -> '712-24'"""
    cleaned = _GROUP_NOISE_WORDS.sub(" ", value or "").strip()
    cleaned = re.sub(r"[\s_./\\]+", "-", cleaned).strip("-")
    return cleaned.upper() if cleaned else (value or "").strip()


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

    # --- Bot orqali o'z-o'zidan ro'yxatdan o'tish uchun: nom bo'yicha topish/yaratish ---
    @staticmethod
    async def find_university_by_name(session: AsyncSession, name: str) -> Optional[University]:
        stmt = select(University).where(func.lower(University.name) == name.strip().lower())
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def find_faculty_by_name(session: AsyncSession, university_id: int, name: str) -> Optional[Faculty]:
        stmt = select(Faculty).where(Faculty.university_id == university_id, func.lower(Faculty.name) == name.strip().lower())
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def match_university(session: AsyncSession, name: str) -> Optional[University]:
        """
        Talaba yozgan nomni bazadagi universitetga moslaydi: harf/belgi farqlari e'tiborsiz,
        'TATU' kabi qisqartma ham to'liq nomga tushadi. Qisqartma bir nechta universitetga
        mos kelsa, adashib birlashtirmaslik uchun hech biri tanlanmaydi.
        """
        key = name_key(name)
        if not key:
            return None
        key = UNIVERSITY_ALIASES.get(key, key)
        universities = (await session.execute(select(University))).scalars().all()

        for u in universities:
            if key in (name_key(u.name), name_key(u.short_name or "")):
                return u

        # Kichik imlo xatolari: 'univesiteti' / 'texnologiyalar' kabi
        close = [u for u in universities if SequenceMatcher(None, key, name_key(u.name)).ratio() >= 0.9]
        if len(close) == 1:
            return close[0]

        typed_acronym = acronym(name)
        candidates = [
            u for u in universities
            if (acronym(u.name) and acronym(u.name) == key)
            or (typed_acronym and typed_acronym in (name_key(u.name), name_key(u.short_name or "")))
        ]
        return candidates[0] if len(candidates) == 1 else None

    @staticmethod
    async def match_group(session: AsyncSession, university_id: int, name: str) -> Optional[Group]:
        key = group_key(name)
        if not key:
            return None
        groups = (await session.execute(select(Group).where(Group.university_id == university_id))).scalars().all()
        return next((g for g in groups if group_key(g.name) == key), None)

    @staticmethod
    async def match_faculty(session: AsyncSession, university_id: int, name: str) -> Optional[Faculty]:
        """Fakultet: harf/belgi farqi, qisqartma va kichik imlo xatosi ('Kiberxafvsizlik') e'tiborsiz"""
        key = name_key(name)
        if not key:
            return None
        faculties = [
            f for f in (await session.execute(select(Faculty).where(Faculty.university_id == university_id))).scalars().all()
            if f.name != GENERAL_FACULTY_NAME
        ]
        for f in faculties:
            if key in (name_key(f.name), name_key(f.short_name or "")):
                return f
        close = [f for f in faculties if SequenceMatcher(None, key, name_key(f.name)).ratio() >= 0.85]
        if len(close) == 1:
            return close[0]
        by_acronym = [f for f in faculties if acronym(f.name) and acronym(f.name) == key]
        return by_acronym[0] if len(by_acronym) == 1 else None

    @staticmethod
    async def register_university_and_group(
        session: AsyncSession, university_name: str, group_name: str, faculty_name: Optional[str] = None
    ):
        """Universitet, fakultet va guruhni yozilgan nom bo'yicha topadi yoki yaratadi"""
        univ = await UniversityService.match_university(session, university_name)
        if not univ:
            univ = University(name=pretty_university_name(university_name))
            session.add(univ)
            await session.flush()

        faculty = None
        if faculty_name and faculty_name.strip():
            faculty = await UniversityService.match_faculty(session, univ.id, faculty_name)
            if not faculty:
                faculty = Faculty(university_id=univ.id, name=pretty_faculty_name(faculty_name))
                session.add(faculty)
                await session.flush()

        group = await UniversityService.match_group(session, univ.id, group_name)
        if group:
            # Fakultetsiz yozilgan eski guruh - endi talaba aytgan fakultetga o'tkaziladi.
            # Boshqa fakultetda bo'lsa o'zgartirmaymiz: guruhdoshlar jadvali bitta qolsin.
            current = await session.get(Faculty, group.faculty_id)
            if faculty and current and current.name == GENERAL_FACULTY_NAME:
                group.faculty_id = faculty.id
        else:
            if not faculty:
                faculty = await UniversityService.find_faculty_by_name(session, univ.id, GENERAL_FACULTY_NAME)
                if not faculty:
                    faculty = Faculty(university_id=univ.id, name=GENERAL_FACULTY_NAME)
                    session.add(faculty)
                    await session.flush()
            group = Group(university_id=univ.id, faculty_id=faculty.id, name=pretty_group_name(group_name))
            session.add(group)
            await session.flush()

        await session.commit()
        return univ, group

    @staticmethod
    async def get_or_create_university_by_name(session: AsyncSession, name: str) -> University:
        name = name.strip()
        stmt = select(University).where(func.lower(University.name) == name.lower())
        result = await session.execute(stmt)
        univ = result.scalar_one_or_none()
        if univ:
            return univ
        univ = University(name=name)
        session.add(univ)
        await session.commit()
        await session.refresh(univ)
        return univ

    @staticmethod
    async def get_or_create_faculty_by_name(session: AsyncSession, university_id: int, name: str) -> Faculty:
        name = name.strip()
        stmt = select(Faculty).where(Faculty.university_id == university_id, func.lower(Faculty.name) == name.lower())
        result = await session.execute(stmt)
        faculty = result.scalar_one_or_none()
        if faculty:
            return faculty
        faculty = Faculty(university_id=university_id, name=name)
        session.add(faculty)
        await session.commit()
        await session.refresh(faculty)
        return faculty

    @staticmethod
    async def get_or_create_group_by_name(session: AsyncSession, university_id: int, faculty_id: int, name: str) -> Group:
        name = name.strip()
        stmt = select(Group).where(Group.faculty_id == faculty_id, func.lower(Group.name) == name.lower())
        result = await session.execute(stmt)
        group = result.scalar_one_or_none()
        if group:
            return group
        group = Group(university_id=university_id, faculty_id=faculty_id, name=name)
        session.add(group)
        await session.commit()
        await session.refresh(group)
        return group
