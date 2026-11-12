"""Mening rejalarim: AI javobini tekshirish, saqlash, eslatmalar, "Boshqa" foydalanuvchi va uning hisobi"""
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.bot.handlers import plans as plan_handlers
from app.bot.handlers.admin_menu import collect_user_counts
from app.models.enums import UserRole
from app.models.task import PersonalEvent
from app.models.user import User
from app.services import admin_service
from app.services import plan_service
from app.services.plan_service import ParsedEvent, PlanService, reminder_due, to_utc_naive, validate_items
from tests.conftest import TestingSessionLocal


def make_user(db, tg=7001, **kw) -> User:
    user = User(telegram_id=tg, first_name="Ali", role=UserRole.USER, is_active=True, language_chosen=True, **kw)
    db.add(user)
    return user


class _State:
    def __init__(self):
        self.data, self.state, self.cleared = {}, None, False

    async def get_data(self):
        return self.data

    async def update_data(self, **kw):
        self.data.update(kw)

    async def set_state(self, s):
        self.state = s

    async def clear(self):
        self.cleared, self.data, self.state = True, {}, None


def _message(text=None):
    m = MagicMock()
    m.text, m.caption, m.photo, m.document = text, None, None, None
    m.answer = AsyncMock()
    return m


def test_ai_answer_is_checked_before_anything_is_saved():
    today = date(2026, 11, 12)
    items = [
        {"title": "Uchrashuv", "date": "2026-11-15", "time": "14:00", "place": "Dekanat"},
        {"title": "O'tgan voqea", "date": "2026-11-01", "time": "10:00"},          # o'tib ketgan
        {"title": "", "date": "2026-11-16"},                                         # nomsiz
        {"title": "Sanasiz"},                                                        # sana yo'q
        {"title": "Yomon sana", "date": "2026-13-45"},
        {"title": "Juda uzoq", "date": "2040-01-01"},
        {"title": "Kun tartibi", "date": "2026-11-13", "time": "soat nechida"},      # vaqt o'qilmadi -> vaqtsiz
        {"title": "uchrashuv", "date": "2026-11-15", "time": "14:00"},               # takror
        "axlat",
    ]
    events = validate_items(items, today)
    assert [(e.title, e.day.isoformat(), e.at.strftime("%H:%M") if e.at else None) for e in events] == [
        ("Kun tartibi", "2026-11-13", None), ("Uchrashuv", "2026-11-15", "14:00")]
    assert events[1].place == "Dekanat"
    assert validate_items({"events": [{"title": "X", "date": "2026-11-12"}]}, today)[0].title == "X"  # bugun ham bo'ladi
    assert validate_items(None, today) == []


@pytest.mark.asyncio
async def test_events_are_saved_once_listed_by_time_and_only_the_owner_can_delete(db_session):
    a, b = make_user(db_session, 7001), make_user(db_session, 7002)
    await db_session.commit()
    soon = date.today() + timedelta(days=3)
    evs = [ParsedEvent("Imtihon", soon, None), ParsedEvent("Uchrashuv", soon, datetime.strptime("14:00", "%H:%M").time(), "Dekanat")]
    assert await PlanService.add_events(db_session, a, evs) == 2
    assert await PlanService.add_events(db_session, a, evs) == 0   # takror yozilmaydi
    rows = await PlanService.upcoming(db_session, a)
    assert [r.title for r in rows] == ["Imtihon", "Uchrashuv"]      # 09:00 (vaqtsiz) 14:00 dan oldin
    assert rows[0].has_time is False and rows[1].place == "Dekanat"
    assert await PlanService.upcoming(db_session, b) == []
    assert await PlanService.delete(db_session, b, rows[0].id) is False   # boshqaning rejasi
    assert await PlanService.delete(db_session, a, rows[0].id) is True
    assert [r.title for r in await PlanService.upcoming(db_session, a)] == ["Uchrashuv"]


def _event(start, has_time=True, **kw):
    return PersonalEvent(user_id=1, title="X", event_type="plan", start_time=start, has_time=has_time,
                         remind1_sent=kw.get("r1", False), remind2_sent=kw.get("r2", False))


def test_reminders_come_on_time_and_never_say_tomorrow_when_it_is_not():
    start = datetime(2026, 11, 20, 9, 0)
    ev = _event(start)
    assert reminder_due(ev, start - timedelta(days=2)) is None
    assert reminder_due(ev, start - timedelta(hours=23, minutes=30)) == "day"
    assert reminder_due(ev, start - timedelta(hours=10)) is None                 # kunlik eslatma oynasi o'tdi
    assert reminder_due(ev, start - timedelta(minutes=50)) == "soon"
    assert reminder_due(ev, start + timedelta(minutes=5)) is None                # boshlanib bo'ldi
    assert reminder_due(_event(start, r1=True), start - timedelta(hours=23, minutes=30)) is None
    assert reminder_due(_event(start, r1=True, r2=True), start - timedelta(minutes=50)) is None
    # voqea 3 soat qolganda qo'shildi: "ertaga" demaydi, 1 soat qolganda eslatadi
    assert reminder_due(ev, start - timedelta(hours=3)) is None
    # vaqtsiz voqea: kun oldin va o'sha kuni ertalab
    day_only = _event(start, has_time=False)
    assert reminder_due(day_only, start - timedelta(hours=23, minutes=30)) == "day"
    assert reminder_due(day_only, start + timedelta(minutes=1)) == "soon"


