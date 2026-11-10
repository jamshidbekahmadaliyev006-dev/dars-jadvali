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


def _message(text="", uid=1):
    from aiogram.types import Chat
    m = MagicMock(spec=Message)
    m.text = text
    m.chat = MagicMock(spec=Chat)
    m.chat.id = uid
    m.answer = AsyncMock()
    m.bot = MagicMock(send_message=AsyncMock(), send_chat_action=AsyncMock(), send_media_group=AsyncMock())
    return m


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


def test_week_coverage_rules():
    from app.bot.text_utils import MIN_TEACHER_DAYS, MIN_TEACHER_LESSONS, is_full_week, week_coverage

    one_day = [{"day": "Payshanba", "subject": s} for s in ("A", "B", "C")]     # sizning holatingiz: 1 kun, 3 dars
    assert not is_full_week(one_day)
    assert [d.value for d in week_coverage(one_day)[0]] == ["THURSDAY"]
    week = [{"day": d, "subject": "x"} for d in ("Dushanba", "Dushanba", "Seshanba", "Chorshanba", "Juma")]
    assert is_full_week(week)
    assert not is_full_week([{"day": "Dushanba"}] * 6)                          # 6 dars, lekin 1 kun
    assert not is_full_week([{"day": "Du"}, {"day": "Se"}])                     # kam
    assert is_full_week([{"day": "Dushanba"}, {"day": "Seshanba"}, {"day": "Seshanba"}], MIN_TEACHER_DAYS, MIN_TEACHER_LESSONS)


@pytest.mark.asyncio
async def test_single_day_photo_is_not_saved_as_the_group_schedule(db_session: AsyncSession, monkeypatch):
    from app.bot.handlers import user_menu
    from app.models.enums import SubmissionStatus
    from app.models.schedule import Schedule, ScheduleSubmission
    from app.models.university import Faculty, Group, University
    from sqlalchemy import select as sa_select

    univ = University(name="TATU")
    db_session.add(univ)
    await db_session.commit()
    fac = Faculty(name="KX", university_id=univ.id)
    db_session.add(fac)
    await db_session.commit()
    grp = Group(name="711-24", university_id=univ.id, faculty_id=fac.id)
    db_session.add(grp)
    await db_session.commit()
    student = User(telegram_id=6060, first_name="Nilufar", role=UserRole.USER, university_id=univ.id,
                   faculty_id=fac.id, group_id=grp.id, language_code="uz")
    db_session.add(student)
    await db_session.commit()

    class OneDayAI:
        async def extract_schedule_from_image(self, data, name="x.jpg"):
            from app.schemas.ai import ExtractedLessonItem, ExtractedScheduleResult
            return ExtractedScheduleResult(lessons=[
                ExtractedLessonItem(day="Payshanba", subject=s, start_time=t_, end_time="09:30", room="B-213", building="B")
                for s, t_ in (("Matematik modellashtirish", "08:00"), ("Sonli usullar", "09:30"), ("Hisoblash paketlari", "11:00"))])

    monkeypatch.setattr("app.services.ai_service.get_ai_provider", lambda: OneDayAI())
    monkeypatch.setattr(user_menu, "get_ai_provider", lambda: OneDayAI())
    monkeypatch.setattr(type(user_menu.settings), "admin_id_list", property(lambda self: [1]))

    msg = _message("", 6060)
    msg.document = None
    loading = MagicMock(edit_text=AsyncMock())
    msg.answer = AsyncMock(return_value=loading)
    msg.bot.get_file = AsyncMock(return_value=MagicMock(file_path="p"))
    msg.bot.download_file = AsyncMock(return_value=MagicMock(read=lambda: b"img"))
    await user_menu.process_schedule_input(msg, student, db_session, file_ids=["f1"])

    assert (await db_session.execute(sa_select(Schedule))).scalars().first() is None     # saqlanmadi
    sub = (await db_session.execute(sa_select(ScheduleSubmission))).scalars().first()
    assert sub.status == SubmissionStatus.NEEDS_CORRECTION
    shown = loading.edit_text.call_args.args[0]
    assert "to'liq emas" in shown and "Payshanba" in shown and "butun haftalik" in shown
    msg.bot.send_message.assert_not_awaited()                                              # adminga ham ketmadi


