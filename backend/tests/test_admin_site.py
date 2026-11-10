"""Admin sayt: kirish himoyasi va ma'lumotlar bot bazasi bilan bir xil ekanini tekshiradi."""
import asyncio
import json
import time

import pytest
from sqlalchemy import select

from app.api.v1 import admin as admin_api
from app.core.config import settings
from app.core.telegram_auth import TelegramAuthError, sign_init_data, verify_init_data
from app.models.enums import DayOfWeek, SubmissionStatus, UserRole
from app.models.log import Announcement
from app.models.schedule import Schedule, ScheduleSubmission
from app.models.university import Faculty, Group, Subject, University
from app.models.user import User
from app.services import admin_service

TOKEN = "123456:TEST-TOKEN"
ADMIN_TG = 999888777


@pytest.fixture(autouse=True)
def bot_settings(monkeypatch):
    monkeypatch.setattr(settings, "BOT_TOKEN", TOKEN)
    monkeypatch.setattr(settings, "ADMIN_IDS_RAW", str(ADMIN_TG))


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))


@pytest.fixture
def fake_bot(monkeypatch):
    bot = FakeBot()
    monkeypatch.setattr(admin_api, "get_bot", lambda: bot)
    return bot


def init_for(user_id: int, age: int = 0, token: str = TOKEN) -> dict:
    data = sign_init_data({
        "auth_date": str(int(time.time()) - age),
        "user": json.dumps({"id": user_id, "first_name": "Jamshid", "username": "boss"}),
        "query_id": "AAE",
    }, token)
    return {"X-Telegram-Init-Data": data}


ADMIN = init_for(ADMIN_TG)


async def seed(db):
    """Universitet: 2 guruh (biri jadvalli), 4 talaba turli bosqichda, 2 so'rov"""
    uni = University(name="Toshkent Axborot Texnologiyalari Universiteti")
    other = University(name="FDU")
    db.add_all([uni, other])
    await db.flush()
    fac = Faculty(university_id=uni.id, name="Kiberxavfsizlik")
    db.add(fac)
    await db.flush()
    g1 = Group(university_id=uni.id, faculty_id=fac.id, name="712-24")
    g2 = Group(university_id=uni.id, faculty_id=fac.id, name="713-24")
    db.add_all([g1, g2])
    await db.flush()
    subj = Subject(university_id=uni.id, name="Hisob 1", code="MAT001")
    db.add(subj)
    await db.flush()
    db.add(Schedule(university_id=uni.id, group_id=g1.id, subject_id=subj.id, day_of_week=DayOfWeek.MONDAY,
                    start_time="08:00", end_time="09:20"))
    users = [
        User(telegram_id=1001, first_name="Madina", username="madina_r", language_code="uz", university_id=uni.id, faculty_id=fac.id, group_id=g1.id),
        User(telegram_id=1002, first_name="Sardor", language_code="ru", university_id=uni.id, faculty_id=fac.id, group_id=g2.id),
        User(telegram_id=1003, first_name="Aziz", language_code="uz", university_id=uni.id, faculty_id=fac.id, group_id=g2.id),
        User(telegram_id=1004, first_name="Nodira", language_code="en", university_id=uni.id),
        User(telegram_id=2001, first_name="Begona", language_code="uz", university_id=other.id),
        User(telegram_id=ADMIN_TG, first_name="Admin", role=UserRole.ADMIN, university_id=uni.id),
    ]
    db.add_all(users)
    await db.flush()
    lessons = [{"day": "Dushanba", "subject": "Hisob 1-MAT001", "start_time": "08:00", "end_time": "09:20",
                "building": "D", "room": "307", "teacher": None, "lesson_type": "LECTURE", "week_parity": "ALL"}]
    s_done = ScheduleSubmission(user_id=users[0].id, university_id=uni.id, group_id=g1.id, image_file_id="-",
                                status=SubmissionStatus.APPROVED, ai_extracted_json=json.dumps(lessons))
    s_open = ScheduleSubmission(user_id=users[1].id, university_id=uni.id, group_id=g2.id, image_file_id="x",
                                status=SubmissionStatus.ADMIN_REVIEW, ai_extracted_json=json.dumps(lessons))
    db.add_all([s_done, s_open])
    await db.commit()
    return {"uni": uni, "other": other, "g1": g1, "g2": g2, "users": users, "done": s_done, "open": s_open}


