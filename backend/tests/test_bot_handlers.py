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
        language_chosen=True,
    )
    mock_msg = make_mock_message("/start", 12345)
    mock_state = AsyncMock()

    await handle_start(mock_msg, current_user=student_user, state=mock_state)

    mock_msg.answer.assert_called_once()
    args, kwargs = mock_msg.answer.call_args
    # Javob matnida talabaga xush kelibsiz so'zlari borligini tekshirish
    assert "Salom, Aziz" in args[0]
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
        language_chosen=True,
    )
    mock_msg = make_mock_message("/start", 99999)
    mock_state = AsyncMock()

    await handle_start(mock_msg, current_user=admin_user, state=mock_state)

    mock_msg.answer.assert_called_once()
    args, kwargs = mock_msg.answer.call_args
    assert "Salom, Adminbek" in args[0]
    assert "administrator" in args[0]


@pytest.mark.asyncio
async def test_start_handler_triggers_registration_when_no_group():
    new_user = User(
        id=3,
        telegram_id=55555,
        first_name="Yangi",
        role=UserRole.USER,
        is_active=True,
        group_id=None,
        language_chosen=True,
    )
    mock_msg = make_mock_message("/start", 55555)
    mock_state = AsyncMock()

    await handle_start(mock_msg, current_user=new_user, state=mock_state)

    # Faqat bitta qisqa "Tanlang:" xabari va ikkita tugma: Talaba / O'qituvchi
    assert mock_msg.answer.call_count == 1
    role_call = mock_msg.answer.call_args_list[0]
    assert role_call.args[0] == "Tanlang:"
    buttons = [b.callback_data for row in role_call.kwargs["reply_markup"].inline_keyboard for b in row]
    assert buttons == ["role_student", "role_teacher"]


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
    assert "Statistika" in args[0]
    assert "Universitetlar" in args[0] and "Fanlar" in args[0]


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


@pytest.mark.parametrize(
    "raw, name, code",
    [
        ("Axborot xavfsizligi auditi (4 kr)-INS001", "Axborot xavfsizligi auditi", "INS001"),
        ("Axborot xavfsizligi auditi (4 kr)-INS001-3", "Axborot xavfsizligi auditi", "INS001"),
        ("Tarmoq havfsizligi/-NWS001", "Tarmoq havfsizligi", "NWS001"),
        ("Foydalanishlarni boshqarish (M)-ACC001-3", "Foydalanishlarni boshqarish", "ACC001"),
        ("Oliy matematika", "Oliy matematika", None),
    ],
)
def test_subject_variants_are_one_subject(raw, name, code):
    from app.services.schedule_service import normalize_subject_name

    assert normalize_subject_name(raw) == (name, code)


@pytest.mark.asyncio
async def test_rejecting_submission_notifies_student_once(db_session: AsyncSession):
    from app.bot.handlers.admin_menu import handle_reject_submission_callback
    from app.models.enums import SubmissionStatus
    from app.models.schedule import ScheduleSubmission
    from app.models.university import University

    univ = University(name="TATU")
    student = User(telegram_id=501, first_name="T", role=UserRole.USER, is_active=True)
    admin = User(telegram_id=502, first_name="A", role=UserRole.ADMIN, is_active=True)
    db_session.add_all([univ, student, admin])
    await db_session.commit()
    sub = ScheduleSubmission(
        user_id=student.id, university_id=univ.id, image_file_id="f",
        status=SubmissionStatus.ADMIN_REVIEW,
    )
    db_session.add(sub)
    await db_session.commit()

    query = MagicMock()
    query.data = f"reject_sub_{sub.id}"
    query.answer = AsyncMock()
    query.bot.send_message = AsyncMock()
    query.message.photo = [MagicMock()]
    query.message.edit_caption = AsyncMock()

    await handle_reject_submission_callback(query, admin, db_session)
    await handle_reject_submission_callback(query, admin, db_session)

    assert sub.status == SubmissionStatus.REJECTED
    query.message.edit_caption.assert_awaited_once()
    query.bot.send_message.assert_awaited_once()
    assert query.bot.send_message.call_args.kwargs["chat_id"] == 501


