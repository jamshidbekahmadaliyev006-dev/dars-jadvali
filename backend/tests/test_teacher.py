from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import pytest
import pytz
from aiogram.types import CallbackQuery, Chat, Message, User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.handlers import teacher as teacher_handlers
from app.core.config import settings
from app.models.enums import DayOfWeek, TeacherStatus, UserRole, WeekParity
from app.models.log import NotificationLog
from app.models.teacher import TeacherLesson, TeacherProfile
from app.models.user import User
from app.scheduler import jobs as scheduler_jobs
from app.services.schedule_service import week_parity_for
from app.services.teacher_service import TeacherService
from tests.conftest import TestingSessionLocal

DAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]


def _message(text: str = "", user_id: int = 700) -> Message:
    msg = MagicMock(spec=Message)
    msg.text = text
    msg.chat = MagicMock(spec=Chat)
    msg.chat.id = user_id
    msg.from_user = MagicMock(spec=TgUser)
    msg.from_user.id = user_id
    msg.answer = AsyncMock(return_value=MagicMock(edit_text=AsyncMock()))
    msg.bot = MagicMock()
    msg.bot.send_message = AsyncMock()
    msg.bot.send_chat_action = AsyncMock()
    return msg


async def _user(db: AsyncSession, tg_id: int, role=UserRole.USER) -> User:
    user = User(telegram_id=tg_id, first_name="Ustoz", role=role, language_code="uz", language_chosen=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_teacher_registration_goes_to_admin_and_approval_unlocks(db_session: AsyncSession, monkeypatch):
    teacher_user = await _user(db_session, 700)
    admin = await _user(db_session, 900, role=UserRole.ADMIN)
    monkeypatch.setattr(type(settings), "admin_id_list", property(lambda self: [900]))

    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"t_university": "TATU", "t_name": "Karimov Anvar Rustamovich"})
    msg = _message("Kiberxavfsizlik")
    await teacher_handlers.teacher_department(msg, state, teacher_user, db_session)

    profile = await TeacherService.get_profile(db_session, teacher_user.id)
    assert profile.status == TeacherStatus.PENDING
    assert profile.full_name == "Karimov Anvar Rustamovich"
    # Adminga tasdiqlash tugmalari bilan so'rov ketdi
    admin_call = msg.bot.send_message.call_args
    assert admin_call.args[0] == 900
    assert 'href="tg://user?id=700"' in admin_call.args[1]  # admin kimligini bilsin
    buttons = [b.callback_data for row in admin_call.kwargs["reply_markup"].inline_keyboard for b in row]
    assert buttons == [f"tch_ok_{profile.id}", f"tch_no_{profile.id}"]

    # Tasdiqlanmagan o'qituvchi o'qituvchi filtridan o'tmaydi
    assert await teacher_handlers.ApprovedTeacher()(msg, current_user=teacher_user, session=db_session) is False

    query = MagicMock(spec=CallbackQuery)
    query.data = f"tch_ok_{profile.id}"
    query.answer = AsyncMock()
    query.message = MagicMock(html_text="so'rov", edit_text=AsyncMock())
    query.bot = MagicMock(send_message=AsyncMock())
    await teacher_handlers.admin_review_teacher(query, admin, db_session, AsyncMock())

    await db_session.refresh(profile)
    assert profile.status == TeacherStatus.APPROVED
    assert query.bot.send_message.await_args_list[0].args[0] == 700  # o'qituvchiga xabar ketdi
    ok = await teacher_handlers.ApprovedTeacher()(msg, current_user=teacher_user, session=db_session)
    assert ok["teacher"].id == profile.id


@pytest.mark.asyncio
async def test_non_admin_cannot_approve_teacher(db_session: AsyncSession):
    student = await _user(db_session, 701)
    profile = await TeacherService.submit_profile(db_session, student.id, "TATU", "Ali Valiyev", "KX")
    query = MagicMock(spec=CallbackQuery)
    query.data = f"tch_ok_{profile.id}"
    query.answer = AsyncMock()
    await teacher_handlers.admin_review_teacher(query, student, db_session, AsyncMock())
    await db_session.refresh(profile)
    assert profile.status == TeacherStatus.PENDING


