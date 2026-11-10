from abc import ABC, abstractmethod
import base64
import json
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.schemas.ai import ExtractedLessonItem, ExtractedScheduleResult


class BaseAIProvider(ABC):
    """Barcha AI provayderlari (Gemini, OpenAI, Mock) uchun unifikatsiyalangan interfeys"""

    @abstractmethod
    async def extract_schedule_from_image(self, image_bytes: bytes, filename: str = "schedule.jpg") -> ExtractedScheduleResult:
        """Dars jadvali screenshotidan darslarni strukturali JSON ko'rinishida ajratib olish"""
        pass

    @abstractmethod
    async def chat_student_assistant(self, query: str, context: Dict[str, Any]) -> str:
        """Talabaga darslar, vazifalar va rejalar bo'yicha yordam beruvchi AI assistant"""
        pass


class MockAIProvider(BaseAIProvider):
    """
    Offline va test rejimida yoki API key bo'lmaganda ishlovchi Mock provayder.
    Tizimni to'xtatib qo'ymasdan realistik ma'lumotlar bilan ta'minlaydi.
    """

    async def extract_schedule_from_image(self, image_bytes: bytes, filename: str = "schedule.jpg") -> ExtractedScheduleResult:
        logger.info("MockAIProvider: Simulating schedule extraction from image.")
        sample_lessons = [
            ExtractedLessonItem(
                day="Dushanba",
                subject="Kompyuter tarmoqlari",
                teacher="Dots. Qodirov A.A.",
                start_time="09:00",
                end_time="10:20",
                building="2-Bino",
                room="305",
                lesson_type="LECTURE",
            ),
            ExtractedLessonItem(
                day="Dushanba",
                subject="Ma'lumotlar bazasi tizimlari",
                teacher="Ass. Yusupova D.Sh.",
                start_time="10:30",
                end_time="11:50",
                building="2-Bino",
                room="308",
                lesson_type="PRACTICE",
            ),
            ExtractedLessonItem(
                day="Seshanba",
                subject="Algoritmlar va ma'lumotlar tuzilmasi",
                teacher="Prof. Karimov S.T.",
                start_time="09:00",
                end_time="10:20",
                building="Bosh bino",
                room="104",
                lesson_type="LECTURE",
            ),
            ExtractedLessonItem(
                day="Chorshanba",
                subject="Sun'iy intellekt asoslari",
                teacher="PhD Aliyev O.N.",
                start_time="11:00",
                end_time="12:20",
                building="IT Markaz",
                room="Lab-2",
                lesson_type="LAB",
            ),
        ]
        return ExtractedScheduleResult(
            lessons=sample_lessons,
            confidence=0.95,
            warnings="Mock tahlil natijasi: haqiqiy API kalit ulanmaganligi sababli test jadvali taqdim etildi.",
            raw_response=json.dumps([l.model_dump() for l in sample_lessons], ensure_ascii=False),
        )

    async def chat_student_assistant(self, query: str, context: Dict[str, Any]) -> str:
        logger.info(f"MockAIProvider: Answering assistant query: '{query}'")
        q_lower = query.lower()

        today_lessons = context.get("today_lessons", [])
        tomorrow_lessons = context.get("tomorrow_lessons", [])
        tasks = context.get("pending_tasks", [])

        if "bugun" in q_lower or "nechta" in q_lower or "qaysi dars" in q_lower:
            if today_lessons:
                lesson_names = ", ".join(f"{l.get('subject_name')} ({l.get('start_time')})" for l in today_lessons)
                return f"Bugun sizda {len(today_lessons)} ta dars bor: {lesson_names}. Darslaringizga o'z vaqtida boring!"
            else:
                return "Bugun sizning guruhingizda darslar jadvalga kiritilmagan yoki bugun dam olish kuni!"

        elif "ertaga" in q_lower:
            if tomorrow_lessons:
                lesson_names = ", ".join(f"{l.get('subject_name')} ({l.get('start_time')})" for l in tomorrow_lessons)
                return f"Ertaga sizda {len(tomorrow_lessons)} ta dars bor: {lesson_names}."
            else:
                return "Ertaga jadvalda darslar ko'rsatilmagan."

        elif "keyingi dars" in q_lower:
            if today_lessons:
                first = today_lessons[0]
                return f"Keyingi darsingiz: '{first.get('subject_name')}', soat {first.get('start_time')} da, {first.get('room_number', 'aniqlanmagan')} xonada."
            return "Hozirda yaqin dars topilmadi."

        elif "vazifa" in q_lower or "topshiriq" in q_lower:
            if tasks:
                t_names = ", ".join(t.get("title") for t in tasks[:3])
                return f"Sizda {len(tasks)} ta faol vazifa bor. Eng muhimlari: {t_names}."
            return "Sizda bajarilmagan shaxsiy vazifalar mavjud emas. Yangi vazifa qo'shishingiz mumkin!"

        elif "reja" in q_lower:
            plan = "Bugungi rejangiz:\n"
            if today_lessons:
                plan += f"1. Darslar: {len(today_lessons)} ta darsda qatnashish.\n"
            if tasks:
                plan += f"2. Vazifalar: '{tasks[0].get('title')}' topshirig'ini bajarish.\n"
            plan += "3. Shaxsiy dars takrorlash va hordiq chiqarish."
            return plan

        return (
            f"Salom! Men sizning AI yordamchingizman. Sizning darslaringiz va vazifalaringizni tahlil qila olaman. "
            f"Hozir sizda {len(today_lessons)} ta bugungi dars va {len(tasks)} ta bajarilmagan vazifa mavjud."
        )


