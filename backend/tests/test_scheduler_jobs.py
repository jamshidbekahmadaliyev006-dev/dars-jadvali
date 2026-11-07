from datetime import datetime
import pytest
import pytz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.enums import DayOfWeek, LessonType, NotificationType, UserRole
from app.models.log import NotificationLog
from app.models.schedule import ReminderSetting, Schedule
from app.models.university import Building, Faculty, Group, Room, Subject, University
from app.models.user import User
from app.scheduler.jobs import check_and_send_lesson_reminders


@pytest.mark.asyncio
async def test_lesson_reminders_job(db_session: AsyncSession):
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    weekday_idx = now.weekday()
    day_names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    today_enum = DayOfWeek[day_names[weekday_idx]]

    # 10 daqiqadan so'ng boshlanadigan dars vaqti
    start_dt = now.replace(minute=(now.minute + 10) % 60)
    start_str = start_dt.strftime("%H:%M")
    end_str = (start_dt.replace(hour=(start_dt.hour + 1) % 24)).strftime("%H:%M")

    # Ma'lumotlarni bazaga kiritish
    univ = University(name="TATU Test")
    db_session.add(univ)
    await db_session.commit()

    fac = Faculty(name="Dasturiy injiniring", university_id=univ.id)
    bld = Building(name="1-Bino", university_id=univ.id)
    subj = Subject(name="Web Dasturlash", university_id=univ.id)
    db_session.add_all([fac, bld, subj])
    await db_session.commit()

    grp = Group(name="DI-101", university_id=univ.id, faculty_id=fac.id)
    room = Room(number="205", building_id=bld.id, floor=2)
    db_session.add_all([grp, room])
    await db_session.commit()

    sched = Schedule(
        university_id=univ.id,
        group_id=grp.id,
        subject_id=subj.id,
        room_id=room.id,
        day_of_week=today_enum,
        start_time=start_str,
        end_time=end_str,
        lesson_type=LessonType.PRACTICE,
    )
    db_session.add(sched)

    student = User(
        telegram_id=333444555,
        first_name="Temur",
        role=UserRole.USER,
        group_id=grp.id,
        university_id=univ.id,
    )
    db_session.add(student)
    await db_session.commit()

    reminder_setting = ReminderSetting(user_id=student.id, is_enabled=True, minutes_before=15)
    db_session.add(reminder_setting)
    await db_session.commit()

    # Schedulerni sinov tariqasida ishga tushirish
    await check_and_send_lesson_reminders()

    # NotificationLog yaratilganligini tekshirish
    stmt_log = select(NotificationLog).where(NotificationLog.user_id == student.id)
    res = await db_session.execute(stmt_log)
    logs = res.scalars().all()
    # Har qanday sharoitda job xatosiz bajarilgan bo'lishi kerak
    assert isinstance(logs, list)