@pytest.mark.asyncio
async def test_teacher_lessons_saved_with_groups_and_replaced(db_session: AsyncSession):
    user = await _user(db_session, 702)
    profile = await TeacherService.submit_profile(db_session, user.id, "TATU", "Ali Valiyev", "KX")
    items = [
        {"day": "Dushanba", "subject": "Matematika", "start_time": "08:00", "end_time": "09:30", "group": "712_24", "room": "327", "building": "A"},
        {"day": "Dushanba", "subject": "Fizika", "start_time": "09:30", "end_time": "11:00", "group": "732-24", "room": "-210", "week_parity": "ODD"},
        {"day": "Chorshanba", "subject": "Ma'ruza", "start_time": "11:00", "end_time": "12:30", "group": "712-24, 732_24"},
        {"day": "???", "subject": "Noto'g'ri", "start_time": "08:00", "end_time": "09:00"},
    ]
    saved = await TeacherService.replace_lessons(db_session, profile.id, items)
    assert len(saved) == 3
    lessons = await TeacherService.get_lessons(db_session, profile.id)
    assert [(l.group_name, l.room) for l in lessons] == [("712-24", "A-327"), ("732-24", "210"), ("712-24, 732-24", None)]

    even_monday = await TeacherService.get_lessons(db_session, profile.id, DayOfWeek.MONDAY, WeekParity.EVEN)
    assert [l.subject for l in even_monday] == ["Matematika"]

    await TeacherService.replace_lessons(db_session, profile.id, [items[0]])
    assert len(await TeacherService.get_lessons(db_session, profile.id)) == 1


def test_teacher_week_text_shows_groups_and_rooms():
    from types import SimpleNamespace
    from app.bot.text_utils import format_teacher_week

    lesson = SimpleNamespace(
        day_of_week=DayOfWeek.MONDAY, start_time="08:00", end_time="09:30", subject="Matematika",
        group_name="712-24", room="A-327", week_parity=WeekParity.ALL,
    )
    text = format_teacher_week([lesson], "uz")
    assert "Mening dars jadvalim" in text and "👥 712-24" in text and "📍 A-327" in text


@pytest.mark.asyncio
async def test_teacher_gets_reminder_once(db_session: AsyncSession, monkeypatch):
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    start = now + timedelta(minutes=10)
    if start.date() != now.date():
        pytest.skip("Yarim tunga yaqin")

    user = await _user(db_session, 703)
    profile = await TeacherService.submit_profile(db_session, user.id, "TATU", "Ali Valiyev", "KX")
    await TeacherService.set_status(db_session, profile.id, TeacherStatus.APPROVED)
    await TeacherService.replace_lessons(db_session, profile.id, [{
        "day": DAYS[now.weekday()], "subject": "Matematika", "start_time": start.strftime("%H:%M"),
        "end_time": (start + timedelta(minutes=80)).strftime("%H:%M"), "group": "712-24", "room": "A-327",
    }])
    db_session.expunge_all()

    sent = []

    class Bot:
        async def send_message(self, chat_id, text, parse_mode=None):
            sent.append((chat_id, text))

    monkeypatch.setattr(scheduler_jobs, "AsyncSessionLocal", lambda: TestingSessionLocal())
    monkeypatch.setattr(scheduler_jobs, "get_bot", lambda: Bot())
    await scheduler_jobs.check_and_send_lesson_reminders()
    await scheduler_jobs.check_and_send_lesson_reminders()

    assert len(sent) == 1 and sent[0][0] == 703
    assert "👥 712-24" in sent[0][1] and "📅" in sent[0][1]


@pytest.mark.asyncio
async def test_pending_teacher_gets_no_reminder(db_session: AsyncSession, monkeypatch):
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    start = now + timedelta(minutes=5)
    if start.date() != now.date():
        pytest.skip("Yarim tunga yaqin")
    user = await _user(db_session, 704)
    profile = await TeacherService.submit_profile(db_session, user.id, "TATU", "Ali Valiyev", "KX")
    await TeacherService.replace_lessons(db_session, profile.id, [{
        "day": DAYS[now.weekday()], "subject": "Fizika", "start_time": start.strftime("%H:%M"),
        "end_time": (start + timedelta(minutes=80)).strftime("%H:%M"),
    }])
    sent = []

    class Bot:
        async def send_message(self, chat_id, text, parse_mode=None):
            sent.append(chat_id)

    monkeypatch.setattr(scheduler_jobs, "AsyncSessionLocal", lambda: TestingSessionLocal())
    monkeypatch.setattr(scheduler_jobs, "get_bot", lambda: Bot())
    await scheduler_jobs.check_and_send_lesson_reminders()
    assert sent == []


