"""Admin sayt: kirish himoyasi, botdagi bilan bir xil raqamlar, rad etishda xato matni."""
import asyncio
import json
import time

import pytest
from sqlalchemy import select

from app.api.v1 import admin as admin_api
from app.bot.handlers.admin_menu import collect_statistics, collect_user_counts
from app.core import admin_session
from app.core.admin_session import create_login_token, create_session_token, exchange_login_token, verify_session
from app.core.config import settings
from app.models.enums import DayOfWeek, SubmissionStatus, TeacherStatus, UserRole
from app.models.log import Announcement
from app.models.schedule import Schedule, ScheduleSubmission
from app.models.teacher import TeacherLesson, TeacherProfile
from app.models.university import Faculty, Group, Subject, University
from app.models.user import User
from app.models.log import AdminBroadcast
from app.services import admin_service
from tests.conftest import TestingSessionLocal

TOKEN = "123456:TEST-TOKEN"
ADMIN_TG = 999888777


@pytest.fixture(autouse=True)
def bot_settings(monkeypatch):
    monkeypatch.setattr(settings, "BOT_TOKEN", TOKEN)
    monkeypatch.setattr(settings, "ADMIN_IDS_RAW", str(ADMIN_TG))
    monkeypatch.setattr(admin_service, "SESSION_FACTORY", TestingSessionLocal)  # xabar natijasi test bazasiga yoziladi
    admin_session._USED_LOGINS.clear()
    admin_service.BROADCASTS.clear()


class FakeBot:
    def __init__(self):
        self.sent = []
        self.deleted = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))
        return type("Sent", (), {"message_id": 5000 + len(self.sent)})()

    async def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))


@pytest.fixture
def fake_bot(monkeypatch):
    bot = FakeBot()
    monkeypatch.setattr(admin_api, "get_bot", lambda: bot)
    return bot


def auth(tg_id: int = ADMIN_TG) -> dict:
    return {"Authorization": "Bearer " + create_session_token(tg_id)}


async def wait_for(predicate, attempts: int = 60):
    for _ in range(attempts):
        if predicate():
            return True
        await asyncio.sleep(0.05)
    return False


async def seed(db):
    """
    TATU: 2 guruh (biri jadvalli), 3 talaba, 1 tasdiqlangan va 1 kutayotgan o'qituvchi, 2 ta tugatmagan.
    FDU: 1 tugatmagan. Universitet tanlamagan: 1 ta.
    """
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
        User(telegram_id=3001, first_name="Ustoz", language_code="uz", university_id=uni.id),
        User(telegram_id=3002, first_name="Kutuvchi", language_code="uz"),
        User(telegram_id=4001, first_name="Yangi", language_code="uz"),
    ]
    db.add_all(users)
    await db.flush()
    teacher = TeacherProfile(user_id=users[6].id, university_id=uni.id, full_name="Ustoz U", status=TeacherStatus.APPROVED)
    waiting = TeacherProfile(user_id=users[7].id, university_id=uni.id, full_name="Kutuvchi K", status=TeacherStatus.PENDING)
    db.add_all([teacher, waiting])
    await db.flush()
    db.add(TeacherLesson(teacher_id=teacher.id, day_of_week=DayOfWeek.TUESDAY, start_time="08:00", end_time="09:20",
                         subject="Kriptografiya-CRY001"))
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
def test_tokens_cannot_be_forged_or_confused():
    login = create_login_token(ADMIN_TG)
    session = create_session_token(ADMIN_TG)
    assert verify_session(session) == ADMIN_TG
    assert verify_session(login) is None          # havola sessiya o'rnida ishlamaydi
    assert exchange_login_token(session) is None  # sessiya havola o'rnida ishlamaydi
    body, sig = session.split(".")
    assert verify_session(body + "." + sig[:-2] + "AA") is None
    assert verify_session(body.replace(body[5], "A" if body[5] != "A" else "B") + "." + sig) is None
    assert verify_session("") is None and verify_session("x.y") is None
    assert verify_session(create_session_token(ADMIN_TG, now=time.time() - 2 * 86400)) is None  # eskirgan


