from abc import ABC, abstractmethod
import asyncio
import base64
import json
import time
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.schemas.ai import ExtractedLessonItem, ExtractedScheduleResult


def _detect_image_mime(data: bytes, filename: str = "") -> str:
    """Fayl sifatida yuborilgan rasm PNG yoki WEBP bo'lishi mumkin - turini baytlardan aniqlaymiz"""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if filename.lower().endswith(".png"):
        return "image/png"
    return "image/jpeg"


class BaseAIProvider(ABC):
    """Barcha AI provayderlari (Gemini, OpenAI, Mock) uchun unifikatsiyalangan interfeys"""

    @abstractmethod
    async def extract_schedule_from_image(self, image_bytes: bytes, filename: str = "schedule.jpg") -> ExtractedScheduleResult:
        """Dars jadvali screenshotidan darslarni strukturali JSON ko'rinishida ajratib olish"""
        pass

    async def judge_name(self, kind: str, value: str) -> Optional[bool]:
        """Nom haqiqiy universitet/fakultet/kafedraga o'xshaydimi; bilib bo'lmasa None"""
        return None

    async def resolve_faculty(self, typed: str, existing: List[str]) -> Optional[Dict[str, Any]]:
        """
        Yozilgan fakultet nomini mavjud fakultetlarga moslaydi.
        {"match": mavjud nom | None, "complete": bool, "canonical": to'liq nom | None}; bilib bo'lmasa None.
        """
        return None

    async def extract_schedule_from_images(
        self, images: List[bytes], filenames: Optional[List[str]] = None
    ) -> ExtractedScheduleResult:
        """Standart: rasmlar navbatma-navbat o'qiladi va darslar birlashtiriladi (takrorlarsiz)"""
        lessons, seen = [], set()
        for index, data in enumerate(images):
            name = (filenames or [])[index] if filenames and index < len(filenames) else "schedule.jpg"
            result = await self.extract_schedule_from_image(data, name)
            for lesson in result.lessons:
                key = (lesson.day, lesson.start_time, lesson.subject, lesson.week_parity)
                if key not in seen:
                    seen.add(key)
                    lessons.append(lesson)
        return ExtractedScheduleResult(lessons=lessons, confidence=0.9)

    async def extract_schedule_from_text(self, text: str) -> ExtractedScheduleResult:
        """Talaba qo'lda yozgan jadval matnidan darslarni ajratib olish"""
        raise RuntimeError("Bu AI provayderi jadval matnini o'qiy olmaydi")

    @abstractmethod
    async def chat_student_assistant(self, query: str, context: Dict[str, Any]) -> str:
        """Talabaga darslar, vazifalar va rejalar bo'yicha yordam beruvchi AI assistant"""
        pass


