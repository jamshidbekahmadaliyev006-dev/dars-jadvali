from unittest.mock import AsyncMock, MagicMock
import pytest
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Message, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.middlewares.menu_reset import MenuResetMiddleware
from app.bot.sender import BLOCKED, FAILED, NOT_STARTED, OK, safe_send
from app.models.enums import TeacherStatus, UserRole
from app.models.user import User
from app.services.teacher_service import TeacherService
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_menu_button_cancels_pending_input_state():
    state = AsyncMock()
    state.get_state = AsyncMock(return_value="ReminderStates:waiting_minutes")
    handler = AsyncMock(return_value="ran")
    msg = MagicMock(spec=Message)
    msg.text = "📖 Bugun"
    result = await MenuResetMiddleware()(handler, msg, {"state": state})
    state.clear.assert_awaited_once()      # kutilayotgan holat bekor qilindi
    assert result == "ran"                 # tugma o'z ishini qildi

    state.clear.reset_mock()
    msg.text = "30"                        # oddiy son - holat saqlanadi (vaqt kiritilyapti)
    await MenuResetMiddleware()(handler, msg, {"state": state})
    state.clear.assert_not_awaited()


@pytest.mark.asyncio
async def test_block_by_link_username_or_id_revokes_teacher(db_session: AsyncSession):
    user = User(telegram_id=555, username="AcoderM", first_name="Fake", role=UserRole.USER)
    db_session.add(user)
    await db_session.commit()
    profile = await TeacherService.submit_profile(db_session, user.id, "TATU", "Soxta Ustoz", "KX")
    await TeacherService.set_status(db_session, profile.id, TeacherStatus.APPROVED)

    for query in ("@AcoderM", "https://t.me/AcoderM", "acoderm", "555"):
        found = await UserService.find_user(db_session, query)
        assert found and found.id == user.id, query

    await UserService.set_blocked(db_session, user, True)
    await db_session.refresh(user)
    await db_session.refresh(profile)
    assert user.is_active is False and profile.status == TeacherStatus.REJECTED
    assert await TeacherService.get_approved(db_session, user.id) is None

    await UserService.set_blocked(db_session, user, False)
    await db_session.refresh(user)
    assert user.is_active is True and profile.status == TeacherStatus.REJECTED  # ustozlik qayta tasdiq talab qiladi


@pytest.mark.asyncio
async def test_admin_cannot_be_blocked(db_session: AsyncSession, monkeypatch):
    from app.bot.handlers import admin_menu

    admin = User(telegram_id=1, first_name="A", role=UserRole.ADMIN, language_code="uz")
    db_session.add(admin)
    await db_session.commit()
    msg = MagicMock(spec=Message)
    msg.text = "/block 1"
    msg.answer = AsyncMock()
    await admin_menu.handle_block_command(msg, admin, db_session)
    assert "bloklab bo'lmaydi" in msg.answer.call_args.args[0]
    await db_session.refresh(admin)
    assert admin.is_active is True


@pytest.mark.asyncio
async def test_safe_send_classifies_failures_and_retries():
    from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter
    from aiogram.methods import SendMessage

    def err(cls, text, **kw):
        return cls(method=SendMessage(chat_id=1, text="x"), message=text, **kw)

    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=err(TelegramForbiddenError, "Forbidden: bot was blocked by the user"))
    assert (await safe_send(bot, 1, "x"))[0] == BLOCKED
    bot.send_message = AsyncMock(side_effect=err(TelegramForbiddenError, "Forbidden: bot can't initiate conversation with a user"))
    assert (await safe_send(bot, 1, "x"))[0] == NOT_STARTED
    bot.send_message = AsyncMock(side_effect=err(TelegramBadRequest, "Bad Request: chat not found"))
    assert (await safe_send(bot, 1, "x"))[0] == NOT_STARTED
    # tezlik chegarasi: bir marta kutib, qayta urinadi va yetkazadi
    bot.send_message = AsyncMock(side_effect=[TelegramRetryAfter(method=SendMessage(chat_id=1, text="x"), message="flood", retry_after=0), None])
    status, _ = await safe_send(bot, 1, "x")
    assert status == OK and bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_new_user_gets_15_minute_reminder(db_session: AsyncSession):
    from app.bot.middlewares.auth import AuthMiddleware

    tg = MagicMock(spec=TgUser)
    tg.id, tg.first_name, tg.last_name, tg.username, tg.language_code = 9090, "Yangi", None, None, "uz"
    msg = MagicMock(spec=Message)
    seen = {}

    async def handler(event, data):
        seen.update(data)

    await AuthMiddleware()(handler, msg, {"event_from_user": tg, "session": db_session})
    from app.services.schedule_service import ScheduleService
    setting = await ScheduleService.get_or_create_reminder_setting(db_session, seen["current_user"].id)
    assert setting.minutes_before == 15 and setting.is_enabled is True


def test_only_a_full_text_schedule_is_accepted():
    from app.bot.text_utils import looks_like_full_schedule as full

    three = "Dushanba 08:00-09:30 Matematika A-327\nDushanba 09:30-11:00 Fizika\nSeshanba 8.00-9.30 Ingliz tili"
    assert full(three)
    assert full("Du 8:00-9:30 Mat; Du 9:30-11:00 Fiz; Se 8:00-9:30 Ing")
    for junk in ("Matematika", "salom", "712-24", "Dushanba matematika 8:00", "Dushanba 08:00 Matematika\nSeshanba 09:00 Fizika"):
        assert not full(junk), junk


@pytest.mark.asyncio
async def test_incomplete_text_after_registration_is_not_treated_as_schedule(db_session: AsyncSession):
    from app.bot.handlers import registration

    user = User(telegram_id=4040, first_name="T", role=UserRole.USER, language_code="uz")
    msg = MagicMock(spec=Message)
    msg.text = "Matematika"
    msg.answer = AsyncMock()
    state = AsyncMock()
    await registration.process_schedule_text(msg, state, user, db_session)
    assert "to'liq jadval emas" in msg.answer.call_args.args[0]
    state.clear.assert_not_awaited()  # holat saqlandi - rasm yoki to'liq matn yuborish mumkin


def test_small_images_are_detected_without_a_graphics_library():
    import struct, zlib
    from app.bot.album import image_size, looks_too_small

    def png(w, h):
        def chunk(tag, data):
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IEND", b"")

    assert image_size(png(572, 1280)) == (572, 1280)
    assert looks_too_small([png(572, 1280)]) is True      # tor skrinshot - mayda yozuv
    assert looks_too_small([png(1080, 1920)]) is False
    assert looks_too_small([b"not an image"]) is False