@pytest.mark.asyncio
async def test_same_subject_code_is_one_subject_even_if_name_is_cut(db_session: AsyncSession):
    from app.models.schedule import ScheduleSubmission
    from app.models.enums import SubmissionStatus
    from app.models.university import Faculty, Group, Subject, University
    from app.services.schedule_service import ScheduleService
    from sqlalchemy import select as sa_select
    import json

    univ = University(name="TATU")
    db_session.add(univ)
    await db_session.commit()
    fac = Faculty(name="RTT", university_id=univ.id)
    db_session.add(fac)
    await db_session.commit()
    grp = Group(name="062-23", university_id=univ.id, faculty_id=fac.id)
    user = User(telegram_id=7070, first_name="T", role=UserRole.USER)
    db_session.add_all([grp, user])
    await db_session.commit()
    lessons = [
        {"day": "Dushanba", "subject": "Masofaviy ta'lim texnologiyalari-DLT001", "start_time": "13:00", "end_time": "14:20", "building": "E", "room": "214"},
        {"day": "Payshanba", "subject": "Masofaviy ta'lim texnologiyalar i-/DLT001-1", "start_time": "13:00", "end_time": "14:20", "building": "B", "room": "/408", "week_parity": "EVEN"},
        {"day": "Juma", "subject": "Masofaviy ta'lim texnologiyalari-DLT001-1", "start_time": "09:30", "end_time": "10:50", "building": "B", "room": "408"},
        {"day": "Seshanba", "subject": "Elektron pedagogika (8 kr)-ELP001", "start_time": "09:30", "end_time": "10:50", "building": "B", "room": "411"},
    ]
    sub = ScheduleSubmission(user_id=user.id, university_id=univ.id, group_id=grp.id, image_file_id="-",
                             status=SubmissionStatus.ADMIN_REVIEW, ai_extracted_json=json.dumps(lessons))
    db_session.add(sub)
    await db_session.commit()
    created = await ScheduleService.resolve_and_create_schedules_from_extraction(db_session, sub)
    assert len(created) == 4
    names = sorted((await db_session.execute(sa_select(Subject.name))).scalars().all())
    assert names == ["Elektron pedagogika", "Masofaviy ta'lim texnologiyalari"]   # bitta fan ikki marta emas


@pytest.mark.asyncio
async def test_faculty_variants_match_the_same_faculty(db_session: AsyncSession):
    from app.models.university import Faculty, University
    from app.services.university_service import UniversityService

    univ = University(name="TATU")
    db_session.add(univ)
    await db_session.commit()
    kx = Faculty(name="Kiberxavfsizlik", university_id=univ.id)
    ki = Faculty(name="Kompyuter injiniringi", university_id=univ.id)
    rma = Faculty(name="Radio va mobil aloqa", university_id=univ.id)
    db_session.add_all([kx, ki, rma])
    await db_session.commit()
    for typed, expected in [("Kiber", kx), ("Кибербезопасность", kx), ("KIF", ki), ("kompyuter engineering", ki),
                            ("RMA", rma), ("RVMA", rma), ("kiberxafvsizlik", kx)]:
        found = await UniversityService.match_faculty(db_session, univ.id, typed)
        assert found is not None and found.id == expected.id, typed
    assert await UniversityService.match_faculty(db_session, univ.id, "Iqtisodiyot") is None


def test_admin_menu_has_no_schedules_button():
    from app.bot.keyboards.reply import get_admin_main_keyboard

    texts = [b.text for row in get_admin_main_keyboard("uz").keyboard for b in row]
    assert not any("Jadvallar" in x or "screenshot" in x.lower() for x in texts)
    assert "👨‍🏫 O'qituvchilar" in texts and "👥 Guruhlar" in texts