class MockAIProvider(BaseAIProvider):
    """
    Offline va test rejimida yoki API key bo'lmaganda ishlovchi Mock provayder.
    Tizimni to'xtatib qo'ymasdan realistik ma'lumotlar bilan ta'minlaydi.
    """

    async def extract_schedule_from_text(self, text: str) -> ExtractedScheduleResult:
        return await self.extract_schedule_from_image(b"")

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

    # Yengil modellar real jadval rasmini ~5 soniyada o'qiydi; gemini-flash-latest esa band
    # paytda 503 qaytarib, 40 soniyadan ko'proq ushlab turadi. Birinchisi ishlamasa ikkinchisi.
    # Tez modellar oldinda; ular band bo'lsa (503) zaxira modellar ishlatiladi
    VISION_MODELS = (
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-2.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-2.5-flash",
    )
    CHAT_MODEL = "gemini-3.5-flash-lite"
    REQUEST_TIMEOUT_SECONDS = 30.0
    TOTAL_BUDGET_SECONDS = 75.0

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def _headers(self) -> Dict[str, str]:
        # Kalit URL'da emas, sarlavhada: URL'lar loglarga yoziladi
        return {"x-goog-api-key": self.api_key}

    JSON_FORMAT = (
        "Faqat JSON massiv qaytaring, har bir element kalitlari: "
        "day (Dushanba, Seshanba, Chorshanba, Payshanba, Juma, Shanba, Yakshanba), subject, "
        "teacher (yo'q bo'lsa null), start_time (HH:MM), end_time (HH:MM), building (yo'q bo'lsa null), "
        "room (yo'q bo'lsa null), lesson_type (LECTURE, PRACTICE, LAB, SEMINAR yoki OTHER), "
        "week_parity (toq hafta=ODD, juft hafta=EVEN, belgi bo'lmasa=ALL), "
        "group (dars qaysi guruh bilan - guruh nomi ko'rinsa, masalan '712-24'; o'qituvchi jadvalida muhim; bo'lmasa null)."
    )

    async def extract_schedule_from_text(self, text: str) -> ExtractedScheduleResult:
        prompt = (
            "Talaba o'z haftalik dars jadvalini matn ko'rinishida yozdi (o'zbek yoki rus tilida, "
            "qisqartmalar bilan bo'lishi mumkin: Du/Dush=Dushanba, Se/Sesh=Seshanba, Pn=Dushanba va h.k.). "
            "Har bir darsni ajrating. Vaqt 8.00, 8:00 yoki 800 kabi yozilishi mumkin - HH:MM ga keltiring. "
            "Tugash vaqti yozilmagan bo'lsa, boshlanishiga 80 daqiqa qo'shing. "
            "Fan nomlarini talaba yozganidek qoldiring. Xonani harflari va belgilari bilan aynan ko'chiring "
            "(masalan 'A-327' bo'lsa 'A-327', '327' emas). Hech narsa to'qimang. Matnda jadval bo'lmasa, [] qaytaring. "
            + self.JSON_FORMAT
            + "\n\nMatn:\n"
            + text[:4000]
        )
        return await self._extract({"contents": [{"parts": [{"text": prompt}]}]})

    async def extract_schedule_from_image(self, image_bytes: bytes, filename: str = "schedule.jpg") -> ExtractedScheduleResult:
        return await self.extract_schedule_from_images([image_bytes], [filename])

    async def extract_schedule_from_images(
        self, images: List[bytes], filenames: Optional[List[str]] = None
    ) -> ExtractedScheduleResult:
        """Bir yoki bir nechta rasm (bitta jadvalning qismlari) - bitta so'rovda birga o'qiladi"""
        filenames = filenames or ["schedule.jpg"] * len(images)
        multi = (
            f"Sizga {len(images)} ta rasm berildi - bu BITTA guruhning bitta jadvalining qismlari (masalan turli kunlar, "
            "turli haftalar yoki ekranning turli bo'laklari). Hamma rasmlardagi darslarni birlashtirib bitta ro'yxat "
            "qiling. Bir xil darsni (kun, vaqt, fan bir xil) ikki marta yozmang.\n"
            if len(images) > 1 else ""
        )

        prompt = multi + (
            "Bu universitet haftalik dars jadvali rasmi. U har xil ko'rinishda bo'lishi mumkin: HEMIS skrinshoti "
            "(rangli bloklar), Excel/Word jadvali, qog'ozdagi jadval fotosi, telefon skrinshoti, o'zbek yoki rus tilida. "
            "Avval jadval tuzilishini aniqlang: kunlar ustunlardami yoki qatorlarda, vaqt qayerda yozilgan.\n"
            "- Har bir blok yoki katak bitta dars. Bo'sh kataklarni o'tkazib yuboring.\n"
            "- Vaqt blok ichida yoki chap/yuqoridagi vaqt o'qida bo'ladi. Tugash vaqti yozilmagan bo'lsa, "
            "blok balandligi va vaqt o'qidan aniqlang. Faqat para raqami (1-para, 2-para) bo'lsa va jadvalda "
            "paralar vaqti yozilgan bo'lsa - o'shandan oling.\n"
            "- Bir vaqtda yonma-yon ikkita blok bo'lsa (masalan 'Toq hafta' va 'Juft hafta'), ikkalasini ham yozing.\n"
            "- Har bir kunning barcha darslarini oxirigacha o'qing, birortasini ham tashlab ketmang.\n"
            "XONA VA BINO - diqqat bilan:\n"
            "- Xona ko'pincha qavs ichida yoziladi: '(A-327)', '(3-407)', '(B blok-214)'. Tire oldidagi qism BINO "
            "(harf, raqam yoki nom), keyingi qism XONA raqami. building ga faqat binoni ('A', '3', 'B blok'), "
            "room ga faqat xona raqamini ('327') yozing.\n"
            "- Bino harf/raqam emas, ikonka bilan chizilgan yoki o'qib bo'lmasa, building = null. "
            "room hech qachon tire bilan boshlanmasin ('-407' emas, '407').\n"
            "Fan nomi qator oxirida kesilib so'z bo'linib qolgan bo'lsa (masalan 'texnologiyalar' + 'i'), so'zni to'liq "
            "('texnologiyalari') yozing; nom ichida '/' belgisini yozmang. Bir fan kodi (masalan DLT001) hamma joyda "
            "bir xil nom bilan yozilsin.\n"
            "Fan nomi va kodini aynan, harfma-harf ko'chiring. Fan nomidan keyingi kodni (masalan ISE001) hech qachon "
            "ochib, tarjima qilib yoki boshqa fan nomi bilan almashtirib yozmang, kod ma'nosini taxmin qilmang: "
            "nom faqat rasmda yozilgan matn bo'lsin. O'qituvchi ko'rinsa teacher ga yozing. Dars turi ko'rinsa "
            "(ma'ruza=LECTURE, amaliy=PRACTICE, laboratoriya=LAB, seminar=SEMINAR), aks holda OTHER. "
            "GURUH: rasmning sarlavhasida yoki darslarda guruh nomi (masalan '712-24') ko'rinsa, uni har bir "
            "darsning group maydoniga yozing; ko'rinmasa null.\n"
            "Faqat rasmda ko'ringan narsani yozing, hech narsa to'qimang. Rasm dars jadvali bo'lmasa, [] qaytaring. "
            + self.JSON_FORMAT
        )

        parts: List[Dict[str, Any]] = [{"text": prompt}]
        for data, name in zip(images, filenames):
            parts.append({"inline_data": {
                "mime_type": _detect_image_mime(data, name),
                "data": base64.b64encode(data).decode("utf-8"),
            }})
        return await self._extract({"contents": [{"parts": parts}]})

    async def _extract(self, payload: Dict[str, Any]) -> ExtractedScheduleResult:
        payload = {
            **payload,
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0,
            },
        }

        # Xato bo'lsa namuna ma'lumot QAYTARILMAYDI: soxta darslar haqiqiy jadvalga yozilib ketardi
        last_error = "noma'lum xato"
        deadline = time.monotonic() + self.TOTAL_BUDGET_SECONDS
        # Gemini band bo'lsa (503/429) keyingi modelga o'tamiz; hammasi band bo'lsa bir oz kutib yana bir aylana
        attempts = [m for m in self.VISION_MODELS] + [m for m in self.VISION_MODELS[:2]]
        async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT_SECONDS) as client:
            for index, model in enumerate(attempts):
                if time.monotonic() > deadline:
                    break
                if index == len(self.VISION_MODELS):
                    await asyncio.sleep(2)
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
            "samimiy va aqlli 'Qulay Jadval AI yordamchisi'san. "
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

    async def extract_schedule_from_images(
        self, images: List[bytes], filenames: Optional[List[str]] = None
    ) -> ExtractedScheduleResult:
        if self.vision_provider:
            return await self.vision_provider.extract_schedule_from_images(images, filenames)
        raise RuntimeError("Rasm o'qish uchun GEMINI_API_KEY kerak: Groq hisobida vision model yo'q")

    async def extract_schedule_from_text(self, text: str) -> ExtractedScheduleResult:
        if self.vision_provider:
            return await self.vision_provider.extract_schedule_from_text(text)
        raise RuntimeError("Jadval matnini o'qish uchun GEMINI_API_KEY kerak")

    async def resolve_faculty(self, typed: str, existing: List[str]) -> Optional[Dict[str, Any]]:
        known = "; ".join(existing[:60]) or "(hali yo'q)"
        payload = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": (
                    "Siz O'zbekiston universiteti fakultetlari bo'yicha mutaxassissiz. Talaba o'z fakultetini yozdi. "
                    "Uni quyidagi MAVJUD fakultetlar ro'yxatiga moslang. Talaba o'zbek (lotin), rus yoki ingliz tilida, "
                    "qisqartma yoki imlo xatosi bilan yozishi mumkin ('Kiber', 'KIF', 'Кибербезопасность', 'Kompyuter engineering' "
                    "kabilar - bular mavjud 'Kiberxavfsizlik' va 'Kompyuter injiniringi' fakultetlari).\n"
                    f"MAVJUD fakultetlar: {known}\n"
                    "Javob faqat JSON: {\"match\": mavjud fakultetning AYNAN o'sha nomi yoki null, "
                    "\"complete\": true/false, \"canonical\": to'liq rasmiy nom (o'zbek lotin, bosh harf bilan) yoki null}.\n"
                    "Qoidalar: (1) yozilgan nom mavjud fakultetlardan birining boshqacha yozilishi bo'lsa - match shu nom. "
                    "(2) match yo'q bo'lsa va yozilgan nom to'liq, tushunarli fakultet nomi bo'lsa - complete=true va canonical "
                    "to'liq nom. (3) Yozilgan nom qisqartma yoki bo'lak bo'lsa va uni aniq bitta to'liq nomga yoyib bo'lmasa - "
                    "complete=false."
                )},
                {"role": "user", "content": typed[:120]},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(self.BASE_URL, headers=self._headers(), json=payload)
                if res.status_code == 429:  # tezlik chegarasi: bir marta kutib qayta uriniladi
                    await asyncio.sleep(2)
                    res = await client.post(self.BASE_URL, headers=self._headers(), json=payload)
            if res.status_code != 200:
                logger.error(f"Groq resolve_faculty error {res.status_code}")
                return None
            data = json.loads(res.json()["choices"][0]["message"]["content"])
            match = data.get("match")
            if match not in existing:
                match = None
            return {
                "match": match,
                "complete": bool(data.get("complete", True)),
                "canonical": (data.get("canonical") or "").strip() or None,
            }
        except Exception as e:
            logger.error(f"Groq resolve_faculty failed: {type(e).__name__}")
            return None

    async def judge_name(self, kind: str, value: str) -> Optional[bool]:
        what = {
            "university": "oliy ta'lim muassasasi (universitet, institut, akademiya) nomi yoki uning qisqartmasi",
            "faculty": "universitet fakulteti yoki kafedrasi nomi (masalan Kiberxavfsizlik, Iqtisodiyot, Matematika) yoki uning qisqartmasi",
        }.get(kind, kind)
        payload = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": (
                    "Siz ro'yxatdan o'tish formasini tekshiruvchisiz. Foydalanuvchi yozgan matn haqiqatan "
                    f"{what} bo'lishi mumkinmi? O'zbek, rus yoki ingliz tilida, imlo xatosi bilan bo'lishi mumkin - "
                    "bunday holatda ham ha. Haqorat, so'kinish, ovqat nomi, tasodifiy harflar, hazil, "
                    "odam ismi yoki mavzuga aloqasiz so'z bo'lsa - yo'q. "
                    'Faqat JSON qaytaring: {"ok": true} yoki {"ok": false}.'
                )},
                {"role": "user", "content": value[:120]},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(self.BASE_URL, headers=self._headers(), json=payload)
            if res.status_code != 200:
                logger.error(f"Groq judge_name error {res.status_code}")
                return None
            content = res.json()["choices"][0]["message"]["content"]
            return bool(json.loads(content).get("ok"))
        except Exception as e:
            logger.error(f"Groq judge_name failed: {type(e).__name__}")
            return None

    async def chat_student_assistant(self, query: str, context: Dict[str, Any]) -> str:
        system_instruction = (
            "Sen talabalarga dars jadvali, vazifalar va o'qish rejalari bo'yicha yordam beruvchi "
            "samimiy va aqlli 'Qulay Jadval AI yordamchisi'san. "
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
