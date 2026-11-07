from unittest.mock import AsyncMock, MagicMock
import pytest
from aiogram.types import Chat, Message, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.handlers.admin_menu import handle_admin_statistics
from app.bot.handlers.start import handle_start
from app.bot.handlers.user_menu import handle_today_lessons
from app.models.enums import UserRole
from app.models.user import User


def make_mock_message(text: str, user_id: int = 12345) -> Message:
    message = MagicMock(spec=Message)
    message.text = text
    message.chat = MagicMock(spec=Chat)
    message.chat.id = user_id
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = user_id
    message.from_user.first_name = "TestUser"
    message.answer = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_start_handler_for_student():
    student_user = User(
        id=1,
        telegram_id=12345,
        first_name="Aziz",
        role=UserRole.USER,
        is_active=True,
        group_id=1,  # ro'yxatdan o'tgan - registration oqimi ishga tushmasligi uchun
    )
    mock_msg = make_mock_message("/start", 12345)
    mock_state = AsyncMock()

    await handle_start(mock_msg, current_user=student_user, state=mock_state)

    mock_msg.answer.assert_called_once()
    args, kwargs = mock_msg.answer.call_args
    # Javob matnida talabaga xush kelibsiz so'zlari borligini tekshirish
    assert "universitet talabalari uchun universal platformaga xush kelibsiz" in args[0]
    # Reply markup borligini tekshirish
    assert "reply_markup" in kwargs


@pytest.mark.asyncio
async def test_start_handler_for_admin():
    admin_user = User(
        id=2,
        telegram_id=99999,
        first_name="Adminbek",
        role=UserRole.ADMIN,
        is_active=True,
        group_id=1,
    )
    mock_msg = make_mock_message("/start", 99999)
    mock_state = AsyncMock()

    await handle_start(mock_msg, current_user=admin_user, state=mock_state)

    mock_msg.answer.assert_called_once()
    args, kwargs = mock_msg.answer.call_args
    assert "Administrator Adminbek" in args[0]
    assert "UniNotify boshqaruv tizimiga xush kelibsiz" in args[0]


@pytest.mark.asyncio
async def test_start_handler_triggers_registration_when_no_group():
    new_user = User(
        id=3,
        telegram_id=55555,
        first_name="Yangi",
        role=UserRole.USER,
        is_active=True,
        group_id=None,
    )
    mock_msg = make_mock_message("/start", 55555)
    mock_state = AsyncMock()

    await handle_start(mock_msg, current_user=new_user, state=mock_state)

    # Avval xush kelibsiz, keyin ro'yxatdan o'tish (universitet so'rovi) yuboriladi
    assert mock_msg.answer.call_count == 2
    mock_state.set_state.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_statistics_permission_denied(db_session: AsyncSession):
    student_user = User(
        id=1,
        telegram_id=12345,
        first_name="Aziz",
        role=UserRole.USER,
        is_active=True,
    )
    mock_msg = make_mock_message("📈 Statistika", 12345)

    await handle_admin_statistics(mock_msg, current_user=student_user, session=db_session)
    mock_msg.answer.assert_called_once()
    args, _ = mock_msg.answer.call_args
    assert "faqat tizim administratorlari uchun" in args[0]


@pytest.mark.asyncio
async def test_admin_statistics_permission_granted(db_session: AsyncSession):
    admin_user = User(
        id=2,
        telegram_id=99999,
        first_name="Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )
    mock_msg = make_mock_message("📈 Statistika", 99999)

    await handle_admin_statistics(mock_msg, current_user=admin_user, session=db_session)
    mock_msg.answer.assert_called_once()
    args, _ = mock_msg.answer.call_args
    assert "UniNotify Tizim Statistikasi" in args[0]
    assert "Foydalanuvchilar" in args[0]


@pytest.mark.asyncio
async def test_registration_shows_existing_group_schedule(db_session: AsyncSession):
    from app.bot.handlers.registration import process_group
    from app.models.enums import DayOfWeek
    from app.models.schedule import Schedule
    from app.models.university import Faculty, Group, Subject, University

    univ = University(name="TATU")
    db_session.add(univ)
    await db_session.commit()
    fac = Faculty(name="Kiberxavfsizlik", university_id=univ.id)
    subj = Subject(name="Tarmoq xavfsizligi", university_id=univ.id)
    db_session.add_all([fac, subj])
    await db_session.commit()
    grp = Group(name="KX-21", university_id=univ.id, faculty_id=fac.id)
    db_session.add(grp)
    await db_session.commit()
    db_session.add(Schedule(
        university_id=univ.id, group_id=grp.id, subject_id=subj.id,
        day_of_week=DayOfWeek.MONDAY, start_time="08:00", end_time="09:20",
    ))
    classmate = User(telegram_id=4242, first_name="Guruhdosh", role=UserRole.USER, is_active=True)
    db_session.add(classmate)
    await db_session.commit()

    mock_msg = make_mock_message("kx-21", 4242)
    mock_state = AsyncMock()
    mock_state.get_data.return_value = {"university_name": "tatu", "faculty_name": "kiberxavfsizlik"}

    await process_group(mock_msg, mock_state, classmate, db_session)

    assert classmate.group_id == grp.id
    assert mock_msg.answer.call_count == 2
    assert "Tarmoq xavfsizligi" in mock_msg.answer.call_args_list[1].args[0]


@pytest.mark.asyncio
async def test_failed_ai_reading_never_writes_lessons(db_session: AsyncSession, monkeypatch):
    from sqlalchemy import select
    from app.bot.handlers import user_menu
    from app.models.schedule import Schedule
    from app.models.university import Faculty, Group, University
    from app.services import ai_service

    class FailingProvider:
        async def extract_schedule_from_image(self, image_bytes, filename="x.jpg"):
            raise RuntimeError("AI ishlamadi")

    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: FailingProvider())

    univ = University(name="TATU")
    db_session.add(univ)
    await db_session.commit()
    fac = Faculty(name="KI", university_id=univ.id)
    db_session.add(fac)
    await db_session.commit()
    grp = Group(name="1", university_id=univ.id, faculty_id=fac.id)
    db_session.add(grp)
    await db_session.commit()
    student = User(
        telegram_id=77, first_name="T", role=UserRole.USER, is_active=True,
        university_id=univ.id, faculty_id=fac.id, group_id=grp.id,
    )
    db_session.add(student)
    await db_session.commit()

    msg = make_mock_message("", 77)
    msg.photo = [MagicMock(file_id="f1")]
    msg.bot = MagicMock()
    msg.bot.get_file = AsyncMock(return_value=MagicMock(file_path="p"))
    msg.bot.download_file = AsyncMock(return_value=MagicMock(read=lambda: b"img"))
    msg.bot.send_photo = AsyncMock()
    loading = MagicMock(edit_text=AsyncMock())
    msg.answer = AsyncMock(return_value=loading)

    await user_menu.handle_schedule_photo_upload(msg, student, db_session, AsyncMock())

    rows = (await db_session.execute(select(Schedule))).scalars().all()
    assert rows == []
    assert "o'qib bo'lmadi" in loading.edit_text.call_args.args[0]