@pytest.mark.asyncio
async def test_changing_language_only_confirms(db_session: AsyncSession):
    from app.bot.handlers import start

    user = User(telegram_id=8080, first_name="Til", role=UserRole.USER, language_code="uz", language_chosen=True, group_id=1)
    db_session.add(user)
    await db_session.commit()
    q = MagicMock(spec=CallbackQuery)
    q.data = "lang_en"
    q.answer = AsyncMock()
    q.message = MagicMock(delete=AsyncMock(), answer=AsyncMock(), edit_text=AsyncMock())
    await start.handle_language_choice(q, AsyncMock(), user, db_session)

    assert user.language_code == "en"
    q.message.answer.assert_awaited_once()                       # faqat bitta xabar: "qabul qilindi" + menyu
    shown = q.message.answer.call_args
    assert "saved" in shown.args[0].lower() or "language" in shown.args[0].lower()
    assert [b.text for row in shown.kwargs["reply_markup"].keyboard for b in row][0] == "📅 Timetable"


class _FacultyAI:
    def __init__(self, verdict):
        self.verdict = verdict

    async def resolve_faculty(self, typed, existing):
        return self.verdict


@pytest.mark.asyncio
async def test_faculty_resolution_merges_variants_and_asks_for_full_names(db_session: AsyncSession, monkeypatch):
    from app.models.university import Faculty, University
    from app.services import name_validation
    from app.services.name_validation import resolve_faculty_name

    univ = University(name="Toshkent Axborot Texnologiyalari Universiteti")
    db_session.add(univ)
    await db_session.commit()
    db_session.add_all([Faculty(name="Kiberxavfsizlik", university_id=univ.id),
                        Faculty(name="Kompyuter injiniringi", university_id=univ.id)])
    await db_session.commit()
    U = "TATU"

    monkeypatch.setattr(name_validation, "get_ai_provider", lambda: _FacultyAI(None))
    # Qoidalar o'zi topadi - AI kerak emas
    for typed in ("Kiber", "Кибербезопасность", "kiberxafvsizlik", "KIF", "Kompyuter engineering"):
        got = await resolve_faculty_name(db_session, U, typed)
        assert got in ("Kiberxavfsizlik", "Kompyuter injiniringi"), typed
    assert await resolve_faculty_name(db_session, U, "KIF") == "Kompyuter injiniringi"
    assert await resolve_faculty_name(db_session, U, "Kiber") == "Kiberxavfsizlik"

    # AI "KIF = Kiberxavfsizlik" desa ham, bu qisqartma emas - ishonilmaydi, to'liq yozish so'raladi
    monkeypatch.setattr(name_validation, "get_ai_provider",
                        lambda: _FacultyAI({"match": "Kiberxavfsizlik", "complete": True, "canonical": "Kiberxavfsizlik"}))
    assert await resolve_faculty_name(db_session, U, "ABC") is None

    # Yangi, lekin to'liq nom - toza ko'rinishda qabul
    monkeypatch.setattr(name_validation, "get_ai_provider",
                        lambda: _FacultyAI({"match": None, "complete": True, "canonical": "Sanoat muhandisligi"}))
    assert await resolve_faculty_name(db_session, U, "sanoat muhandisligi") == "Sanoat muhandisligi"

    # Bo'lak/qisqartma va aniqlab bo'lmasa - None (to'liq yozing)
    monkeypatch.setattr(name_validation, "get_ai_provider",
                        lambda: _FacultyAI({"match": None, "complete": False, "canonical": None}))
    assert await resolve_faculty_name(db_session, U, "Telekom") is None
    assert await resolve_faculty_name(db_session, U, "IT") is None


def _png(w, h):
    import struct, zlib

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IEND", b"")