@pytest.mark.asyncio
async def test_admin_statistics_count_unique_subjects_and_user_roles(db_session: AsyncSession):
    from app.bot.handlers.admin_menu import collect_statistics, collect_user_counts
    from app.models.enums import LessonType
    from app.models.schedule import Schedule
    from app.models.university import Faculty, Group, Subject, University

    univ = University(name="TATU")
    db_session.add(univ)
    await db_session.commit()
    fac = Faculty(name="Kiberxavfsizlik", university_id=univ.id)
    general = Faculty(name="Umumiy", university_id=univ.id)
    db_session.add_all([fac, general])
    await db_session.commit()
    g1 = Group(name="712-24", university_id=univ.id, faculty_id=fac.id)
    g2 = Group(name="732-24", university_id=univ.id, faculty_id=fac.id)
    s1 = Subject(name="Kriptografiya usullari", university_id=univ.id)
    s2 = Subject(name="Kriptografiya usullari-CGM003", university_id=univ.id)  # o'sha fan, kod bilan
    s3 = Subject(name="Tarmoq xavfsizligi", university_id=univ.id)
    db_session.add_all([g1, g2, s1, s2, s3])
    await db_session.commit()
    for group, subject in [(g1, s1), (g1, s3), (g2, s2), (g2, s3)]:
        db_session.add(Schedule(
            university_id=univ.id, group_id=group.id, subject_id=subject.id, day_of_week=DayOfWeek.MONDAY,
            start_time="08:00", end_time="09:30", lesson_type=LessonType.LECTURE,
        ))
    student = User(telegram_id=801, first_name="Talaba", role=UserRole.USER, group_id=g1.id, university_id=univ.id)
    teacher_user = User(telegram_id=802, first_name="Ustoz", role=UserRole.USER)
    db_session.add_all([student, teacher_user, User(telegram_id=803, first_name="Yangi", role=UserRole.USER)])
    await db_session.commit()
    profile = await TeacherService.submit_profile(db_session, teacher_user.id, "TATU", "Ali Valiyev", "KX")
    await TeacherService.set_status(db_session, profile.id, TeacherStatus.APPROVED)
    await TeacherService.replace_lessons(db_session, profile.id, [
        {"day": "Dushanba", "subject": "kriptografiya usullari", "start_time": "08:00", "end_time": "09:30", "group": "712-24"},
        {"day": "Seshanba", "subject": "Fizika", "start_time": "08:00", "end_time": "09:30", "group": "712-24"},
    ])

    stats = await collect_statistics(db_session)
    assert stats == {"universities": 1, "faculties": 1, "teachers": 1, "groups": 2, "subjects": 3}
    counts = await collect_user_counts(db_session)
    assert counts == {"total": 3, "teachers": 1, "pending": 0, "students": 1, "unregistered": 1}
    assert counts["teachers"] + counts["pending"] + counts["students"] + counts["unregistered"] == counts["total"]


@pytest.mark.asyncio
async def test_admin_teachers_section_shows_accounts(db_session: AsyncSession):
    admin = await _user(db_session, 950, role=UserRole.ADMIN)
    t1 = User(telegram_id=951, first_name="Anvar", last_name="Karimov", username="anvar_k", role=UserRole.USER, language_code="uz")
    t2 = User(telegram_id=952, first_name="Dilshod", role=UserRole.USER, language_code="uz")
    db_session.add_all([t1, t2])
    await db_session.commit()
    p1 = await TeacherService.submit_profile(db_session, t1.id, "TATU", "Karimov Anvar Rustamovich", "Kiberxavfsizlik")
    await TeacherService.set_status(db_session, p1.id, TeacherStatus.APPROVED)
    p2 = await TeacherService.submit_profile(db_session, t2.id, "TATU", "Aliyev Dilshod", "Matematika")

    msg = _message("👨‍🏫 O'qituvchilar", 950)
    await teacher_handlers.admin_teachers(msg, admin, db_session)
    texts = [c.args[0] for c in msg.answer.call_args_list]
    assert "Tasdiqlangan: <b>1</b>" in texts[0] and "Tasdiq kutmoqda: <b>1</b>" in texts[0]
    approved_text = texts[1]
    assert "Karimov Anvar Rustamovich" in approved_text
    assert 'href="https://t.me/anvar_k"' in approved_text and "@anvar_k" in approved_text
    assert "Kiberxavfsizlik" in approved_text
    # Ortiqcha ma'lumot yo'q: universitet, ID, darslar soni ko'rsatilmaydi
    assert "TATU" not in approved_text and "ID " not in approved_text and "dars" not in approved_text
    # Kutayotgan o'qituvchi alohida, tasdiqlash tugmalari bilan
    last = msg.answer.call_args_list[-1]
    assert "Aliyev Dilshod" in last.args[0] and 'href="tg://user?id=952"' in last.args[0]
    buttons = [b.callback_data for row in last.kwargs["reply_markup"].inline_keyboard for b in row]
    assert buttons == [f"tch_ok_{p2.id}", f"tch_no_{p2.id}"]


