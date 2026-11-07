from datetime import date, datetime, timedelta
import pytest
import pytz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.enums import DayOfWeek, LessonType, NotificationType, UserRole, WeekParity
from app.models.log import NotificationLog
from app.models.schedule import ReminderSetting, Schedule
from app.models.university import Building, Faculty, Group, Room, Subject, University
from app.models.user import User
from app.scheduler import jobs as scheduler_jobs
from tests.conftest import TestingSessionLocal
from app.scheduler.jobs import check_and_send_lesson_reminders
from app.services.schedule_service import resolve_week_parity, week_parity_for


@pytest.mark.parametrize(
    "day, expected",
    [
        (date(2026, 11, 9), WeekParity.ODD),
        (date(2026, 11, 15), WeekParity.ODD),
        (date(2026, 11, 16), WeekParity.EVEN),
        (date(2026, 11, 23), WeekParity.ODD),
        (date(2026, 11, 7), WeekParity.EVEN),
    ],
)
def test_week_parity_counts_from_configured_monday(day, expected):
    assert week_parity_for(day) == expected


def test_unknown_parity_means_every_week():
    assert resolve_week_parity("odd") == WeekParity.ODD
    assert resolve_week_parity(None) == WeekParity.ALL
    assert resolve_week_parity("boshqa") == WeekParity.ALL


@pytest.mark.parametrize("same_week", [True, False])
@pytest.mark.asyncio
async def test_lesson_reminders_job(db_session: AsyncSession, monkeypatch, same_week):
    # Scheduler ishi odatda ishlab chiqarish bazasiga ulanadigan AsyncSessionLocal'dan
    # foydalanadi. Testda esa shu bir xil in-memory test bazasini ishlatishi uchun,
    # modul darajasidagi session factory'ni testning o'ziga moslashtiramiz - aks holda
    # job hali yaratilmagan haqiqiy faylga ulanib, "no such table" xatosi bilan yiqiladi.
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    weekday_idx = now.weekday()
    day_names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    today_enum = DayOfWeek[day_names[weekday_idx]]

    # 10 daqiqadan so'ng boshlanadigan dars vaqti
    start_dt = now + timedelta(minutes=10)
    if start_dt.date() != now.date():
        pytest.skip("Yarim tunga yaqin: dars ertangi kunga o'tib ketadi")
    start_str = start_dt.strftime("%H:%M")
    end_str = (start_dt + timedelta(minutes=80)).strftime("%H:%M")

    current_parity = week_parity_for(now.date())
    other_parity = WeekParity.EVEN if current_parity == WeekParity.ODD else WeekParity.ODD
    lesson_parity = current_parity if same_week else other_parity

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
        week_parity=lesson_parity,
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

    # Sessiya keshi yordam bermasligi uchun tozalaymiz - job real holatdagidek ishlashi kerak
    db_session.expunge_all()

    # Ikki marta ishga tushiramiz: eslatma yuborilishi va takrorlanmasligi kerak
    monkeypatch.setattr(scheduler_jobs, "AsyncSessionLocal", lambda: TestingSessionLocal())
    await check_and_send_lesson_reminders()
    await check_and_send_lesson_reminders()

    async with TestingSessionLocal() as check_session:
        res = await check_session.execute(select(NotificationLog))
        logs = res.scalars().all()
    if not same_week:
        assert logs == []
        return
    assert len(logs) == 1
    assert logs[0].is_success is True
    assert "Web Dasturlash" in logs[0].body
