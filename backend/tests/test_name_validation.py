import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services import name_validation
from app.services.name_validation import check_faculty_name, check_group_name, check_university_name


@pytest.mark.parametrize("name", ["712-24", "712_24", "IQ-7-25", "071-23", "KI 21-03", "211", "1201"])
def test_good_group_names(name):
    assert check_group_name(name)


@pytest.mark.parametrize("name", ["SOMSA", "69", "45333", "SHU", "", "a", "712-24 🍕", "x" * 25])
def test_bad_group_names(name):
    assert not check_group_name(name)


class _Judge:
    def __init__(self, verdict):
        self.verdict = verdict
        self.calls = []

    async def judge_name(self, kind, value):
        self.calls.append((kind, value))
        return self.verdict


@pytest.mark.asyncio
async def test_university_rules_and_ai(db_session: AsyncSession, monkeypatch):
    from app.models.university import University

    db_session.add(University(name="Toshkent Axborot Texnologiyalari Universiteti"))
    await db_session.commit()
    judge = _Judge(False)
    monkeypatch.setattr(name_validation, "get_ai_provider", lambda: judge)
    # Bazadagi universitet (qisqartma bilan ham) va "universitet" so'zi bor nom - AI'siz qabul
    assert await check_university_name(db_session, "TATU")
    assert await check_university_name(db_session, "Toshkent davlat iqtisodiyot universiteti")
    assert judge.calls == []
    # Bazada yo'q, katta harf bilan yozilgan hazil ham AI'dan o'tadi
    assert not await check_university_name(db_session, "SOMSA")
    judge.calls.clear()
    # So'kinish - AI'siz rad
    assert not await check_university_name(db_session, "qo'toq")
    assert not await check_university_name(db_session, "yibanul")
    # Noaniq yangi nom - AI hal qiladi
    assert not await check_university_name(db_session, "zavtrak")
    assert judge.calls == [("university", "zavtrak")]


@pytest.mark.asyncio
async def test_ai_unavailable_does_not_block_students(db_session: AsyncSession, monkeypatch):
    monkeypatch.setattr(name_validation, "get_ai_provider", lambda: _Judge(None))
    assert await check_faculty_name(db_session, "Kiberxavfsizlik")
    assert await check_university_name(db_session, "Inha")


@pytest.mark.asyncio
async def test_faculty_rules(db_session: AsyncSession, monkeypatch):
    monkeypatch.setattr(name_validation, "get_ai_provider", lambda: _Judge(False))
    assert not await check_faculty_name(db_session, "om")
    assert not await check_faculty_name(db_session, "zavtrak")
    monkeypatch.setattr(name_validation, "get_ai_provider", lambda: _Judge(True))
    assert await check_faculty_name(db_session, "Iqtisodiyot")
    assert not await check_faculty_name(db_session, "om")  # AI "ha" desa ham - juda qisqa
    assert await check_faculty_name(db_session, "IT")  # katta harfli qisqartma