def test_login_link_works_once_and_expires():
    link = create_login_token(ADMIN_TG)
    assert exchange_login_token(link) == ADMIN_TG
    assert exchange_login_token(link) is None  # ikkinchi marta ishlamaydi
    assert exchange_login_token(create_login_token(ADMIN_TG, now=time.time() - 600)) is None  # 5 daqiqadan eski


def test_tokens_depend_on_the_bot_token(monkeypatch):
    session = create_session_token(ADMIN_TG)
    monkeypatch.setattr(settings, "BOT_TOKEN", "999:OTHER")
    assert verify_session(session) is None  # bot tokenini bilmagan odam token yasay olmaydi


@pytest.mark.asyncio
async def test_api_is_closed_to_everyone_but_the_logged_in_admin(async_client, db_session):
    await seed(db_session)
    url = "/api/v1/admin/universities"
    assert (await async_client.get(url)).status_code == 401
    assert (await async_client.get(url, headers={"Authorization": "Bearer garbage"})).status_code == 401
    assert (await async_client.get(url, headers={"Authorization": "Bearer " + create_login_token(ADMIN_TG)})).status_code == 401
    assert (await async_client.get(url, headers=auth(1001))).status_code == 403  # oddiy foydalanuvchi
    assert (await async_client.get(url, headers={"Authorization": "Bearer " + create_session_token(ADMIN_TG, now=time.time() - 3 * 86400)})).status_code == 401
    assert (await async_client.get(url, headers=auth())).status_code == 200


@pytest.mark.asyncio
async def test_removing_an_admin_from_the_list_stops_their_session(async_client, db_session, monkeypatch):
    await seed(db_session)
    assert (await async_client.get("/api/v1/admin/me", headers=auth())).status_code == 200
    monkeypatch.setattr(settings, "ADMIN_IDS_RAW", "123")
    assert (await async_client.get("/api/v1/admin/me", headers=auth())).status_code == 403


@pytest.mark.asyncio
async def test_login_endpoint_exchanges_the_bot_link_for_a_session(async_client, db_session):
    await seed(db_session)
    link = create_login_token(ADMIN_TG)
    r = await async_client.post("/api/v1/admin/login", json={"token": link})
    assert r.status_code == 200
    me = await async_client.get("/api/v1/admin/me", headers={"Authorization": "Bearer " + r.json()["session"]})
    assert me.status_code == 200 and me.json()["name"] == "Admin" and me.json()["week"] in ("ODD", "EVEN")
    assert (await async_client.post("/api/v1/admin/login", json={"token": link})).status_code == 401  # bir marta
    stranger = await async_client.post("/api/v1/admin/login", json={"token": create_login_token(1001)})
    assert stranger.status_code == 403  # admin bo'lmagan odam havola olsa ham kirmaydi
    assert (await async_client.post("/api/v1/admin/login", json={"token": "x.y"})).status_code == 401


@pytest.mark.asyncio
async def test_admin_page_is_served_with_security_headers(async_client):
    r = await async_client.get("/admin")
    assert r.status_code == 200
    assert "Qulay Jadval" in r.text and "Authorization" in r.text and "telegram-web-app" not in r.text
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


@pytest.mark.asyncio
async def test_bot_button_gives_a_one_time_link_only_to_the_admin(monkeypatch):
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
    assert button.web_app is None  # Telegram mini app emas, oddiy brauzer havolasi
    prefix = "https://149-118-57-149.sslip.io/admin#login="
    assert button.url.startswith(prefix)  # token # dan keyin: serverga va loglarga tushmaydi
    token = button.url[len(prefix):]
    assert exchange_login_token(token) == ADMIN_TG
    assert exchange_login_token(token) is None

    # ADMIN roli bor, lekin ADMIN_IDS'da yo'q - havola berilmaydi
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


# ---------------- sayt va bot bir xil raqam ko'rsatadi ----------------
@pytest.mark.asyncio
async def test_site_numbers_equal_the_bots_numbers(async_client, db_session):
    await seed(db_session)
    bot_users = await collect_user_counts(db_session)
    bot_stats = await collect_statistics(db_session)
    ov = (await async_client.get("/api/v1/admin/overview?uni=0", headers=auth())).json()
    for key in ("total", "teachers", "pending", "students", "unregistered"):
        assert ov[key] == bot_users[key], key
    for key in ("universities", "faculties", "groups", "subjects"):
        assert ov[key] == bot_stats[key], key
    assert ov["teachers"] == bot_stats["teachers"]
    assert (ov["total"], ov["students"], ov["teachers"], ov["pending"], ov["unregistered"]) == (9, 3, 1, 1, 4)
    assert ov["subjects"] == 2  # Hisob 1 (MAT001) va o'qituvchi darsi (CRY001)
    assert ov["total"] == ov["students"] + ov["teachers"] + ov["pending"] + ov["unregistered"]


