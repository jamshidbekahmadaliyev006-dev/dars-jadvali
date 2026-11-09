"""
Ro'yxatdan o'tishda yozilgan universitet / fakultet / guruh nomlarini tekshirish.
Maqsad: "qo'toq", "zavtrak", "SOMSA", "69" kabi hazil yoki noto'g'ri yozuvlar bazaga tushmasin.

Tartib:
1. Oddiy qoidalar (tez): bo'sh/juda qisqa, faqat raqam, so'kinish, guruhda raqam yo'qligi.
2. Bazada shunday nom allaqachon bo'lsa - darhol qabul (AI chaqirilmaydi).
3. Universitet uchun aniq belgilar (universitet/institut/akademiya so'zi yoki TATU kabi qisqartma) - qabul.
4. Qolgan yangi nomlarni AI tekshiradi. AI javob bermasa (tarmoq va h.k.) - qabul qilamiz:
   to'g'ri yozgan talabani to'xtatib qo'yishdan ko'ra, bitta shubhali nom yaxshiroq.
"""
import re
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.ai_provider import get_ai_provider
from app.services.university_service import UniversityService, name_key

# So'kinish va haqoratlarning ildizlari (kichik harfda, belgilarsiz)
_BAD_ROOTS = (
    "qotoq", "qutoq", "yiban", "jalab", "dalbayob", "dalbaeb", "skay", "sikay", "sikish", "qanjiq",
    "amingni", "onangni", "xuy", "huy", "хуй", "пизд", "ебан", "ебат", "бля", "сука", "мудак", "pidr", "пидор",
    "blya", "suka", "pizd", "eban", "fuck", "shit", "bitch",
)
_EDU_WORDS = (
    "universitet", "university", "университет", "institut", "institute", "институт", "akademiya", "academy",
    "академия", "kollej", "college", "колледж", "konservatoriya", "консерватория", "texnikum", "техникум",
    "oliygoh", "filiali", "filial", "филиал",
)
_ACRONYM = re.compile(r"^[A-ZА-ЯЎҚҒҲ'`ʻ]{2,8}$")


def _letters(value: str) -> int:
    return sum(ch.isalpha() for ch in value)


def _too_short(text: str) -> bool:
    """3 harfdan qisqa nom faqat katta harfli qisqartma bo'lsa ("IT", "KX") - "om" kabi emas"""
    return _letters(text) < 3 and not _ACRONYM.match(text)


def has_bad_word(value: str) -> bool:
    key = name_key(value)
    return any(root in key for root in _BAD_ROOTS)


def check_group_name(value: str) -> bool:
    """Guruh: raqam bo'lishi shart (712-24, IQ-7-25, 071-23), qisqa va oddiy belgilardan iborat"""
    text = (value or "").strip()
    if not (2 <= len(text) <= 20) or has_bad_word(text):
        return False
    if not re.fullmatch(r"[0-9A-Za-zА-Яа-яЎўҚқҒғҲҳ'`ʻ\-_ ./]+", text):
        return False
    digits = sum(ch.isdigit() for ch in text)
    if digits == 0:
        return False
    if text.isdigit():
        # Faqat raqamdan iborat guruh: 3-4 xonali bo'lishi mumkin (211, 1201); "69", "45333" emas
        return 3 <= len(text) <= 4
    return True


async def check_university_name(session: AsyncSession, value: str) -> bool:
    text = " ".join((value or "").split())
    if _too_short(text) or len(text) > 150 or has_bad_word(text):
        return False
    if await UniversityService.match_university(session, text):
        return True
    lowered = text.lower()
    if any(word in lowered for word in _EDU_WORDS):
        return True
    # Bazada yo'q qisqartma (TDIU, SOMSA ...) ham AI'dan o'tadi
    verdict = await get_ai_provider().judge_name("university", text)
    return verdict is not False


async def check_faculty_name(session: AsyncSession, value: str, university_name: Optional[str] = None) -> bool:
    text = " ".join((value or "").split())
    if _too_short(text) or len(text) > 150 or has_bad_word(text):
        return False
    if university_name:
        univ = await UniversityService.match_university(session, university_name)
        if univ and await UniversityService.match_faculty(session, univ.id, text):
            return True
    verdict = await get_ai_provider().judge_name("faculty", text)
    return verdict is not False
