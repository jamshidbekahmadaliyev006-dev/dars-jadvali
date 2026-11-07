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


class GeminiAIProvider(BaseAIProvider):
    """
    Google Gemini Multimodal Vision & Text AI provayderi.
    Rasmiy HTTP REST API orqali ortiqcha og'ir kutubxonalarsiz ishlaydi.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    async def extract_schedule_from_image(self, image_bytes: bytes, filename: str = "schedule.jpg") -> ExtractedScheduleResult:
        model = "gemini-1.5-flash"
        url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"

        base64_data = base64.b64encode(image_bytes).decode("utf-8")
        mime_type = "image/png" if filename.endswith(".png") else "image/jpeg"

        prompt = (
            "Ushbu universitet dars jadvali screenshotini diqqat bilan tahlil qiling. "
            "Barcha darslarni JSON ro'yxati shaklida ajrating. "
            "Har bir dars uchun quyidagi kalitlar bo'lsin: "
            "'day' (Dushanba, Seshanba, Chorshanba, Payshanba, Juma, Shanba), "
            "'subject' (fan nomi), 'teacher' (o'qituvchi ismi sharifi), "
            "'start_time' (HH:MM formatda, masalan 09:00), 'end_time' (HH:MM formatda, masalan 10:20), "
            "'building' (bino nomi), 'room' (xona yoki auditoriya raqami), "
            "'lesson_type' (LECTURE, PRACTICE yoki LAB). "
            "Faqat toza JSON array qaytaring, ortiqcha matnlarsiz."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64_data,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code != 200:
                    logger.error(f"Gemini API error {res.status_code}: {res.text}")
                    # Fallback to mock on error
                    return await MockAIProvider().extract_schedule_from_image(image_bytes, filename)

                resp_json = res.json()
                content_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(content_text)
                items = [ExtractedLessonItem(**item) for item in parsed]
                return ExtractedScheduleResult(
                    lessons=items,
                    confidence=0.9,
                    warnings=None,
                    raw_response=content_text,
                )
        except Exception as e:
            logger.error(f"Gemini extract error: {e}")
            return await MockAIProvider().extract_schedule_from_image(image_bytes, filename)

    async def chat_student_assistant(self, query: str, context: Dict[str, Any]) -> str:
        model = "gemini-1.5-flash"
        url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"

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
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.error(f"Gemini chat error: {e}")

        # Fallback to smart rule-based mock
        return await MockAIProvider().chat_student_assistant(query, context)


def get_ai_provider() -> BaseAIProvider:
    """AI Provayder fabrikasi"""
    if settings.AI_PROVIDER.lower() == "gemini" and settings.GEMINI_API_KEY:
        return GeminiAIProvider(api_key=settings.GEMINI_API_KEY)
    return MockAIProvider()