@pytest.mark.asyncio
async def test_university_view_filters_the_same_rules(async_client, db_session):
    d = await seed(db_session)
    unis = (await async_client.get("/api/v1/admin/universities", headers=auth())).json()
    assert unis[0]["short"] == "TATU" and unis[0]["users"] == 7 and {u["short"] for u in unis} == {"TATU", "FDU"}

    ov = (await async_client.get(f"/api/v1/admin/overview?uni={d['uni'].id}", headers=auth())).json()
    assert (ov["total"], ov["students"], ov["teachers"], ov["pending"], ov["unregistered"]) == (7, 3, 1, 1, 2)
    assert ov["groups"] == 2 and ov["faculties"] == 1 and ov["lessons"] == 1 and ov["universities"] == 1
    assert ov["req_status"] == {"APPROVED": 1, "ADMIN_REVIEW": 1}
    assert ov["lang"] == {"uz": 5, "ru": 1, "en": 1}
    assert ov["top"] == [["Hisob 1", 1]]
    assert sum(n for _, n in ov["users_day"]) == 7 and sum(n for _, n in ov["req_day"]) == 2

    other = (await async_client.get(f"/api/v1/admin/overview?uni={d['other'].id}", headers=auth())).json()
    assert other["total"] == 1 and other["unregistered"] == 1 and other["groups"] == 0 and other["req_status"] == {}
    assert (await async_client.get("/api/v1/admin/overview?uni=999", headers=auth())).status_code == 404


@pytest.mark.asyncio
async def test_activity_follows_the_chosen_date(async_client, db_session):
    d = await seed(db_session)
    get = lambda q: async_client.get("/api/v1/admin/activity?" + q, headers=auth())
    day = (await get("period=day")).json()
    assert len(day["labels"]) == 24 and day["total_users"] == 9 and sum(day["users"]) == 9
    week = (await get("period=week")).json()
    assert len(week["labels"]) == 7 and week["total_users"] == 9 and week["start"] <= day["start"] <= week["end"]
    month = (await get("period=month")).json()
    assert month["total_users"] == 9 and 4 <= len(month["labels"]) <= 6 and "–" in month["labels"][0]
    assert week["labels"][0].startswith("Du ")
    old = (await get("period=month&day=2020-02-10")).json()
    assert old["total_users"] == 0 and len(old["labels"]) == 5 and old["labels"][0] == "01–02.02" and old["start"] == "2020-02-01"
    # sana o'tmishda bo'lsa, umumiy raqamlar ham o'sha kungacha bo'lgan holatni ko'rsatadi
    past = (await async_client.get("/api/v1/admin/overview?uni=0&day=2020-02-10", headers=auth())).json()
    assert past["total"] == 0 and past["groups"] == 0 and past["req_status"] == {}
    now = (await async_client.get("/api/v1/admin/overview?uni=0", headers=auth())).json()
    today = (await async_client.get(f"/api/v1/admin/overview?uni=0&day={day['start']}", headers=auth())).json()
    assert today["total"] == now["total"] == 9
    assert (await get(f"period=week&uni={d['other'].id}")).json()["total_users"] == 1
    assert (await get("period=year")).status_code == 422


@pytest.mark.asyncio
async def test_submissions_can_be_paged(async_client, db_session):
    await seed(db_session)
    first = (await async_client.get("/api/v1/admin/submissions?limit=1", headers=auth())).json()
    second = (await async_client.get("/api/v1/admin/submissions?limit=1&offset=1", headers=auth())).json()
    assert len(first) == 1 and len(second) == 1 and first[0]["id"] != second[0]["id"]
    assert (await async_client.get("/api/v1/admin/submissions?limit=1&offset=50", headers=auth())).json() == []