@pytest.mark.asyncio
async def test_first_start_asks_language_before_anything_else():
    new_user = User(id=9, telegram_id=9001, first_name="Yangi", role=UserRole.USER, is_active=True)
    mock_msg = make_mock_message("/start", 9001)
    mock_state = AsyncMock()

    await handle_start(mock_msg, current_user=new_user, state=mock_state)

    mock_msg.answer.assert_called_once()
    assert "Выберите язык" in mock_msg.answer.call_args.args[0]
    mock_state.set_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_choosing_russian_saves_it_and_continues_in_russian(db_session: AsyncSession):
    from app.bot.handlers.start import handle_language_choice

    user = User(telegram_id=9002, first_name="Иван", role=UserRole.USER, is_active=True, language_code="en")
    db_session.add(user)
    await db_session.commit()

    query = MagicMock()
    query.data = "lang_ru"
    query.answer = AsyncMock()
    query.message.edit_text = AsyncMock()
    query.message.answer = AsyncMock()

    await handle_language_choice(query, AsyncMock(), user, db_session)

    assert user.language_code == "ru"
    assert user.language_chosen is True
    texts = [call.args[0] for call in query.message.answer.call_args_list]
    # Til tanlangach darhol qisqa "Выберите:" va rol tugmalari (ortiqcha salom matnisiz)
    assert texts == ["Выберите:"]


@pytest.mark.parametrize("typed", ["712-24", "712_24", "712 24", "712/24", " 712-24 guruh", "712.24"])
def test_group_names_written_differently_are_the_same_group(typed):
    from app.services.university_service import group_key, pretty_group_name

    assert group_key(typed) == group_key("712-24")
    assert pretty_group_name(typed) == "712-24"


async def test_university_matches_abbreviation_and_typos(db_session: AsyncSession):
    from app.models.university import University
    from app.services.university_service import UniversityService

    tatu = University(name="Toshkent Axborot Texnologiyalari Universiteti")
    db_session.add(tatu)
    await db_session.commit()

    for typed in ["TATU", "tatu", "Toshkent axborot texnologiyalar univesiteti"]:
        found = await UniversityService.match_university(db_session, typed)
        assert found is not None and found.id == tatu.id, typed
    assert await UniversityService.match_university(db_session, "Samarqand davlat universiteti") is None


async def test_registration_asks_only_university_and_group_and_reuses_group(db_session: AsyncSession):
    from app.services.university_service import UniversityService

    u1, g1 = await UniversityService.register_university_and_group(db_session, "TATU", "712_24")
    u2, g2 = await UniversityService.register_university_and_group(db_session, "tatu", "712-24")
    assert (u1.id, g1.id) == (u2.id, g2.id)
    assert g1.name == "712-24"


def test_every_text_exists_in_both_languages():
    from app.bot.i18n import LANGUAGES, TEXTS

    for key, values in TEXTS.items():
        assert set(values) == set(LANGUAGES), key


def test_every_menu_button_has_a_handler_for_both_languages():
    from app.bot.i18n import labels
    from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard

    known = set()
    for key in (
        "btn_today", "btn_tomorrow", "btn_week", "btn_reminder", "btn_send", "btn_profile", "btn_language", "btn_contact",
        "btn_new_shots", "btn_stats", "btn_groups", "btn_users", "btn_announce", "btn_student_view", "btn_teachers",
        "btn_admin_site",
    ):
        known |= labels(key)

    for lang in ("uz", "ru"):
        for keyboard in (get_user_main_keyboard(lang), get_admin_main_keyboard(lang)):
            for row in keyboard.keyboard:
                for button in row:
                    assert button.text in known


@pytest.mark.parametrize(
    "minutes, lang, expected",
    [
        (30, "uz", "30 daqiqa (yarim soat)"),
        (30, "ru", "30 минут (полчаса)"),
        (21, "ru", "21 минуту"),
        (2, "ru", "2 минуты"),
        (60, "ru", "60 минут (1 ч)"),
        (90, "ru", "90 минут (1 ч 30 мин)"),
    ],
)
def test_minutes_read_naturally(minutes, lang, expected):
    from app.bot.i18n import format_minutes

    assert format_minutes(minutes, lang) == expected


def test_russian_counts_use_correct_plural():
    from app.bot.i18n import format_counts

    assert format_counts(6, 15, "ru") == "6 предметов · 15 занятий"
    assert format_counts(1, 2, "ru") == "1 предмет · 2 занятия"


def test_schedule_issues_tells_student_what_is_wrong():
    from app.bot.text_utils import schedule_issues

    lessons = [
        {"day": "Dushanba", "subject": "Matematika", "start_time": "08:00", "end_time": "09:30", "room": "327", "building": None, "week_parity": "ALL"},
        {"day": "Dushanba", "subject": "Fizika", "start_time": "09:00", "end_time": "10:20", "room": None, "building": None, "week_parity": "ALL"},
        {"day": "Payshanbe?", "subject": "Kimyo", "start_time": "11:00", "end_time": "", "room": "A-1", "building": "A", "week_parity": "ALL"},
    ]
    text = "\n".join(schedule_issues(lessons, "uz"))
    assert "bino aniqlanmadi" in text
    assert "xona ko'rsatilmagan" in text
    assert "kun aniqlanmadi" in text and "vaqt to'liq emas" in text
    assert "ustma-ust" in text