# ---------------- kirish himoyasi ----------------
def test_signature_roundtrip_and_tampering():
    header = init_for(ADMIN_TG)["X-Telegram-Init-Data"]
    assert verify_init_data(header, TOKEN)["id"] == ADMIN_TG
    with pytest.raises(TelegramAuthError):
        verify_init_data(header.replace("Jamshid", "Hacker"), TOKEN)
    with pytest.raises(TelegramAuthError):
        verify_init_data(header, "999:OTHER")


@pytest.mark.asyncio
async def test_access_is_closed_to_everyone_but_the_admin(async_client, db_session):
    await seed(db_session)
    assert (await async_client.get("/api/v1/admin/universities")).status_code == 401
    assert (await async_client.get("/api/v1/admin/universities", headers={"X-Telegram-Init-Data": "user=1&hash=abc"})).status_code == 401
    assert (await async_client.get("/api/v1/admin/universities", headers=init_for(1001))).status_code == 403
    assert (await async_client.get("/api/v1/admin/universities", headers=init_for(ADMIN_TG, age=3 * 86400))).status_code == 401
    assert (await async_client.get("/api/v1/admin/universities", headers=init_for(ADMIN_TG, token="1:OTHER"))).status_code == 401
    ok = await async_client.get("/api/v1/admin/universities", headers=ADMIN)
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_admin_page_is_served(async_client):
    r = await async_client.get("/admin")
    assert r.status_code == 200
    assert "Qulay Jadval" in r.text and "X-Telegram-Init-Data" in r.text
    assert r.headers["cache-control"] == "no-store"


# ---------------- ma'lumotlar ----------------
@pytest.mark.asyncio
async def test_universities_and_overview_match_the_database(async_client, db_session):
    d = await seed(db_session)
    unis = (await async_client.get("/api/v1/admin/universities", headers=ADMIN)).json()
    assert unis[0]["short"] == "TATU" and unis[0]["users"] == 4  # admin talaba sifatida sanalmaydi
    assert {u["short"] for u in unis} == {"TATU", "FDU"}

    ov = (await async_client.get(f"/api/v1/admin/overview?uni={d['uni'].id}", headers=ADMIN)).json()
    assert ov["users"] == 4
    assert (ov["with_sch"], ov["no_sch"], ov["no_group"]) == (1, 2, 1)
    assert ov["groups"] == 2 and ov["lessons"] == 1 and ov["subjects"] == 1
    assert ov["req_status"] == {"APPROVED": 1, "ADMIN_REVIEW": 1}
    assert ov["lang"] == {"uz": 2, "ru": 1, "en": 1}
    assert ov["top"] == [["Hisob 1", 1]]
    assert sum(n for _, n in ov["users_day"]) == 4 and sum(n for _, n in ov["req_day"]) == 2

    other = (await async_client.get(f"/api/v1/admin/overview?uni={d['other'].id}", headers=ADMIN)).json()
    assert other["users"] == 1 and other["groups"] == 0 and other["req_status"] == {}