def test_photo_is_too_small_when_a_day_gets_too_few_pixels():
    from app.bot.album import too_small_for_lessons

    week = [{"day": d} for d in ("Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma")]
    assert too_small_for_lessons(_png(576, 1280), week)          # 115 px/kun: sizning xira rasmingiz
    assert not too_small_for_lessons(_png(1080, 2400), week)     # fayl qilib yuborilgan skrinshot: 216 px/kun
    assert not too_small_for_lessons(_png(1280, 736), week)      # aniq rasm: 256 px/kun
    assert not too_small_for_lessons(_png(576, 1280), week[:2])  # 2 kunlik kattalashtirilgan rasm - normal
    assert not too_small_for_lessons(b"not an image", week)      # o'lcham noma'lum - rad etilmaydi


@pytest.mark.asyncio
async def test_unclear_photo_is_not_saved_and_user_is_asked_for_a_sharper_one(db_session: AsyncSession, monkeypatch):
    from app.bot.handlers import user_menu
    from app.models.enums import SubmissionStatus
    from app.models.schedule import Schedule, ScheduleSubmission
    from app.models.university import Faculty, Group, University
    from sqlalchemy import select as sa_select

    univ = University(name="TATU")
    db_session.add(univ)
    await db_session.commit()
    fac = Faculty(name="KX", university_id=univ.id)
    db_session.add(fac)
    await db_session.commit()
    grp = Group(name="712-24", university_id=univ.id, faculty_id=fac.id)
    db_session.add(grp)
    await db_session.commit()
    student = User(telegram_id=9191, first_name="Aziz", role=UserRole.USER, university_id=univ.id,
                   faculty_id=fac.id, group_id=grp.id, language_code="uz")
    db_session.add(student)
    await db_session.commit()

    class WeekAI:
        async def extract_schedule_from_image(self, data, name="x.jpg"):
            from app.schemas.ai import ExtractedLessonItem, ExtractedScheduleResult
            days = ["Dushanba", "Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma"]
            return ExtractedScheduleResult(lessons=[
                ExtractedLessonItem(day=d, subject=f"Fan {i}", start_time=f"{8 + i}:00", end_time=f"{9 + i}:00", room="A-1", building="A")
                for i, d in enumerate(days)])

    monkeypatch.setattr("app.services.ai_service.get_ai_provider", lambda: WeekAI())
    monkeypatch.setattr(user_menu, "get_ai_provider", lambda: WeekAI())
    monkeypatch.setattr(type(user_menu.settings), "admin_id_list", property(lambda self: [1]))

    async def send(width, height):
        msg = _message("", 9191)
        msg.document = None
        loading = MagicMock(edit_text=AsyncMock())
        msg.answer = AsyncMock(return_value=loading)
        msg.bot.get_file = AsyncMock(return_value=MagicMock(file_path="p"))
        msg.bot.download_file = AsyncMock(return_value=MagicMock(read=lambda: _png(width, height)))
        await user_menu.process_schedule_input(msg, student, db_session, file_ids=["f1"])
        return msg, loading

    # Xira (576 px, 5 kun): saqlanmaydi, tiniq rasm so'raladi, adminga ham ketmaydi
    msg, loading = await send(576, 1280)
    assert (await db_session.execute(sa_select(Schedule))).scalars().first() is None
    sub = (await db_session.execute(sa_select(ScheduleSubmission))).scalars().first()
    assert sub.status == SubmissionStatus.NEEDS_CORRECTION and sub.image_file_id == "-"
    shown = loading.edit_text.call_args.args[0]
    assert "xira yoki uzoqdan" in shown and "saqlanmadi" in shown and "tiniq" in shown and "fayl" in shown
    assert "576×1280" in shown and "~115 px" in shown and "160 px" in shown      # aniq raqamlar keltirilgan
    msg.bot.send_message.assert_not_awaited()

    # Aniq rasm (1080 px, 5 kun): odatdagidek saqlanadi
    msg, loading = await send(1080, 2400)
    assert (await db_session.execute(sa_select(Schedule))).scalars().first() is not None