@pytest.mark.asyncio
async def test_users_list_filters_and_detail(async_client, db_session):
    d = await seed(db_session)
    base = f"/api/v1/admin/users?uni={d['uni'].id}"
    allu = (await async_client.get(base, headers=auth())).json()
    assert allu["total"] == 7
    stages = {u["name"]: u["stage"] for u in allu["items"]}
    assert stages == {"Madina": "done", "Sardor": "nosch", "Aziz": "nosch", "Nodira": "nogr", "Admin": "nogr",
                      "Ustoz": "teacher", "Kutuvchi": "pending"}
    assert next(u for u in allu["items"] if u["name"] == "Admin")["is_admin"] is True
    assert (await async_client.get(base + "&stage=nosch", headers=auth())).json()["total"] == 2
    assert (await async_client.get(base + "&stage=students", headers=auth())).json()["total"] == 3
    assert (await async_client.get(base + "&stage=teacher", headers=auth())).json()["items"][0]["name"] == "Ustoz"
    assert (await async_client.get(base + "&stage=nogr", headers=auth())).json()["total"] == 2
    assert (await async_client.get(base + "&stage=zzz", headers=auth())).status_code == 422
    assert (await async_client.get(base + "&lang=en", headers=auth())).json()["items"][0]["name"] == "Nodira"
    found = (await async_client.get(base + "&q=@madina", headers=auth())).json()
    assert found["total"] == 1 and found["items"][0]["username"] == "madina_r" and found["items"][0]["group"] == "712-24"
    assert (await async_client.get(base + "&q=713-24", headers=auth())).json()["total"] == 2
    assert len((await async_client.get(base + "&size=3&page=3", headers=auth())).json()["items"]) == 1
    everyone = (await async_client.get("/api/v1/admin/users?uni=0&size=50", headers=auth())).json()
    assert everyone["total"] == 9 and any(u["name"] == "Yangi" for u in everyone["items"])

    detail = (await async_client.get(f"/api/v1/admin/users/{d['users'][0].id}", headers=auth())).json()
    assert detail["university"].startswith("Toshkent") and detail["faculty"] == "Kiberxavfsizlik" and detail["requests"] == 1


@pytest.mark.asyncio
async def test_block_user_but_never_an_admin(async_client, db_session):
    d = await seed(db_session)
    sardor, admin = d["users"][1], d["users"][5]
    r = await async_client.post(f"/api/v1/admin/users/{sardor.id}/block", json={"blocked": True}, headers=auth())
    assert r.status_code == 200
    await db_session.refresh(sardor)
    assert sardor.is_active is False
    assert (await async_client.post(f"/api/v1/admin/users/{admin.id}/block", json={"blocked": True}, headers=auth())).status_code == 400


@pytest.mark.asyncio
async def test_groups_counts_and_all_universities(async_client, db_session):
    d = await seed(db_session)
    groups = {g["name"]: g for g in (await async_client.get(f"/api/v1/admin/groups?uni={d['uni'].id}", headers=auth())).json()}
    assert groups["712-24"]["users"] == 1 and groups["712-24"]["subjects"] == 1 and groups["712-24"]["lessons"] == 1
    assert groups["713-24"]["users"] == 2 and groups["713-24"]["subjects"] == 0 and groups["713-24"]["univ"] == "TATU"
    assert len((await async_client.get("/api/v1/admin/groups?uni=0", headers=auth())).json()) == 2


# ---------------- jadval so'rovlari ----------------
@pytest.mark.asyncio
async def test_editing_an_approved_request_updates_the_group_schedule(async_client, db_session):
    d = await seed(db_session)
    sub_id = d["done"].id
    detail = (await async_client.get(f"/api/v1/admin/submissions/{sub_id}", headers=auth())).json()
    lesson = detail["lessons"][0]
    assert lesson["room"] == "D-307" and lesson["subject"] == "Hisob 1-MAT001"

    edited = dict(lesson, subject="Dasturiy injiniringga kirish-ISE001", start_time="09:30", end_time="")
    extra = {"day": "Seshanba", "start_time": "11:00", "end_time": "12:20", "subject": "Fizika 1", "room": "E-110",
             "teacher": "", "week_parity": "ODD", "lesson_type": "OTHER"}
    r = await async_client.put(f"/api/v1/admin/submissions/{sub_id}/lessons", json={"lessons": [edited, extra, {"subject": ""}]}, headers=auth())
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
    saved = json.loads((await db_session.get(ScheduleSubmission, sub_id)).ai_extracted_json)
    assert saved[0]["building"] == "D" and saved[0]["room"] == "307"  # xona o'zgarmagan dars asl bino/xonasini saqlaydi