@pytest.mark.asyncio
async def test_reminder_job_sends_once_with_the_event_details(monkeypatch):
    from app.scheduler import jobs

    async with TestingSessionLocal() as s:
        user = make_user(s, 7100)
        await s.commit()
        start = datetime.utcnow() + timedelta(minutes=50)
        s.add(PersonalEvent(user_id=user.id, title="Dekanat uchrashuvi", event_type="plan", start_time=start,
                            has_time=True, place="2-bino"))
        await s.commit()
    sent = []
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=lambda **kw: sent.append(kw))
    monkeypatch.setattr(jobs, "get_bot", lambda: bot)
    monkeypatch.setattr(jobs, "AsyncSessionLocal", TestingSessionLocal)
    await jobs.check_and_send_event_reminders()
    await jobs.check_and_send_event_reminders()   # ikkinchi marta yuborilmaydi
    assert len(sent) == 1 and sent[0]["chat_id"] == 7100
    assert "Dekanat uchrashuvi" in sent[0]["text"] and "2-bino" in sent[0]["text"] and "1 soatdan keyin" in sent[0]["text"]


@pytest.mark.asyncio
async def test_other_user_sends_text_reads_it_and_saves_after_confirmation(db_session, monkeypatch):
    user = make_user(db_session, 7200, plan_only=True)
    await db_session.commit()
    day = date.today() + timedelta(days=5)
    monkeypatch.setattr(PlanService, "read", AsyncMock(return_value=[ParsedEvent("Yig'ilish", day, datetime.strptime("10:30", "%H:%M").time())]))
    state, msg = _State(), _message("5 kundan keyin 10:30 yig'ilish")
    await plan_handlers.plan_only_text(msg, state, user)            # tugma bosmasdan yozildi
    assert "plan_events" in state.data and "Yig'ilish" in msg.answer.await_args.args[0]
    assert (await db_session.execute(select(PersonalEvent))).scalars().first() is None   # tasdiqlanmaguncha saqlanmaydi

    query = MagicMock()
    query.answer, query.message = AsyncMock(), MagicMock()
    query.message.edit_reply_markup, query.message.answer = AsyncMock(), AsyncMock()
    await plan_handlers.handle_plan_save(query, state, user, db_session)
    saved = (await db_session.execute(select(PersonalEvent))).scalars().all()
    assert [(e.title, e.has_time) for e in saved] == [("Yig'ilish", True)]
    assert state.cleared


@pytest.mark.asyncio
async def test_unreadable_input_is_explained_and_daily_limit_protects_the_ai(db_session, monkeypatch):
    user = make_user(db_session, 7300, plan_only=True)
    await db_session.commit()
    plan_service._AI_USES.clear()
    monkeypatch.setattr(PlanService, "read", AsyncMock(return_value=[]))
    state = _State()
    msg = _message("salom")
    await plan_handlers._read_and_preview(msg, state, user, None, "salom")
    assert "topilmadi" in msg.answer.await_args.args[0] and "plan_events" not in state.data

    monkeypatch.setattr(PlanService, "read", AsyncMock(side_effect=RuntimeError("AI band")))
    msg2 = _message("x")
    await plan_handlers._read_and_preview(msg2, state, user, None, "x")
    assert "o'qib bo'lmadi" in msg2.answer.await_args.args[0]

    plan_service._AI_USES[user.id] = (plan_service.local_now().date().isoformat(), plan_service.DAILY_AI_LIMIT)
    reader = AsyncMock(return_value=[])
    monkeypatch.setattr(PlanService, "read", reader)
    msg3 = _message("y")
    await plan_handlers._read_and_preview(msg3, state, user, None, "y")
    reader.assert_not_awaited()                                    # limit tugagach AI chaqirilmaydi
    assert "limit" in msg3.answer.await_args.args[0].lower()
    plan_service._AI_USES.clear()


@pytest.mark.asyncio
async def test_choosing_other_marks_the_user_and_registering_later_clears_it(db_session):
    user = make_user(db_session, 7400)
    await db_session.commit()
    query = MagicMock()
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.edit_reply_markup, query.message.answer = AsyncMock(), AsyncMock()
    await plan_handlers.choose_other(query, _State(), user, db_session)
    assert user.plan_only is True
    texts = [c.args[0] for c in query.message.answer.await_args_list]
    assert any("Tayyor" in x for x in texts)


@pytest.mark.asyncio
async def test_other_users_are_their_own_group_in_the_counts_filters_and_audiences(db_session):
    make_user(db_session, 7500)                       # ro'yxatdan o'tishni tugatmagan
    make_user(db_session, 7501, plan_only=True)       # "Boshqa"
    make_user(db_session, 7502, plan_only=True)
    await db_session.commit()
    bot = await collect_user_counts(db_session)
    site = await admin_service.user_counts(db_session, 0)
    for key in ("total", "teachers", "pending", "students", "unregistered", "others"):
        assert site[key] == bot[key], key
    assert (site["total"], site["others"], site["unregistered"]) == (3, 2, 1)
    assert site["total"] == site["students"] + site["teachers"] + site["pending"] + site["others"] + site["unregistered"]

    other = await admin_service.list_users(db_session, 0, stage="other")
    nogr = await admin_service.list_users(db_session, 0, stage="nogr")
    assert other["total"] == 2 and {u["stage"] for u in other["items"]} == {"other"}
    assert nogr["total"] == 1 and nogr["items"][0]["stage"] == "nogr"
    counts = await admin_service.audience_counts(db_session, 0)
    assert counts["others"] == 2 and counts["nogr"] == 1 and counts["all"] == 3