def unify_subject_names_by_code(items: List[Any]) -> None:
    """
    Bir xil fan kodli (masalan ISE001 va ISE001-1) bloklarning nomi turlicha o'qilgan bo'lsa,
    eng ko'p uchragan nomni hammasiga beradi: bitta fan ikkita turli fanga bo'linib ketmasin.
    """
    from collections import Counter
    from app.services.schedule_service import normalize_subject_name

    by_code: Dict[str, Counter] = {}
    for item in items:
        name, code = normalize_subject_name(item.subject or "")
        if code and name:
            by_code.setdefault(code, Counter())[name] += 1

    for item in items:
        name, code = normalize_subject_name(item.subject or "")
        if code and code in by_code:
            best = by_code[code].most_common(1)[0][0]
            if best != name:
                item.subject = f"{best}-{code}"


class GeminiAIProvider(BaseAIProvider):
    """
    Google Gemini Multimodal Vision & Text AI provayderi.
    Rasmiy HTTP REST API orqali ortiqcha og'ir kutubxonalarsiz ishlaydi.
    """

    # Yengil modellar real jadval rasmini ~5 soniyada o'qiydi; gemini-flash-latest esa band
    # paytda 503 qaytarib, 40 soniyadan ko'proq ushlab turadi. Birinchisi ishlamasa ikkinchisi.
    VISION_MODELS = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite")
    CHAT_MODEL = "gemini-3.5-flash-lite"
    REQUEST_TIMEOUT_SECONDS = 45.0

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def _headers(self) -> Dict[str, str]:
        # Kalit URL'da emas, sarlavhada: URL'lar loglarga yoziladi
        return {"x-goog-api-key": self.api_key}

    async def extract_schedule_from_image(self, image_bytes: bytes, filename: str = "schedule.jpg") -> ExtractedScheduleResult:
        base64_data = base64.b64encode(image_bytes).decode("utf-8")
        mime_type = "image/png" if filename.lower().endswith(".png") else "image/jpeg"

        prompt = (
            "Bu universitet haftalik dars jadvali rasmi. Har bir rangli blok yoki jadval katagi bitta dars. "
            "Ustun yoki qator sarlavhasi kun, blokdagi vaqt boshlanish vaqti. Tugash vaqti yozilmagan bo'lsa, "
            "blok balandligi va vaqt o'qidan aniqlang. Bir vaqtda ikkita dars bo'lsa, ikkalasini ham yozing. "
            "Fan nomi va xonani rasmda qanday yozilgan bo'lsa, aynan shunday ko'chiring, harfma-harf. "
            "Fan nomidan keyingi kod (masalan ABC001) nomning bir qismi sifatida qoladi: kodni hech qachon "
            "ochib, tarjima qilib yoki boshqa fan nomi bilan almashtirib yozmang, kod ma'nosini taxmin qilmang. "
            "Bir xil kodli bloklar bir xil fan nomiga ega. "
            "Faqat rasmda ko'ringan narsani yozing, hech narsa to'qimang. Rasm dars jadvali bo'lmasa, [] qaytaring. "
            "Faqat JSON massiv qaytaring, har bir element kalitlari: "
            "day (Dushanba, Seshanba, Chorshanba, Payshanba, Juma, Shanba, Yakshanba), subject, "
            "teacher (yo'q bo'lsa null), start_time (HH:MM), end_time (HH:MM), building (yo'q bo'lsa null), "
            "room (yo'q bo'lsa null), lesson_type (LECTURE, PRACTICE, LAB, SEMINAR yoki OTHER), "
            "week_parity (toq hafta=ODD, juft hafta=EVEN, belgi bo'lmasa=ALL)."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime_type, "data": base64_data}},
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0,
            },
        }

        # Xato bo'lsa namuna ma'lumot QAYTARILMAYDI: soxta darslar haqiqiy jadvalga yozilib ketardi
        last_error = "noma'lum xato"
        async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT_SECONDS) as client:
            # Aniqroq model birinchi; yengil modellar faqat u xato yoki band bo'lganda
            models = [settings.GEMINI_VISION_MODEL, *self.VISION_MODELS]
            for model in dict.fromkeys(m for m in models if m):
                try:
                    res = await client.post(
                        f"{self.base_url}/{model}:generateContent",
                        headers=self._headers(),
                        json=payload,
                    )
                    if res.status_code != 200:
                        last_error = f"{model}: HTTP {res.status_code}"
                        logger.error(f"Gemini API error {res.status_code} ({model}): {res.text[:300]}")
                        continue

                    content_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(content_text)
                    raw_items = parsed.get("lessons", []) if isinstance(parsed, dict) else parsed
                    items = [ExtractedLessonItem(**item) for item in raw_items]
                    if not items:
                        raise ValueError("Rasmdan birorta ham dars aniqlanmadi")
                    unify_subject_names_by_code(items)
                    return ExtractedScheduleResult(
                        lessons=items,
                        confidence=0.9,
                        warnings=None,
                        raw_response=content_text,
                    )
                except Exception as e:
                    last_error = f"{model}: {type(e).__name__}: {e}"
                    logger.error(f"Gemini extract error: {last_error}")

        raise RuntimeError(f"Jadval rasmini o'qib bo'lmadi ({last_error})")

    async def chat_student_assistant(self, query: str, context: Dict[str, Any]) -> str:
        url = f"{self.base_url}/{self.CHAT_MODEL}:generateContent"

        system_instruction = (
            "Sen talabalarga dars jadvali, vazifalar va o'qish rejalari bo'yicha yordam beruvchi "
            "samimiy va aqlli 'UniNotify AI Yordamchisi'san. "
            "Faqat berilgan talaba ma'lumotlari (context) ga tayangan holda o'zbek tilida aniq, "
            "londa va rag'batlantiruvchi tarzda javob ber. O'zingdan yolg'on dars yoki xona to'qima."
        )

        prompt = f"Kontekst:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\nTalaba savoli: {query}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {"temperature": 0.3},
        }

        try:
            async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT_SECONDS) as client:
                res = await client.post(url, headers=self._headers(), json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.error(f"Gemini chat error: {e}")

        # Fallback to smart rule-based mock
        return await MockAIProvider().chat_student_assistant(query, context)


class GroqAIProvider(BaseAIProvider):
    """
    Groq (OpenAI bilan mos chat completions API) orqali ishlovchi tezkor AI provayder.
    GROQ_MODEL (masalan "openai/gpt-oss-120b") faqat matnli chat uchun ishlatiladi - bunday
    modellar rasm qabul qila olmaydi, shuning uchun jadval rasmi vision_provider'ga
    (Gemini) topshiriladi.
    """

    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, chat_model: str, vision_provider: Optional["BaseAIProvider"] = None):
        self.api_key = api_key
        self.chat_model = chat_model
        self.vision_provider = vision_provider

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def extract_schedule_from_image(self, image_bytes: bytes, filename: str = "schedule.jpg") -> ExtractedScheduleResult:
        if self.vision_provider:
            return await self.vision_provider.extract_schedule_from_image(image_bytes, filename)
        raise RuntimeError("Rasm o'qish uchun GEMINI_API_KEY kerak: Groq hisobida vision model yo'q")

    async def chat_student_assistant(self, query: str, context: Dict[str, Any]) -> str:
        system_instruction = (
            "Sen talabalarga dars jadvali, vazifalar va o'qish rejalari bo'yicha yordam beruvchi "
            "samimiy va aqlli 'UniNotify AI Yordamchisi'san. "
            "Faqat berilgan talaba ma'lumotlari (context) ga tayangan holda o'zbek tilida aniq, "
            "lo'nda va rag'batlantiruvchi tarzda javob ber. O'zingdan yolg'on dars yoki xona to'qima."
        )
        prompt = f"Kontekst:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\nTalaba savoli: {query}"

        payload = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(self.BASE_URL, headers=self._headers(), json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
                logger.error(f"Groq chat API error {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Groq chat error: {e}")

        # Fallback to smart rule-based mock
        return await MockAIProvider().chat_student_assistant(query, context)


def get_ai_provider() -> BaseAIProvider:
    """AI Provayder fabrikasi"""
    provider = settings.AI_PROVIDER.lower()
    if provider == "gemini" and settings.GEMINI_API_KEY:
        return GeminiAIProvider(api_key=settings.GEMINI_API_KEY)
    if provider == "groq" and settings.GROQ_API_KEY:
        vision_provider = GeminiAIProvider(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
        return GroqAIProvider(api_key=settings.GROQ_API_KEY, chat_model=settings.GROQ_MODEL, vision_provider=vision_provider)
    return MockAIProvider()