def test_schedule_issues_groups_many_missing_buildings_into_one_line():
    from app.bot.text_utils import schedule_issues

    lessons = [
        {"day": "Dushanba", "subject": f"Fan {i}", "start_time": f"{8 + i * 2:02d}:00", "end_time": f"{9 + i * 2:02d}:00", "room": str(400 + i), "building": None, "week_parity": "ALL"}
        for i in range(5)
    ]
    issues = schedule_issues(lessons, "uz")
    assert len(issues) == 1 and "5 ta darsda bino aniqlanmadi" in issues[0]


async def test_registration_with_faculty_matches_typos_and_keeps_one_group(db_session: AsyncSession):
    from app.models.university import Faculty
    from app.services.university_service import UniversityService

    u1, g1 = await UniversityService.register_university_and_group(db_session, "TATU", "712-24", faculty_name="Kiberxavfsizlik")
    u2, g2 = await UniversityService.register_university_and_group(db_session, "tatu", "712_24", faculty_name="kiberxafvsizlik")
    assert g1.id == g2.id
    faculty = await db_session.get(Faculty, g1.faculty_id)
    assert faculty.name == "Kiberxavfsizlik"


async def test_group_without_faculty_moves_to_named_faculty(db_session: AsyncSession):
    from app.models.university import Faculty
    from app.services.university_service import GENERAL_FACULTY_NAME, UniversityService

    _, g = await UniversityService.register_university_and_group(db_session, "TATU", "732-24")
    assert (await db_session.get(Faculty, g.faculty_id)).name == GENERAL_FACULTY_NAME
    _, g2 = await UniversityService.register_university_and_group(db_session, "TATU", "732 24", faculty_name="Kiberxavfsizlik")
    assert g2.id == g.id
    assert (await db_session.get(Faculty, g2.faculty_id)).name == "Kiberxavfsizlik"


@pytest.mark.parametrize(
    "lang, with_year, expected",
    [
        ("uz", False, "9-noyabr, Dushanba"),
        ("uz", True, "9-noyabr 2026, Dushanba"),
        ("ru", True, "9 ноября 2026, Понедельник"),
    ],
)
def test_format_date(lang, with_year, expected):
    from datetime import date
    from app.bot.text_utils import format_date

    assert format_date(date(2026, 11, 9), lang, with_year=with_year) == expected


def test_reminder_shows_lesson_date():
    from datetime import date
    from types import SimpleNamespace
    from app.bot.text_utils import format_reminder

    sched = SimpleNamespace(
        subject=SimpleNamespace(name="Matematika"), start_time="08:00", end_time="09:30", room=None, teacher=None
    )
    text = format_reminder(sched, 15, "uz", lesson_date=date(2026, 11, 9))
    assert "📅 9-noyabr 2026, Dushanba" in text
    assert "08:00–09:30" in text


async def test_russian_university_abbreviation_matches_tatu(db_session: AsyncSession):
    from app.models.university import University
    from app.services.university_service import UniversityService

    tatu = University(name="Toshkent Axborot Texnologiyalari Universiteti")
    db_session.add(tatu)
    await db_session.commit()
    for typed in ["ТУИТ", "TUIT", "туит"]:
        found = await UniversityService.match_university(db_session, typed)
        assert found is not None and found.id == tatu.id, typed


async def test_unknown_message_gets_menu_hint():
    from app.bot.handlers.user_menu import handle_unknown_message

    user = User(id=5, telegram_id=5005, first_name="T", role=UserRole.USER, group_id=1, language_code="uz")
    msg = make_mock_message("salom", 5005)
    await handle_unknown_message(msg, current_user=user, session=AsyncMock(), state=AsyncMock())
    assert "Tushunmadim" in msg.answer.call_args.args[0]


async def test_university_spelling_variants_are_one_university(db_session: AsyncSession):
    from app.services.university_service import UniversityService

    u1, _ = await UniversityService.register_university_and_group(db_session, "tatu", "712-24", faculty_name="kiberxavfsizlik")
    assert u1.name == "TATU"
    for typed in ["Tatu", "TATU", " tatu ", "Toshkent axborot texnologiyalari universiteti", "ТУИТ"]:
        u, _ = await UniversityService.register_university_and_group(db_session, typed, "712-24")
        assert u.id == u1.id, typed
    from app.models.university import Faculty
    from sqlalchemy import select as sa_select
    names = (await db_session.execute(sa_select(Faculty.name))).scalars().all()
    assert "Kiberxavfsizlik" in names