@pytest.mark.asyncio
async def test_approve_applies_schedule_and_notifies_student_and_group(async_client, db_session, fake_bot):
    d = await seed(db_session)
    sub_id = d["open"].id
    r = await async_client.post(f"/api/v1/admin/submissions/{sub_id}/review", json={"action": "approve"}, headers=auth())
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED" and r.json()["notified"] == 2  # talaba + guruhdosh
    active = (await db_session.execute(select(Schedule).where(Schedule.group_id == d["g2"].id, Schedule.is_active == True))).scalars().all()
    assert len(active) == 1
    assert await wait_for(lambda: len(fake_bot.sent) == 2)
    to_student = next(text for chat, text, _ in fake_bot.sent if chat == 1002)
    assert "Ваше расписание подтверждено" in to_student  # talaba rus tilida
    to_mate = next(text for chat, text, _ in fake_bot.sent if chat == 1003)
    assert "713-24" in to_mate
    assert (await async_client.post(f"/api/v1/admin/submissions/{sub_id}/review", json={"action": "reject"}, headers=auth())).status_code == 409


@pytest.mark.asyncio
async def test_reject_sends_the_students_what_is_wrong(async_client, db_session, fake_bot):
    d = await seed(db_session)
    sub_id = d["open"].id
    reason = "«Dasturiy injiniringga kirish» fani noto'g'ri o'qilgan <b>tuzating</b>"
    r = await async_client.post(f"/api/v1/admin/submissions/{sub_id}/review", json={"action": "reject", "reason": reason}, headers=auth())
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "REJECTED" and r.json()["notified"] == 1
    assert await wait_for(lambda: len(fake_bot.sent) == 1)
    chat, text, kwargs = fake_bot.sent[0]
    assert chat == 1002 and kwargs["parse_mode"] == "HTML"
    assert "Ошибка" in text and "noto'g'ri o'qilgan" in text and "ещё раз" in text   # talaba rus tilida
    assert "<b>tuzating</b>" not in text and "&lt;b&gt;tuzating" in text             # xato matni HTML sifatida o'qilmaydi
    sub = await db_session.get(ScheduleSubmission, sub_id)
    assert sub.status == SubmissionStatus.REJECTED and "noto'g'ri o'qilgan" in sub.admin_notes
    active = (await db_session.execute(select(Schedule).where(Schedule.group_id == d["g2"].id, Schedule.is_active == True))).scalars().all()
    assert active == []  # rad etilgan jadval guruhga yozilmaydi


@pytest.mark.asyncio
async def test_reject_without_reason_keeps_the_standard_message(async_client, db_session, fake_bot):
    d = await seed(db_session)
    r = await async_client.post(f"/api/v1/admin/submissions/{d['open'].id}/review", json={"action": "reject"}, headers=auth())
    assert r.status_code == 200
    assert await wait_for(lambda: len(fake_bot.sent) == 1)
    assert "Ошибка" not in fake_bot.sent[0][1] and "отклонено" in fake_bot.sent[0][1]


# ---------------- xabarlar ----------------
@pytest.mark.asyncio
async def test_broadcast_reaches_only_the_chosen_audience(async_client, db_session, fake_bot):
    d = await seed(db_session)
    counts = (await async_client.get(f"/api/v1/admin/broadcast/audiences?uni={d['uni'].id}", headers=auth())).json()
    assert counts == {"all": 6, "nosch": 2, "done": 1, "nogr": 1, "teachers": 1, "ru": 1, "en": 1}

    r = await async_client.post("/api/v1/admin/broadcast", json={"uni": d["uni"].id, "audience": "nosch", "text": "<b>Salom</b>"}, headers=auth())
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["total"] == 2
    assert await wait_for(lambda: admin_service.BROADCASTS[job["id"]]["done"])
    assert sorted(c for c, _, _ in fake_bot.sent) == [1002, 1003]
    assert all(kw.get("parse_mode", "x") is None for _, _, kw in fake_bot.sent)  # admin matni HTML sifatida o'qilmaydi
    status = (await async_client.get(f"/api/v1/admin/broadcast/{job['id']}", headers=auth())).json()
    assert status["done"] and status["sent"] == 2
    hist = (await async_client.get(f"/api/v1/admin/broadcast?uni={d['uni'].id}", headers=auth())).json()
    assert hist[-1]["text"] == "<b>Salom</b>" and hist[-1]["sent"] == 2
    assert (await db_session.execute(select(Announcement))).scalars().first() is not None


