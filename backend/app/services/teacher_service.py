import re
from typing import Any, Dict, Iterable, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enums import DayOfWeek, LessonType, TeacherStatus, WeekParity
from app.models.teacher import TeacherLesson, TeacherProfile
from app.models.university import University
from app.services.schedule_service import normalize_subject_name, resolve_day_of_week, resolve_week_parity
from app.services.university_service import UniversityService, pretty_group_name, pretty_university_name


def _clean_room(item: Dict[str, Any]) -> Optional[str]:
    from app.services.schedule_service import clean_room_text

    room = clean_room_text(item.get("room")).lstrip("-–— ").strip()
    building = clean_room_text(item.get("building")).rstrip("-–— ").strip()
    if room and building and not room.lower().startswith(building.lower()):
        room = f"{building}-{room}"
    return room or None


class TeacherService:
    @staticmethod
    async def get_profile(session: AsyncSession, user_id: int) -> Optional[TeacherProfile]:
        stmt = select(TeacherProfile).where(TeacherProfile.user_id == user_id)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def get_approved(session: AsyncSession, user_id: int) -> Optional[TeacherProfile]:
        profile = await TeacherService.get_profile(session, user_id)
        return profile if profile and profile.status == TeacherStatus.APPROVED else None

    @staticmethod
    async def submit_profile(
        session: AsyncSession, user_id: int, university_name: str, full_name: str, department: Optional[str]
    ) -> TeacherProfile:
        """O'qituvchi so'rovini yaratadi yoki yangilaydi (holati PENDING bo'ladi)"""
        univ = await UniversityService.match_university(session, university_name)
        if not univ:
            univ = University(name=pretty_university_name(university_name))
            session.add(univ)
            await session.flush()

        profile = await TeacherService.get_profile(session, user_id)
        if not profile:
            profile = TeacherProfile(user_id=user_id, full_name=full_name.strip())
            session.add(profile)
        profile.full_name = full_name.strip()[:200]
        profile.department = (department or "").strip()[:200] or None
        profile.university_id = univ.id
        profile.status = TeacherStatus.PENDING
        await session.commit()
        await session.refresh(profile)
        return profile

    @staticmethod
    async def set_status(session: AsyncSession, profile_id: int, status: TeacherStatus) -> Optional[TeacherProfile]:
        profile = await session.get(TeacherProfile, profile_id)
        if profile:
            profile.status = status
            await session.commit()
        return profile

    @staticmethod
    async def replace_lessons(session: AsyncSession, teacher_id: int, items: Iterable[Dict[str, Any]]) -> List[TeacherLesson]:
        """Yangi jadval eskisini to'liq almashtiradi; noto'liq qatorlar (kun/vaqt yo'q) tashlanadi"""
        created: List[TeacherLesson] = []
        for item in items:
            day = resolve_day_of_week(item.get("day"))
            start = (item.get("start_time") or "").strip()
            end = (item.get("end_time") or "").strip()
            subject = (item.get("subject") or "").strip()
            if not day or not start or not end or not subject:
                continue
            lesson_type = (item.get("lesson_type") or "OTHER").upper()
            group = (item.get("group") or "").strip()
            created.append(TeacherLesson(
                teacher_id=teacher_id,
                day_of_week=day,
                start_time=start,
                end_time=end,
                subject=normalize_subject_name(subject)[0][:300],
                # Birgalikdagi ma'ruza: "712-24, 732_24" -> "712-24, 732-24"
                group_name=", ".join(pretty_group_name(g) for g in re.split(r"[,;]+", group) if g.strip())[:200] or None,
                room=(_clean_room(item) or None),
                lesson_type=LessonType[lesson_type] if lesson_type in LessonType.__members__ else LessonType.OTHER,
                week_parity=resolve_week_parity(item.get("week_parity")),
            ))

        if created:
            old = await session.execute(
                select(TeacherLesson).where(TeacherLesson.teacher_id == teacher_id, TeacherLesson.is_active == True)
            )
            for lesson in old.scalars().all():
                lesson.is_active = False
            session.add_all(created)
            await session.commit()
        return created

    @staticmethod
    async def get_lessons(
        session: AsyncSession,
        teacher_id: int,
        day_of_week: Optional[DayOfWeek] = None,
        week_parity: Optional[WeekParity] = None,
    ) -> List[TeacherLesson]:
        stmt = select(TeacherLesson).where(TeacherLesson.teacher_id == teacher_id, TeacherLesson.is_active == True)
        if day_of_week:
            stmt = stmt.where(TeacherLesson.day_of_week == day_of_week)
        if week_parity:
            stmt = stmt.where(TeacherLesson.week_parity.in_([WeekParity.ALL, week_parity]))
        lessons = list((await session.execute(stmt)).scalars().all())
        order = list(DayOfWeek)
        lessons.sort(key=lambda l: (order.index(l.day_of_week), l.start_time))
        return lessons