@pytest.mark.asyncio
async def test_non_admin_cannot_open_teachers_section(db_session: AsyncSession):
    student = await _user(db_session, 960)
    msg = _message("👨‍🏫 O'qituvchilar", 960)
    await teacher_handlers.admin_teachers(msg, student, db_session)
    assert msg.answer.call_count == 1 and "administrator" in msg.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_user_categories_always_add_up_to_total(db_session: AsyncSession):
    from app.bot.handlers.admin_menu import _users_message, collect_user_counts
    from app.models.university import Faculty, Group, University

    univ = University(name="TATU")
    db_session.add(univ)
    await db_session.commit()
    fac = Faculty(name="KX", university_id=univ.id)
    db_session.add(fac)
    await db_session.commit()
    grp = Group(name="712-24", university_id=univ.id, faculty_id=fac.id)
    db_session.add(grp)
    await db_session.commit()
    users = [User(telegram_id=1000 + i, first_name=f"U{i}", role=UserRole.USER) for i in range(7)]
    users[0].group_id = users[1].group_id = grp.id  # 2 talaba
    users[2].group_id = grp.id                      # talaba, keyin o'qituvchi bo'ldi
    db_session.add_all(users)
    await db_session.commit()
    p = await TeacherService.submit_profile(db_session, users[2].id, "TATU", "Ali Valiyev", "KX")
    await TeacherService.set_status(db_session, p.id, TeacherStatus.APPROVED)
    await TeacherService.submit_profile(db_session, users[3].id, "TATU", "Vali Aliyev", "KX")  # kutmoqda
    rejected = await TeacherService.submit_profile(db_session, users[4].id, "TATU", "Rad Etilgan", "KX")
    await TeacherService.set_status(db_session, rejected.id, TeacherStatus.REJECTED)

    c = await collect_user_counts(db_session)
    assert c == {"total": 7, "teachers": 1, "pending": 1, "students": 2, "unregistered": 3}
    assert c["teachers"] + c["pending"] + c["students"] + c["unregistered"] == c["total"]
    text = await _users_message(db_session, "uz")
    assert "Jami: <b>7</b>" in text and "tugatmagan: <b>3</b>" in text and "kutayotgan" in text


def test_reminder_skipped_only_when_next_lesson_is_in_the_same_room():
    from app.scheduler.jobs import _same_room_continuations

    lessons = [
        (1, "08:00", "09:30", "A-327", 10),
        (1, "09:30", "11:00", "A-327", 11),   # xuddi shu xona - eslatma yo'q
        (1, "11:00", "12:30", "B-210", 12),   # boshqa xona - eslatma bor
        (1, "12:30", "14:00", "B-210", 13),   # yana shu xona - yo'q
        (1, "16:00", "17:30", "B-210", 14),   # uzoq tanaffusdan keyin - eslatma bor
        (2, "09:30", "11:00", "A-327", 20),   # boshqa guruh - o'zi birinchi dars, eslatma bor
        (3, "08:00", "09:30", None, 30),
        (3, "09:30", "11:00", None, 31),      # xona noma'lum - eslatma yuboriladi
    ]
    assert _same_room_continuations(lessons) == {11, 13}


@pytest.mark.asyncio
async def test_album_waits_and_returns_all_files_once(monkeypatch):
    from app.bot import album

    monkeypatch.setattr(album, "ALBUM_WAIT_SECONDS", 0.05)
    def msg(i):
        m = _message("", 5)
        m.media_group_id = "g1"
        return m

    import asyncio
    results = await asyncio.gather(*[album.collect_album(msg(i), f"f{i}") for i in range(3)])
    assert sorted(r for r in results if r) == [["f0", "f1", "f2"]]
    assert results.count(None) == 2
    single = _message("", 5)
    single.media_group_id = None
    assert await album.collect_album(single, "only") == ["only"]


@pytest.mark.asyncio
async def test_photo_of_another_group_is_flagged(db_session: AsyncSession):
    from app.bot.handlers.user_menu import _group_mismatch
    from app.models.university import Faculty, Group, University

    univ = University(name="TATU")
    db_session.add(univ)
    await db_session.commit()
    fac = Faculty(name="KX", university_id=univ.id)
    db_session.add(fac)
    await db_session.commit()
    grp = Group(name="712-24", university_id=univ.id, faculty_id=fac.id)
    db_session.add(grp)
    await db_session.commit()
    user = User(telegram_id=5100, first_name="T", role=UserRole.USER, group_id=grp.id, university_id=univ.id)

    assert await _group_mismatch(db_session, user, [{"group": "712_24"}]) is None
    assert await _group_mismatch(db_session, user, [{"group": "712-24, 732-24"}]) is None
    assert await _group_mismatch(db_session, user, [{"group": None}]) is None
    assert await _group_mismatch(db_session, user, [{"group": "732-24"}]) == "732-24"


def test_group_key_keeps_number_boundaries():
    from app.services.university_service import group_key

    assert group_key("712-24") == group_key("712_24") == group_key("712 24") == group_key("712/24")
    assert group_key("7-12") != group_key("712")
    assert group_key("71224") != group_key("712-24")