@pytest.mark.asyncio
async def test_deleting_a_broadcast_removes_it_from_the_users_chats_too(async_client, db_session, fake_bot):
    from app.models.log import AdminBroadcast, AdminBroadcastMessage

    d = await seed(db_session)
    job = (await async_client.post("/api/v1/admin/broadcast", json={"uni": d["uni"].id, "audience": "nosch", "text": "Reklama"}, headers=auth())).json()
    assert await wait_for(lambda: admin_service.BROADCASTS[job["id"]]["done"])
    stored = (await db_session.execute(select(AdminBroadcastMessage).where(AdminBroadcastMessage.broadcast_id == job["id"]))).scalars().all()
    assert sorted(m.chat_id for m in stored) == [1002, 1003]

    r = await async_client.delete(f"/api/v1/admin/broadcast/{job['id']}", headers=auth())
    assert r.status_code == 200 and r.json()["to_delete"] == 2 and not r.json()["untracked"]
    assert await wait_for(lambda: len(fake_bot.deleted) == 2)
    assert sorted(c for c, _ in fake_bot.deleted) == [1002, 1003]
    assert sorted(m for _, m in fake_bot.deleted) == sorted(m.message_id for m in stored)
    assert await db_session.get(AdminBroadcast, job["id"]) is None
    hist = (await async_client.get(f"/api/v1/admin/broadcast?uni={d['uni'].id}", headers=auth())).json()
    assert all(h["id"] != job["id"] for h in hist)
    assert (await async_client.delete(f"/api/v1/admin/broadcast/{job['id']}", headers=auth())).status_code == 404

    # eski xabar (message_id saqlanmagan): saytdan o'chadi, lekin buni aytadi
    old = AdminBroadcast(university_id=0, audience="all", text="eski", total=3, sent=3, is_done=True)
    db_session.add(old)
    await db_session.commit()
    r2 = await async_client.delete(f"/api/v1/admin/broadcast/{old.id}", headers=auth())
    assert r2.status_code == 200 and r2.json()["untracked"] is True


@pytest.mark.asyncio
async def test_broadcast_to_teachers_and_to_everyone(async_client, db_session, fake_bot):
    d = await seed(db_session)
    r = await async_client.post("/api/v1/admin/broadcast", json={"uni": 0, "audience": "teachers", "text": "Ustozlarga"}, headers=auth())
    assert r.status_code == 200 and r.json()["total"] == 1
    assert await wait_for(lambda: len(fake_bot.sent) == 1)
    assert fake_bot.sent[0][0] == 3001
    everyone = (await async_client.get("/api/v1/admin/broadcast/audiences?uni=0", headers=auth())).json()
    assert everyone["all"] == 8  # admin xabar olmaydi