@pytest.mark.asyncio
async def test_users_list_filters_and_detail(async_client, db_session):
    d = await seed(db_session)
    base = f"/api/v1/admin/users?uni={d['uni'].id}"
    allu = (await async_client.get(base, headers=ADMIN)).json()
    assert allu["total"] == 4
    stages = {u["name"]: u["stage"] for u in allu["items"]}
    assert stages == {"Madina": "done", "Sardor": "nosch", "Aziz": "nosch", "Nodira": "nogr"}
    assert (await async_client.get(base + "&stage=nosch", headers=ADMIN)).json()["total"] == 2
    assert (await async_client.get(base + "&lang=en", headers=ADMIN)).json()["items"][0]["name"] == "Nodira"
    found = (await async_client.get(base + "&q=@madina", headers=ADMIN)).json()
    assert found["total"] == 1 and found["items"][0]["username"] == "madina_r" and found["items"][0]["group"] == "712-24"
    assert (await async_client.get(base + "&q=713-24", headers=ADMIN)).json()["total"] == 2
    page = (await async_client.get(base + "&size=3&page=2", headers=ADMIN)).json()
    assert len(page["items"]) == 1

    detail = (await async_client.get(f"/api/v1/admin/users/{d['users'][0].id}", headers=ADMIN)).json()
    assert detail["university"].startswith("Toshkent") and detail["faculty"] == "Kiberxavfsizlik" and detail["requests"] == 1


@pytest.mark.asyncio
async def test_block_user_but_never_an_admin(async_client, db_session):
    d = await seed(db_session)
    sardor, admin = d["users"][1], d["users"][5]
    r = await async_client.post(f"/api/v1/admin/users/{sardor.id}/block", json={"blocked": True}, headers=ADMIN)
    assert r.status_code == 200
    await db_session.refresh(sardor)
    assert sardor.is_active is False
    assert (await async_client.post(f"/api/v1/admin/users/{admin.id}/block", json={"blocked": True}, headers=ADMIN)).status_code == 400


@pytest.mark.asyncio
async def test_groups_counts(async_client, db_session):
    d = await seed(db_session)
    groups = {g["name"]: g for g in (await async_client.get(f"/api/v1/admin/groups?uni={d['uni'].id}", headers=ADMIN)).json()}
    assert groups["712-24"]["users"] == 1 and groups["712-24"]["subjects"] == 1 and groups["712-24"]["lessons"] == 1
    assert groups["713-24"]["users"] == 2 and groups["713-24"]["subjects"] == 0


# ---------------- jadval so'rovlari ----------------
@pytest.mark.asyncio
async def test_editing_an_approved_request_updates_the_group_schedule(async_client, db_session):
    d = await seed(db_session)
    sub_id = d["done"].id
    detail = (await async_client.get(f"/api/v1/admin/submissions/{sub_id}", headers=ADMIN)).json()
    lesson = detail["lessons"][0]
    assert lesson["room"] == "D-307" and lesson["subject"] == "Hisob 1-MAT001"

    edited = dict(lesson, subject="Dasturiy injiniringga kirish-ISE001", start_time="09:30", end_time="")
    extra = {"day": "Seshanba", "start_time": "11:00", "end_time": "12:20", "subject": "Fizika 1", "room": "E-110",
             "teacher": "", "week_parity": "ODD", "lesson_type": "OTHER"}
    r = await async_client.put(f"/api/v1/admin/submissions/{sub_id}/lessons", json={"lessons": [edited, extra, {"subject": ""}]}, headers=ADMIN)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["saved"] == 2 and body["applied"] == 2

    rows = (await db_session.execute(
        select(Schedule, Subject.name).join(Subject, Subject.id == Schedule.subject_id)
        .where(Schedule.group_id == d["g1"].id, Schedule.is_active == True)
    )).all()
    got = sorted((s.day_of_week.value, s.start_time, s.end_time, name, s.week_parity.value) for s, name in rows)
    assert got == [("MONDAY", "09:30", "10:50", "Dasturiy injiniringga kirish", "ALL"),
                   ("TUESDAY", "11:00", "12:20", "Fizika 1", "ODD")]
    # xona o'zgarmagan dars o'z bino/xonasini saqlaydi
    saved = json.loads((await db_session.get(ScheduleSubmission, sub_id)).ai_extracted_json)
    assert saved[0]["building"] == "D" and saved[0]["room"] == "307"