@pytest.mark.asyncio
async def test_schedule_change_waits_for_admin_and_old_schedule_stays(db_session: AsyncSession, monkeypatch):
    """Mavjud jadvalni O'ZGARTIRISH admin tasdig'ini kutadi: eski jadval o'zgarmaydi, guruhga xabar ketmaydi"""
    from app.bot.handlers import user_menu
    from app.models.enums import SubmissionStatus
    from app.models.schedule import Schedule, ScheduleSubmission
    from app.models.university import Faculty, Group, Subject, University
    from sqlalchemy import select as sa_select

    univ = University(name="TATU")
    db_session.add(univ)
    await db_session.commit()
    fac = Faculty(name="KX", university_id=univ.id)
    db_session.add(fac)
    await db_session.commit()
    mine = Group(name="712-24", university_id=univ.id, faculty_id=fac.id)
    other = Group(name="732-24", university_id=univ.id, faculty_id=fac.id)
    old_subject = Subject(name="Eski fan", university_id=univ.id)
    db_session.add_all([mine, other, old_subject])
    await db_session.commit()
    author = User(telegram_id=4242, first_name="Muallif", role=UserRole.USER, university_id=univ.id,
                  faculty_id=fac.id, group_id=mine.id, language_code="uz")
    mate = User(telegram_id=4243, first_name="Guruhdosh", role=UserRole.USER, group_id=mine.id, language_code="uz")
    stranger = User(telegram_id=4244, first_name="Boshqa", role=UserRole.USER, group_id=other.id, language_code="uz")
    db_session.add_all([author, mate, stranger])
    await db_session.commit()
    from app.models.enums import DayOfWeek, LessonType
    db_session.add(Schedule(university_id=univ.id, group_id=mine.id, subject_id=old_subject.id, day_of_week=DayOfWeek.MONDAY,
                            start_time="08:00", end_time="09:00", lesson_type=LessonType.LECTURE))
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

    msg = make_mock_message("Dushanba 08:00 ...", 4242)
    msg.answer = AsyncMock(return_value=MagicMock(edit_text=AsyncMock()))
    msg.bot = MagicMock(send_message=AsyncMock(), send_chat_action=AsyncMock(), send_photo=AsyncMock())
    msg.document = None
    await user_menu.process_schedule_input(msg, author, db_session, schedule_text=msg.text, change_request=True)

    sub = (await db_session.execute(sa_select(ScheduleSubmission))).scalars().first()
    assert sub.status == SubmissionStatus.ADMIN_REVIEW                   # admin tasdig'i kutilyapti
    from app.services.schedule_service import ScheduleService
    names = {x.subject.name for x in await ScheduleService.get_schedules(db_session, group_id=mine.id)}
    assert names == {"Eski fan"}                                         # eski jadval o'zgarmadi
    sent = msg.bot.send_message.await_args_list
    to_admin = [c for c in sent if c.args and c.args[0] == 1 or c.kwargs.get("chat_id") == 1]
    assert to_admin and to_admin[0].kwargs.get("reply_markup") is not None   # adminga tasdiqlash tugmalari bilan
    notified = {c.kwargs.get("chat_id") for c in sent}
    assert 4243 not in notified and 4244 not in notified                 # guruhga xabar tasdiqdan keyin ketadi




async def test_admin_has_both_roles_student_mode_and_back():
    from app.bot.handlers.admin_menu import handle_switch_back_to_admin, handle_switch_to_student_view
    from app.bot.keyboards.reply import get_admin_main_keyboard

    admin_kb = [b.text for row in get_admin_main_keyboard("uz").keyboard for b in row]
    assert "🎓 Talaba rejimi" in admin_kb

    admin = User(id=9, telegram_id=9009, first_name="A", role=UserRole.ADMIN, language_code="uz")
    msg = make_mock_message("🎓 Talaba rejimi", 9009)
    await handle_switch_to_student_view(msg, current_user=admin)
    student_kb = [b.text for row in msg.answer.call_args.kwargs["reply_markup"].keyboard for b in row]
    assert "📅 Dars jadvali" in student_kb and "🛠 Admin paneliga qaytish" in student_kb

    msg = make_mock_message("🛠 Admin paneliga qaytish", 9009)
    await handle_switch_back_to_admin(msg, current_user=admin)
    back_kb = [b.text for row in msg.answer.call_args.kwargs["reply_markup"].keyboard for b in row]
    assert "📈 Statistika" in back_kb
