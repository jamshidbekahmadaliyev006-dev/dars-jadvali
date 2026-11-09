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