@pytest.mark.asyncio
async def test_first_schedule_of_a_group_is_decided_by_the_bot_instantly(db_session: AsyncSession, monkeypatch):
    """Ro'yxatdan o'tishda (guruhda jadval yo'q): aniq va to'liq jadval admin kutmasdan saqlanadi"""
    from app.bot.handlers import user_menu
    from app.models.enums import SubmissionStatus
    from app.models.schedule import ScheduleSubmission
    from app.models.university import Faculty, Group, University
    from sqlalchemy import select as sa_select

    univ = University(name="TATU")
    db_session.add(univ)
    await db_session.commit()
    fac = Faculty(name="KX", university_id=univ.id)
    db_session.add(fac)
    await db_session.commit()
    grp = Group(name="712-24", university_id=univ.id, faculty_id=fac.id)
    db_session.add(grp)
    await db_session.commit()
    student = User(telegram_id=5151, first_name="Yangi", role=UserRole.USER, university_id=univ.id,
                   faculty_id=fac.id, group_id=grp.id, language_code="uz")
    db_session.add(student)
    await db_session.commit()

    class RealAI:
        async def extract_schedule_from_text(self, text):
            from app.schemas.ai import ExtractedLessonItem, ExtractedScheduleResult
            days = ["Dushanba", "Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma"]
            return ExtractedScheduleResult(lessons=[
                ExtractedLessonItem(day=d, subject=f"Fan {i}", start_time=f"{8 + i}:00", end_time=f"{9 + i}:00", room="A-1", building="A")
                for i, d in enumerate(days)])

    monkeypatch.setattr("app.services.ai_service.get_ai_provider", lambda: RealAI())
    monkeypatch.setattr(user_menu, "get_ai_provider", lambda: RealAI())
    monkeypatch.setattr(type(user_menu.settings), "admin_id_list", property(lambda self: [1]))

    msg = _message("jadval", 5151)
    msg.document = None
    msg.answer = AsyncMock(return_value=MagicMock(edit_text=AsyncMock()))
    await user_menu.process_schedule_input(msg, student, db_session, schedule_text="x")
    sub = (await db_session.execute(sa_select(ScheduleSubmission))).scalars().first()
    assert sub.status == SubmissionStatus.APPROVED

    # AI o'zi tasdiqlagan bo'lsa ham admin ma'lumot oladi: kim yubordi, "Saqlandi", fanlar va darslar soni
    info = [c for c in msg.bot.send_message.await_args_list if (c.args and c.args[0] == 1) or c.kwargs.get("chat_id") == 1]
    assert info, "admin xabar olmadi"
    text = info[0].args[1] if len(info[0].args) > 1 else info[0].kwargs.get("text")
    assert "Saqlandi" in text and "Yangi" in text and "6 ta dars" in text
    assert info[0].kwargs.get("reply_markup") is None          # faqat ma'lumot - tugma yo'q


def test_the_four_unclear_photos_from_students_are_all_rejected_with_numbers():
    """Haqiqiy talaba rasmlari o'lchamlari: 576x1280, 720x451, 720x590, 720x560 (5 kun) - hammasi rad"""
    from app.bot.album import small_image_details

    week = [{"day": d} for d in ("Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma")]
    for w, h, per_day in [(576, 1280, 115), (720, 451, 144), (720, 590, 144), (720, 560, 144)]:
        details = small_image_details(_png(w, h), week)
        assert details == {"w": w, "h": h, "days": 5, "pd": per_day, "min": 160}
    assert small_image_details(_png(1280, 736), week) is None     # aniq rasm: 256 px/kun
    assert small_image_details(_png(1080, 2400), week) is None    # fayl qilib yuborilgan skrinshot: 216 px/kun
