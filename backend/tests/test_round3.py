from datetime import date
from unittest.mock import AsyncMock, MagicMock
import pytest
from aiogram.types import CallbackQuery, Chat, Message, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.i18n import LANGUAGES, TEXTS, lang_of, t
from app.models.enums import DayOfWeek, LessonType, UserRole
from app.models.schedule import Schedule
from app.models.university import Faculty, Group, Subject, University
from app.models.user import User


def _msg(text="", uid=1):
    m = MagicMock(spec=Message)
    m.text = text
    m.chat = MagicMock(spec=Chat)
    m.chat.id = uid
    m.from_user = MagicMock(spec=TgUser)
    m.answer = AsyncMock()
    return m


def test_english_is_complete_and_formats():
    assert "en" in LANGUAGES
    assert all(set(v) == set(LANGUAGES) for v in TEXTS.values())
    from app.bot.i18n import format_minutes, format_counts
    from app.bot.text_utils import format_date

    assert lang_of(User(language_code="en-US")) == "en" and lang_of(User(language_code="ru")) == "ru"
    assert format_minutes(30, "en") == "30 minutes (half an hour)"
    assert format_counts(1, 2, "en") == "1 subject · 2 lessons"
    assert format_date(date(2026, 11, 9), "en", with_year=True) == "Monday, November 9 2026"
    assert t("en", "btn_week") == "📅 Timetable"


async def _seed(db: AsyncSession):
    univ = University(name="TATU")
    db.add(univ)
    await db.commit()
    fac = Faculty(name="Kiberxavfsizlik", university_id=univ.id)
    db.add(fac)
    await db.commit()
    groups = [Group(name=n, university_id=univ.id, faculty_id=fac.id) for n in ("712-24", "710-24", "732-24")]
    subjects = [Subject(name=n, university_id=univ.id) for n in ("A", "B", "C", "D")]
    db.add_all(groups + subjects)
    await db.commit()
    # 712-24 va 710-24: bir xil jadval; 732-24: boshqacha
    for g in groups[:2]:
        for i, s in enumerate(subjects[:3]):
            db.add(Schedule(university_id=univ.id, group_id=g.id, subject_id=s.id, day_of_week=DayOfWeek.MONDAY,
                            start_time=f"{8 + i * 2:02d}:00", end_time=f"{9 + i * 2:02d}:00", lesson_type=LessonType.LECTURE))
    db.add(Schedule(university_id=univ.id, group_id=groups[2].id, subject_id=subjects[3].id, day_of_week=DayOfWeek.FRIDAY,
                    start_time="08:00", end_time="09:00", lesson_type=LessonType.LECTURE))
    await db.commit()
    return univ, groups


@pytest.mark.asyncio
async def test_admin_groups_report_lists_faculties_schedule_status_and_lookalikes(db_session: AsyncSession):
    from app.bot.handlers.admin_menu import build_groups_report

    await _seed(db_session)
    pages = await build_groups_report(db_session, "uz")
    text = "\n".join(pages)
    assert "TATU" in text and "Kiberxavfsizlik" in text
    assert "✅ 712-24" in text and "✅ 732-24" in text
    assert "⚠️ 710-24" in text and "⚠️ 712-24" in text       # bir xil jadvalli ikki guruh belgilandi
    assert text.count("⚠️") >= 2 and "732-24 —" in text


@pytest.mark.asyncio
async def test_lookalike_schedule_is_detected_for_another_group(db_session: AsyncSession):
    from app.bot.handlers.user_menu import _lookalike_group

    univ, groups = await _seed(db_session)
    user = User(telegram_id=77, first_name="F", role=UserRole.USER, group_id=groups[2].id, university_id=univ.id)
    lessons = [{"day": "Dushanba", "subject": s, "start_time": f"{8 + i * 2:02d}:00"} for i, s in enumerate(("A", "B", "C"))]
    assert await _lookalike_group(db_session, user, lessons) in ("712-24", "710-24")
    other = [{"day": "Seshanba", "subject": s, "start_time": "10:00"} for s in ("X", "Y", "Z")]
    assert await _lookalike_group(db_session, user, other) is None


@pytest.mark.asyncio
async def test_reminder_can_be_switched_off_and_on(db_session: AsyncSession):
    from app.bot.handlers.user_menu import handle_reminder_toggle
    from app.services.schedule_service import ScheduleService

    user = User(telegram_id=88, first_name="R", role=UserRole.USER, language_code="uz")
    db_session.add(user)
    await db_session.commit()
    for data, expected in (("remind_off", False), ("remind_on", True)):
        q = MagicMock(spec=CallbackQuery)
        q.data = data
        q.answer = AsyncMock()
        q.message = MagicMock(edit_text=AsyncMock())
        await handle_reminder_toggle(q, AsyncMock(), user, db_session)
        setting = await ScheduleService.get_or_create_reminder_setting(db_session, user.id)
        assert setting.is_enabled is expected
    from app.bot.keyboards.inline import reminder_minutes_keyboard
    off_kb = [b.callback_data for row in reminder_minutes_keyboard("uz", enabled=False).inline_keyboard for b in row]
    assert off_kb[-1] == "remind_on"


@pytest.mark.asyncio
async def test_announcement_goes_only_to_chosen_group(db_session: AsyncSession):
    from app.bot.handlers.admin_menu import _announcement_recipients

    univ, groups = await _seed(db_session)
    db_session.add_all([
        User(telegram_id=1, first_name="a", role=UserRole.USER, group_id=groups[0].id),
        User(telegram_id=2, first_name="b", role=UserRole.USER, group_id=groups[0].id),
        User(telegram_id=3, first_name="c", role=UserRole.USER, group_id=groups[1].id),
    ])
    await db_session.commit()
    only = await _announcement_recipients(db_session, f"g{groups[0].id}")
    assert sorted(u.telegram_id for u in only) == [1, 2]
    assert len(await _announcement_recipients(db_session, "all")) == 3