@pytest.mark.asyncio
async def test_review_open_request_applies_schedule_and_notifies(async_client, db_session, fake_bot):
    d = await seed(db_session)
    sub_id = d["open"].id
    r = await async_client.post(f"/api/v1/admin/submissions/{sub_id}/review", json={"action": "approve"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED"
    active = (await db_session.execute(select(Schedule).where(Schedule.group_id == d["g2"].id, Schedule.is_active == True))).scalars().all()
    assert len(active) == 1
    again = await async_client.post(f"/api/v1/admin/submissions/{sub_id}/review", json={"action": "reject"}, headers=ADMIN)
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_broadcast_reaches_only_the_chosen_audience(async_client, db_session, fake_bot):
    d = await seed(db_session)
    counts = (await async_client.get(f"/api/v1/admin/broadcast/audiences?uni={d['uni'].id}", headers=ADMIN)).json()
    assert counts["all"] == 4 and counts["nosch"] == 2 and counts["done"] == 1 and counts["nogr"] == 1 and counts["ru"] == 1

    r = await async_client.post("/api/v1/admin/broadcast", json={"uni": d["uni"].id, "audience": "nosch", "text": "<b>Salom</b>"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["total"] == 2
    for _ in range(50):
        if admin_service.BROADCASTS[job["id"]]["done"]:
            break
        await asyncio.sleep(0.05)
    assert sorted(c for c, _, _ in fake_bot.sent) == [1002, 1003]
    assert all(kw.get("parse_mode", "x") is None for _, _, kw in fake_bot.sent)  # admin matni HTML sifatida o'qilmaydi
    status = (await async_client.get(f"/api/v1/admin/broadcast/{job['id']}", headers=ADMIN)).json()
    assert status["done"] and status["sent"] == 2
    hist = (await async_client.get(f"/api/v1/admin/broadcast?uni={d['uni'].id}", headers=ADMIN)).json()
    assert hist[-1]["text"] == "<b>Salom</b>" and hist[-1]["sent"] == 2
    assert (await db_session.execute(select(Announcement))).scalars().first() is not None


@pytest.mark.asyncio
async def test_bot_button_opens_the_site_only_for_the_admin(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from app.bot.handlers.admin_menu import handle_admin_site
    from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard

    admin_kb = [b.text for row in get_admin_main_keyboard("uz").keyboard for b in row]
    user_kb = [b.text for row in get_user_main_keyboard("uz").keyboard for b in row]
    assert "🖥 Admin sayt" in admin_kb and "🖥 Admin sayt" not in user_kb

    monkeypatch.setattr(settings, "ADMIN_WEB_URL", "https://149-118-57-149.sslip.io/admin")
    admin = User(id=1, telegram_id=ADMIN_TG, first_name="A", role=UserRole.ADMIN, language_code="uz")
    msg = MagicMock()
    msg.answer = AsyncMock()
    await handle_admin_site(msg, current_user=admin)
    button = msg.answer.call_args.kwargs["reply_markup"].inline_keyboard[0][0]
    assert button.web_app.url == "https://149-118-57-149.sslip.io/admin"

    # ADMIN roli bor, lekin ADMIN_IDS'da yo'q - sayt berilmaydi
    stranger = User(id=2, telegram_id=555, first_name="B", role=UserRole.ADMIN, language_code="uz")
    msg2 = MagicMock()
    msg2.answer = AsyncMock()
    await handle_admin_site(msg2, current_user=stranger)
    assert "reply_markup" not in msg2.answer.call_args.kwargs

    monkeypatch.setattr(settings, "ADMIN_WEB_URL", "")
    msg3 = MagicMock()
    msg3.answer = AsyncMock()
    await handle_admin_site(msg3, current_user=admin)
    assert "ADMIN_WEB_URL" in msg3.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_message_one_user(async_client, db_session, fake_bot):
    d = await seed(db_session)
    r = await async_client.post(f"/api/v1/admin/users/{d['users'][2].id}/message", json={"text": "Jadvalni yuboring"}, headers=ADMIN)
    assert r.json()["status"] == "ok"
    assert fake_bot.sent[0][0] == 1003
