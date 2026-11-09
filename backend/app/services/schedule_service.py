from datetime import date, datetime, timedelta
import json
import re
from typing import Any, Dict, List, Optional, Tuple
import pytz
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.config import settings
from app.core.logging import logger
from app.models.enums import DayOfWeek, LessonType, SubmissionStatus, WeekParity
from app.models.schedule import ReminderSetting, Schedule, ScheduleSubmission
from app.models.university import Building, Room, Subject, Teacher
from app.schemas.schedule import ReminderSettingUpdate, ScheduleCreate, ScheduleSubmissionCreate, ScheduleSubmissionReview, ScheduleUpdate

# AI OCR dars jadvalidan qaytargan kun nomlarini (o'zbek/rus/ingliz) DayOfWeek enumiga bog'lash
DAY_NAME_MAP: Dict[str, DayOfWeek] = {
    # O'zbekcha
    "dushanba": DayOfWeek.MONDAY,
    "seshanba": DayOfWeek.TUESDAY,
    "chorshanba": DayOfWeek.WEDNESDAY,
    "payshanba": DayOfWeek.THURSDAY,
    "juma": DayOfWeek.FRIDAY,
    "shanba": DayOfWeek.SATURDAY,
    "yakshanba": DayOfWeek.SUNDAY,
    # Inglizcha
    "monday": DayOfWeek.MONDAY,
    "tuesday": DayOfWeek.TUESDAY,
    "wednesday": DayOfWeek.WEDNESDAY,
    "thursday": DayOfWeek.THURSDAY,
    "friday": DayOfWeek.FRIDAY,
    "saturday": DayOfWeek.SATURDAY,
    "sunday": DayOfWeek.SUNDAY,
    # Ruscha (ko'p jadvallarda uchraydi)
    "понедельник": DayOfWeek.MONDAY,
    "вторник": DayOfWeek.TUESDAY,
    "среда": DayOfWeek.WEDNESDAY,
    "четверг": DayOfWeek.THURSDAY,
    "пятница": DayOfWeek.FRIDAY,
    "суббота": DayOfWeek.SATURDAY,
    "воскресенье": DayOfWeek.SUNDAY,
}


# Kun tugmalari tez almashishi uchun tayyor matnlar keshi: (guruh, til, kun, hafta turi) -> (vaqt, matn).
# Jadval tasdiqlanganda (review_submission) to'liq tozalanadi.
SCHEDULE_VIEW_CACHE: Dict[tuple, tuple] = {}
SCHEDULE_VIEW_TTL_SECONDS = 120


def resolve_day_of_week(raw: Optional[str]) -> Optional[DayOfWeek]:
    """AI tomonidan qaytarilgan erkin matndagi kun nomini DayOfWeek enumiga aylantirish"""
    if not raw:
        return None
    key = raw.strip().lower()
    if key in DAY_NAME_MAP:
        return DAY_NAME_MAP[key]
    upper = raw.strip().upper()
    if upper in DayOfWeek.__members__:
        return DayOfWeek[upper]
    return None


_SUBJECT_CODE_RE = re.compile(r"[\s/\-–]*\b([A-Z]{2,}\d{2,})(?:-\d+)?\s*$")


def normalize_subject_name(raw: str) -> Tuple[str, Optional[str]]:
    """
    Jadvaldagi yozuvdan toza fan nomi va kodini ajratadi. Bir fan ma'ruza, amaliyot va
    guruh bo'yicha turlicha yoziladi, masalan "Axborot xavfsizligi auditi (4 kr)-INS001"
    va "...-INS001-3": ikkalasi ham bitta fan.
    """
    text = (raw or "").strip()
    code = None
    match = _SUBJECT_CODE_RE.search(text)
    if match:
        code = match.group(1)
        text = text[:match.start()]
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" /-–,.")
    return (text or (raw or "").strip()), code


def current_local_date() -> date:
    return datetime.now(pytz.timezone(settings.TIMEZONE)).date()


def week_parity_for(day: date) -> WeekParity:
    """Berilgan sana universitet hisobida toq yoki juft haftaga tushishini aniqlaydi"""
    anchor = settings.WEEK_PARITY_ODD_MONDAY
    anchor_monday = anchor - timedelta(days=anchor.weekday())
    day_monday = day - timedelta(days=day.weekday())
    weeks_apart = (day_monday - anchor_monday).days // 7
    return WeekParity.ODD if weeks_apart % 2 == 0 else WeekParity.EVEN


def resolve_week_parity(raw: Optional[str]) -> WeekParity:
    """AI qaytargan belgini WeekParity'ga aylantiradi; noma'lum qiymat har hafta deb olinadi"""
    key = (raw or "").strip().upper()
    return WeekParity[key] if key in WeekParity.__members__ else WeekParity.ALL