@pytest.mark.asyncio
async def test_each_audience_has_its_own_history_saved_in_the_database(async_client, db_session, fake_bot):
    d = await seed(db_session)
    uni = d["uni"].id
    sent = {}
    for audience, text in (("nosch", "Jadval yuboring"), ("done", "Jadvalingiz tayyor"), ("nosch", "Yana eslatma")):
        r = await async_client.post("/api/v1/admin/broadcast", json={"uni": uni, "audience": audience, "text": text}, headers=auth())
        assert r.status_code == 200, r.text
        assert await wait_for(lambda: admin_service.BROADCASTS[r.json()["id"]]["done"])
        sent[text] = r.json()["id"]

    def texts(resp):
        return [h["text"] for h in resp.json()]

    nosch = await async_client.get(f"/api/v1/admin/broadcast?uni={uni}&audience=nosch", headers=auth())
    done = await async_client.get(f"/api/v1/admin/broadcast?uni={uni}&audience=done", headers=auth())
    assert texts(nosch) == ["Jadval yuboring", "Yana eslatma"]  # faqat shu auditoriyaga yozilganlar, eskisi birinchi
    assert texts(done) == ["Jadvalingiz tayyor"]
    assert texts(await async_client.get(f"/api/v1/admin/broadcast?uni={uni}&audience=teachers", headers=auth())) == []
    assert len((await async_client.get(f"/api/v1/admin/broadcast?uni={uni}", headers=auth())).json()) == 3
    assert (await async_client.get("/api/v1/admin/broadcast?uni=0&audience=nosch", headers=auth())).json() == []  # boshqa ko'rinish
    assert (await async_client.get(f"/api/v1/admin/broadcast?uni={uni}&audience=zzz", headers=auth())).status_code == 422

    # natija bazada: server qayta ishga tushsa ham tarix va sanoq qoladi
    admin_service.BROADCASTS.clear()
    first = nosch.json()[0]
    assert (first["total"], first["sent"], first["done"]) == (2, 2, True)
    row = await db_session.get(AdminBroadcast, sent["Jadval yuboring"])
    assert row.is_done and row.sent == 2 and row.audience == "nosch" and row.finished_at is not None
    again = (await async_client.get(f"/api/v1/admin/broadcast/{sent['Jadval yuboring']}", headers=auth())).json()
    assert again["sent"] == 2 and again["done"] is True
    assert sorted(c for c, _, _ in fake_bot.sent) == [1001, 1002, 1002, 1003, 1003]  # "done" faqat Madinaga; "nosch" ikki marta Sardor va Azizga


@pytest.mark.asyncio
async def test_only_admin_review_waits_for_the_admin(async_client, db_session):
    d = await seed(db_session)
    fix = ScheduleSubmission(user_id=d["users"][2].id, university_id=d["uni"].id, group_id=d["g2"].id, image_file_id="x",
                             status=SubmissionStatus.NEEDS_CORRECTION, ai_extracted_json="[]")
    db_session.add(fix)
    await db_session.commit()
    base = f"/api/v1/admin/submissions?uni={d['uni'].id}"
    rows = {r["status"]: r for r in (await async_client.get(base, headers=auth())).json()}
    assert rows["ADMIN_REVIEW"]["open"] is True and rows["NEEDS_CORRECTION"]["open"] is False  # talaba tuzatishi kutilyapti
    assert [r["status"] for r in (await async_client.get(base + "&status=NEEDS_CORRECTION", headers=auth())).json()] == ["NEEDS_CORRECTION"]
    assert len((await async_client.get(base + "&status=APPROVED,ADMIN_REVIEW", headers=auth())).json()) == 2
    assert (await async_client.get(base + "&status=NOPE", headers=auth())).status_code == 422
    assert (await async_client.post(f"/api/v1/admin/submissions/{fix.id}/review", json={"action": "approve"}, headers=auth())).status_code == 409
    assert (await async_client.get("/api/v1/admin/notifications", headers=auth())).json()["review"] == 1


@pytest.mark.asyncio
async def test_bell_lists_every_new_user(async_client, db_session):
    d = await seed(db_session)
    first = d["users"][0].id
    n = (await async_client.get("/api/v1/admin/notifications?since=0", headers=auth())).json()
    assert n["new"] == 0 and n["latest"] == d["users"][8].id  # since noma'lum: eski foydalanuvchilar "yangi" bo'lib yog'ilmaydi
    assert n["items"][0]["name"] == "Yangi" and all(i["name"] != "Admin" for i in n["items"])  # admin o'zi haqida xabar olmaydi
    after = (await async_client.get(f"/api/v1/admin/notifications?since={first}", headers=auth())).json()
    assert after["new"] == 7
    none = (await async_client.get(f"/api/v1/admin/notifications?since={n['latest']}", headers=auth())).json()
    assert none["new"] == 0 and none["review"] == 1
    assert (await async_client.get("/api/v1/admin/notifications")).status_code == 401


@pytest.mark.asyncio
async def test_message_one_user(async_client, db_session, fake_bot):
    d = await seed(db_session)
    r = await async_client.post(f"/api/v1/admin/users/{d['users'][2].id}/message", json={"text": "Jadvalni yuboring"}, headers=auth())
    assert r.json()["status"] == "ok"
    assert fake_bot.sent[0][0] == 1003
