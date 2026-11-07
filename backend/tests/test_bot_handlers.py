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