class ScheduleService:
    @staticmethod
    async def get_schedules(
        session: AsyncSession,
        group_id: Optional[int] = None,
        university_id: Optional[int] = None,
        day_of_week: Optional[DayOfWeek] = None,
        week_parity: Optional[WeekParity] = None,
    ) -> List[Schedule]:
        stmt = (
            select(Schedule)
            .options(
                selectinload(Schedule.subject),
                selectinload(Schedule.teacher),
                selectinload(Schedule.room),
                selectinload(Schedule.group),
            )
            .where(Schedule.is_active == True)
        )
        if group_id:
            stmt = stmt.where(Schedule.group_id == group_id)
        if university_id:
            stmt = stmt.where(Schedule.university_id == university_id)
        if day_of_week:
            stmt = stmt.where(Schedule.day_of_week == day_of_week)
        if week_parity:
            stmt = stmt.where(Schedule.week_parity.in_([WeekParity.ALL, week_parity]))

        stmt = stmt.order_by(Schedule.day_of_week.asc(), Schedule.start_time.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_schedule_by_id(session: AsyncSession, schedule_id: int) -> Optional[Schedule]:
        stmt = (
            select(Schedule)
            .options(
                selectinload(Schedule.subject),
                selectinload(Schedule.teacher),
                selectinload(Schedule.room),
                selectinload(Schedule.group),
            )
            .where(Schedule.id == schedule_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_schedule(session: AsyncSession, payload: ScheduleCreate) -> Schedule:
        schedule = Schedule(**payload.model_dump())
        session.add(schedule)
        await session.commit()
        await session.refresh(schedule)
        return schedule

    @staticmethod
    async def update_schedule(session: AsyncSession, schedule_id: int, payload: ScheduleUpdate) -> Optional[Schedule]:
        sched = await ScheduleService.get_schedule_by_id(session, schedule_id)
        if not sched:
            return None
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(sched, k, v)
        await session.commit()
        await session.refresh(sched)
        return sched

    @staticmethod
    async def delete_schedule(session: AsyncSession, schedule_id: int) -> bool:
        sched = await ScheduleService.get_schedule_by_id(session, schedule_id)
        if not sched:
            return False
        await session.delete(sched)
        await session.commit()
        return True

    # --- Reminder Settings ---
    @staticmethod
    async def get_or_create_reminder_setting(session: AsyncSession, user_id: int) -> ReminderSetting:
        stmt = select(ReminderSetting).where(ReminderSetting.user_id == user_id)
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        if not setting:
            setting = ReminderSetting(user_id=user_id, is_enabled=True, minutes_before=15)
            session.add(setting)
            await session.commit()
            await session.refresh(setting)
        return setting

    @staticmethod
    async def update_reminder_setting(session: AsyncSession, user_id: int, payload: ReminderSettingUpdate) -> ReminderSetting:
        setting = await ScheduleService.get_or_create_reminder_setting(session, user_id)
        setting.is_enabled = payload.is_enabled
        setting.minutes_before = payload.minutes_before
        await session.commit()
        await session.refresh(setting)
        return setting

    # --- Submissions (Workflow) ---
    @staticmethod
    async def create_submission(session: AsyncSession, user_id: int, payload: ScheduleSubmissionCreate) -> ScheduleSubmission:
        submission = ScheduleSubmission(
            user_id=user_id,
            university_id=payload.university_id,
            faculty_id=payload.faculty_id,
            group_id=payload.group_id,
            image_file_id=payload.image_file_id,
            image_url=payload.image_url,
            status=SubmissionStatus.PENDING,
        )
        session.add(submission)
        await session.commit()
        await session.refresh(submission)
        return submission

    @staticmethod
    async def list_submissions(
        session: AsyncSession,
        status: Optional[SubmissionStatus] = None,
        university_id: Optional[int] = None,
    ) -> List[ScheduleSubmission]:
        stmt = select(ScheduleSubmission)
        if status:
            stmt = stmt.where(ScheduleSubmission.status == status)
        if university_id:
            stmt = stmt.where(ScheduleSubmission.university_id == university_id)
        stmt = stmt.order_by(ScheduleSubmission.id.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_submission_by_id(session: AsyncSession, submission_id: int) -> Optional[ScheduleSubmission]:
        stmt = select(ScheduleSubmission).where(ScheduleSubmission.id == submission_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def review_submission(
        session: AsyncSession,
        submission_id: int,
        reviewer_id: int,
        review: ScheduleSubmissionReview,
    ) -> Optional[ScheduleSubmission]:
        submission = await ScheduleService.get_submission_by_id(session, submission_id)
        if not submission:
            return None

        SCHEDULE_VIEW_CACHE.clear()  # jadval o'zgarishi mumkin - tayyor ko'rinishlar eskiradi
        submission.status = review.status
        submission.reviewer_id = reviewer_id
        submission.admin_notes = review.admin_notes
        await session.commit()

        if review.status == SubmissionStatus.APPROVED:
            if not submission.group_id:
                submission.admin_notes = (
                    f"{review.admin_notes or ''}\n"
                    "⚠️ Tasdiqlandi, lekin guruh biriktirilmagani uchun darslar jadvalga qo'shilmadi."
                ).strip()
                await session.commit()
            elif review.approved_schedules:
                # Admin tomonidan aniq ID lar bilan qo'lda tuzatilgan darslar ro'yxati
                for item in review.approved_schedules:
                    day_str = item.get("day_of_week", "MONDAY").upper()
                    day_enum = DayOfWeek[day_str] if day_str in DayOfWeek.__members__ else DayOfWeek.MONDAY
                    lesson_type_str = item.get("lesson_type", "LECTURE").upper()
                    lesson_type_enum = LessonType[lesson_type_str] if lesson_type_str in LessonType.__members__ else LessonType.LECTURE

                    sched = Schedule(
                        university_id=submission.university_id,
                        group_id=submission.group_id,
                        subject_id=item["subject_id"],
                        teacher_id=item.get("teacher_id"),
                        room_id=item.get("room_id"),
                        day_of_week=day_enum,
                        start_time=item["start_time"],
                        end_time=item["end_time"],
                        lesson_type=lesson_type_enum,
                        week_parity=resolve_week_parity(item.get("week_parity")),
                    )
                    session.add(sched)
                await session.commit()
            elif submission.ai_extracted_json:
                # Admin hech qanday qo'lda tuzatish bermadi - AI natijasini avtomatik
                # fan/o'qituvchi/xona nomlari orqali bazaga bog'lab, jadvalni faollashtiramiz
                try:
                    created = await ScheduleService.resolve_and_create_schedules_from_extraction(session, submission)
                    if not created:
                        submission.admin_notes = (
                            f"{review.admin_notes or ''}\n"
                            "⚠️ Tasdiqlandi, lekin AI natijasidan birorta ham dars avtomatik aniqlanmadi."
                        ).strip()
                        await session.commit()
                except Exception as e:
                    logger.error(f"Auto-resolve schedules failed for submission {submission.id}: {e}")
                    submission.admin_notes = (
                        f"{review.admin_notes or ''}\n"
                        f"⚠️ Tasdiqlandi, lekin darslarni avtomatik yaratishda xatolik: {e}"
                    ).strip()
                    await session.commit()

        # Qaror qabul qilindi: rasmga havola endi kerak emas (rasm Telegram'da turadi, bizda faqat nom).
        # Kerakli ma'lumot - darslar - "schedules" jadvalida saqlangan.
        if submission.status in (SubmissionStatus.APPROVED, SubmissionStatus.REJECTED):
            submission.image_file_id = "-"
            submission.image_url = None
            await session.commit()

        await session.refresh(submission)
        return submission

    # --- AI OCR natijasini real DB yozuvlariga avtomatik bog'lash ---
    @staticmethod
    async def _get_or_create_subject(
        session: AsyncSession,
        university_id: int,
        name: str,
        code: Optional[str] = None,
    ) -> Subject:
        stmt = select(Subject).where(Subject.university_id == university_id, func.lower(Subject.name) == name.lower())
        result = await session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj:
            return obj
        obj = Subject(university_id=university_id, name=name, code=code)
        session.add(obj)
        await session.flush()
        return obj

    @staticmethod
    async def _get_or_create_teacher(session: AsyncSession, university_id: int, full_name: str) -> Teacher:
        stmt = select(Teacher).where(Teacher.university_id == university_id, func.lower(Teacher.full_name) == full_name.lower())
        result = await session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj:
            return obj
        obj = Teacher(university_id=university_id, full_name=full_name)
        session.add(obj)
        await session.flush()
        return obj

    @staticmethod
    async def _get_or_create_building(session: AsyncSession, university_id: int, name: str) -> Building:
        stmt = select(Building).where(Building.university_id == university_id, func.lower(Building.name) == name.lower())
        result = await session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj:
            return obj
        obj = Building(university_id=university_id, name=name)
        session.add(obj)
        await session.flush()
        return obj

    @staticmethod
    async def _get_or_create_room(session: AsyncSession, building_id: int, number: str) -> Room:
        stmt = select(Room).where(Room.building_id == building_id, func.lower(Room.number) == number.lower())
        result = await session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj:
            return obj
        obj = Room(building_id=building_id, number=number)
        session.add(obj)
        await session.flush()
        return obj

    @staticmethod
    async def resolve_and_create_schedules_from_extraction(
        session: AsyncSession,
        submission: ScheduleSubmission,
    ) -> List[Schedule]:
        """
        AI OCR orqali ajratilgan (matn ko'rinishidagi fan/o'qituvchi/bino/xona nomlari bilan)
        darslar ro'yxatini tizimdagi haqiqiy yozuvlarga bog'lab (topilmasa avtomatik yaratib),
        guruh uchun tasdiqlangan Schedule qatorlarini hosil qiladi.
        """
        if not submission.group_id:
            raise ValueError("Guruh biriktirilmagan")
        if not submission.ai_extracted_json:
            raise ValueError("AI tahlil natijasi topilmadi")

        try:
            lessons = json.loads(submission.ai_extracted_json)
        except Exception as e:
            raise ValueError(f"AI natijasini o'qishda xatolik: {e}")

        created: List[Schedule] = []
        for item in lessons:
            day_enum = resolve_day_of_week(item.get("day"))
            subject_name = (item.get("subject") or "").strip()
            start_time = (item.get("start_time") or "").strip()
            end_time = (item.get("end_time") or "").strip()

            if not day_enum or not subject_name or not start_time or not end_time:
                # Noto'liq yoki tanilmagan qator - xavfsiz tarzda o'tkazib yuboramiz
                continue

            clean_name, subject_code = normalize_subject_name(subject_name)
            subject = await ScheduleService._get_or_create_subject(
                session, submission.university_id, clean_name, subject_code
            )

            teacher = None
            teacher_name = (item.get("teacher") or "").strip()
            if teacher_name:
                teacher = await ScheduleService._get_or_create_teacher(session, submission.university_id, teacher_name)

            room = None
            room_number = (item.get("room") or "").strip().strip("()").lstrip("-–— ").strip()
            building_label = (item.get("building") or "").strip().strip("()").rstrip("-–— ").strip()
            if room_number and building_label and not room_number.lower().startswith(building_label.lower()):
                # Talabaga ko'rinadigan xona yozuvi binoni ham o'z ichiga olsin: "A-327"
                room_number = f"{building_label}-{room_number}"
            if room_number:
                building_name = building_label or "Bosh bino"
                building = await ScheduleService._get_or_create_building(session, submission.university_id, building_name)
                room = await ScheduleService._get_or_create_room(session, building.id, room_number)

            lesson_type_str = (item.get("lesson_type") or "LECTURE").upper()
            lesson_type_enum = LessonType[lesson_type_str] if lesson_type_str in LessonType.__members__ else LessonType.LECTURE

            week_parity = resolve_week_parity(item.get("week_parity"))

            # Bir xil guruh/fan/kun/vaqt uchun qator allaqachon mavjudmi - tekshirib, bo'lsa
            # UNI YANGILAYMIZ (qayta-qayta screenshot yuborilganda darslar ko'payib ketmasligi
            # uchun), aks holda yangi qator yaratamiz
            dup_stmt = select(Schedule).where(
                Schedule.group_id == submission.group_id,
                Schedule.subject_id == subject.id,
                Schedule.day_of_week == day_enum,
                Schedule.start_time == start_time,
                Schedule.week_parity == week_parity,
            )
            dup_result = await session.execute(dup_stmt)
            sched = dup_result.scalars().first()

            if sched:
                sched.teacher_id = teacher.id if teacher else sched.teacher_id
                sched.room_id = room.id if room else sched.room_id
                sched.end_time = end_time
                sched.lesson_type = lesson_type_enum
                sched.is_active = True
            else:
                sched = Schedule(
                    university_id=submission.university_id,
                    group_id=submission.group_id,
                    subject_id=subject.id,
                    teacher_id=teacher.id if teacher else None,
                    room_id=room.id if room else None,
                    day_of_week=day_enum,
                    start_time=start_time,
                    end_time=end_time,
                    lesson_type=lesson_type_enum,
                    week_parity=week_parity,
                )
                session.add(sched)
            created.append(sched)

        # Yangi jadval eskisini to'liq almashtiradi, aks holda eski darslarga eslatma ketaveradi
        if created:
            await session.flush()
            kept_ids = {s.id for s in created}
            old_stmt = select(Schedule).where(Schedule.group_id == submission.group_id, Schedule.is_active == True)
            for old in (await session.execute(old_stmt)).scalars().all():
                if old.id not in kept_ids:
                    old.is_active = False

        await session.commit()
        for s in created:
            await session.refresh(s)
        return created
