"""Fan kodi (BGH001-3, KSL001, PHY018-L2) jadvalda fan nomi oldida to'liq ko'rinadi"""
import json
from types import SimpleNamespace as NS

import pytest
from sqlalchemy import select

from app.bot.text_utils import _lesson_line, format_reminder, format_teacher_reminder, _teacher_line, subject_label
from app.models.enums import DayOfWeek, SubmissionStatus, WeekParity
from app.models.schedule import Schedule, ScheduleSubmission
from app.models.university import Faculty, Group, University
from app.models.user import User
from app.services.schedule_service import ScheduleService, normalize_subject_name, split_subject_code


@pytest.mark.parametrize("raw, name, base, full", [
    ("Fizika 1 (6 kr)-PHY018", "Fizika 1", "PHY018", "PHY018"),
    ("Fizika 1 (6 kr)-PHY018-2", "Fizika 1", "PHY018", "PHY018-2"),
    ("Fizika 1 (6 kr)-PHY018-L2", "Fizika 1", "PHY018", "PHY018-L2"),      # avval bu kod umuman o'qilmasdi
    ("Hisob (Calculus) 1-CLC018-2", "Hisob 1", "CLC018", "CLC018-2"),
    ("Diskret tuzilmalar-/MTH015", "Diskret tuzilmalar", "MTH015", "MTH015"),
    ("Kompyuter tarmoqlari/-NWK013", "Kompyuter tarmoqlari", "NWK013", "NWK013"),
    ("Axborot xavfsizligi auditi (4 kr)-INS001-3", "Axborot xavfsizligi auditi", "INS001", "INS001-3"),
    ("Xorijiy til", "Xorijiy til", None, None),
])
def test_the_full_code_is_kept_and_the_subject_is_still_one(raw, name, base, full):
    assert split_subject_code(raw) == (name, base, full)
    assert normalize_subject_name(raw) == (name, base)       # fan aniqlash qoidasi o'zgarmadi


def test_code_goes_in_front_of_the_subject_everywhere():
    s = NS(start_time="08:30", subject=NS(name="Fizika 1", code="PHY018"), code="PHY018-L2", room=NS(number="A-327"),
           teacher=None, week_parity=WeekParity.ALL, end_time="09:50")
    assert "<code>PHY018-L2</code> Fizika 1" in _lesson_line(s, "uz")
    assert "📚 <code>PHY018-L2</code> Fizika 1" in format_reminder(s, 15, "uz")
    # to'liq kod saqlanmagan eski dars: fan kodi ko'rsatiladi; kodsiz fan - faqat nom
    old = NS(start_time="08:30", subject=NS(name="Fizika 1", code="PHY018"), code=None, room=None, teacher=None, week_parity=WeekParity.ALL)
    assert "<code>PHY018</code> Fizika 1" in _lesson_line(old, "uz")
    nocode = NS(start_time="08:30", subject=NS(name="Xorijiy til", code=None), code=None, room=None, teacher=None, week_parity=WeekParity.ALL)
    assert "<code>" not in _lesson_line(nocode, "uz") and "Xorijiy til" in _lesson_line(nocode, "uz")
    assert subject_label("A<b>", "X1") == "<code>X1</code> A&lt;b&gt;"          # HTML buzilmaydi
    t = NS(start_time="10:00", end_time="11:20", subject="Kriptografiya", code="CGM001-2", group_name="712-24", room=None, week_parity=WeekParity.ALL)
    assert "<code>CGM001-2</code> Kriptografiya" in _teacher_line(t, "uz")
    assert "📚 <code>CGM001-2</code> Kriptografiya" in format_teacher_reminder(t, 15, "uz", __import__("datetime").date.today())


@pytest.mark.asyncio
async def test_approved_schedule_saves_the_full_code_and_resending_updates_it(db_session):
    univ = University(name="TATU")
    db_session.add(univ)
    await db_session.flush()
    fac = Faculty(university_id=univ.id, name="Kiberxavfsizlik")
    db_session.add(fac)
    await db_session.flush()
    group = Group(university_id=univ.id, faculty_id=fac.id, name="712-24")
    user = User(telegram_id=9001, first_name="A")
    db_session.add_all([group, user])
    await db_session.flush()

    def submission(subject):
        lessons = [{"day": "Dushanba", "subject": subject, "start_time": "08:30", "end_time": "09:50", "lesson_type": "LECTURE"}]
        return ScheduleSubmission(user_id=user.id, university_id=univ.id, faculty_id=fac.id, group_id=group.id,
                                  image_file_id='f', status=SubmissionStatus.ADMIN_REVIEW, ai_extracted_json=json.dumps(lessons))

    first = submission("Fizika 1 (6 kr)-PHY018-L2")
    db_session.add(first)
    await db_session.flush()
    created = await ScheduleService.resolve_and_create_schedules_from_extraction(db_session, first)
    assert [(c.code, c.subject_id is not None) for c in created] == [("PHY018-L2", True)]
    from app.models.university import Subject
    assert [s.code for s in (await db_session.execute(select(Subject))).scalars().all()] == ["PHY018"]                                  # fan bitta, asosiy kod

    second = submission("Fizika 1 (6 kr)-PHY018-2")                  # boshqa bo'lim, o'sha dars
    db_session.add(second)
    await db_session.flush()
    await ScheduleService.resolve_and_create_schedules_from_extraction(db_session, second)
    rows = (await db_session.execute(select(Schedule).where(Schedule.is_active == True))).scalars().all()  # noqa: E712
    assert [(r.day_of_week, r.code) for r in rows] == [(DayOfWeek.MONDAY, "PHY018-2")]   # dars ko'paymadi, kodi yangilandi
