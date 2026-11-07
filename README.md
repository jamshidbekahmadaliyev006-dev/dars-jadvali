# UniNotify — Universal University Student Platform

UniNotify — barcha universitetlar uchun mo‘ljallangan, Telegram Bot va Telegram Mini App asosida ishlaydigan universal talabalar platformasi.

---

## 🚀 Joriy holat: Phase 1 — Bajarildi

Ushbu bosqichda quyidagi asosiy poydevor yaratildi:
1. **Monolit modulli backend arxitekturasi** (FastAPI + SQLAlchemy 2.0 Async + Pydantic v2).
2. **To'liq relyatsion ma'lumotlar bazasi modellari** (Alembic migratsiyalari bilan `universities`, `faculties`, `groups`, `buildings`, `rooms`, `subjects`, `teachers`, `users`, `schedules`, `schedule_submissions`, `reminder_settings`, `personal_tasks`, `personal_events`, `announcements`, `notification_logs`, `ai_processing_logs`).
3. **Rolga asoslangan kirish nazorati (RBAC)**:
   - `USER` (oddiy talaba) — `/start` bosganda avtomatik ro'yxatdan o'tadi va talaba menyusi ko'rsatiladi.
   - `ADMIN` (administrator) — faqat tizim konfiguratsiyasidagi `ADMIN_IDS` orqali tan olinadi va maxsus boshqaruv menyusiga ega bo'ladi.
4. **Telegram Bot (Aiogram 3.x)**:
   - `DbSessionMiddleware` (har bir xabar uchun async database session).
   - `AuthMiddleware` (foydalanuvchini avtomatik identifikatsiya qilish va contextga yuklash).
   - Foydalanuvchi roliga qarab moslashuvchi ReplyKeyboardMarkup (Talaba va Admin menyulari) hamda Mini App ochish tugmalari.
5. **Xavfsizlik & Telegram Mini App integratsiyasi**:
   - Rasmiy Telegram WebApp `initData` HMAC-SHA256 validatsiya servisi.
   - JWT autentifikatsiya mexanizmi (`/api/v1/auth/telegram-webapp`).
   - Admin ruxsatini talab qiluvchi dependency (`require_admin`).
6. **Background Task Scheduler**:
   - `APScheduler` (Asia/Tashkent vaqt zonasi bilan) integratsiyasi va FastAPI lifespan bilan toza start/stop.
7. **Keng qamrovli testlar**:
   - Pytest orqali 17 ta avtomatlashtirilgan test (API, Auth HMAC/JWT, Database & Modellar, UserService va Bot handlerlari).

---

## 📁 Loyiha Strukturasi

```
uninotify/
├── .env.example              # Muhit o'zgaruvchilari namunasi
├── .env                      # Faol muhit konfiguratsiyasi
├── .gitignore                # Git e'tiborsiz qoldiradigan fayllar
├── README.md                 # Loyiha hujjatlari
├── requirements.txt          # Python kutubxonalari
└── backend/
    ├── alembic.ini           # Alembic migratsiya konfiguratsiyasi
    ├── pytest.ini            # Pytest sozlamalari
    ├── alembic/              # Baza migratsiyalari
    │   ├── env.py
    │   └── versions/
    │       └── b1418bf5669c_initial_phase_1_tables.py
    ├── app/
    │   ├── main.py           # FastAPI ilovasi va bot/scheduler lifespan
    │   ├── core/             # Konfiguratsiya, baza, xavfsizlik va loglar
    │   │   ├── config.py
    │   │   ├── database.py
    │   │   ├── security.py
    │   │   └── logging.py
    │   ├── models/           # SQLAlchemy 2.0 ma'lumotlar modellari
    │   │   ├── base.py
    │   │   ├── enums.py
    │   │   ├── user.py
    │   │   ├── university.py
    │   │   ├── schedule.py
    │   │   ├── task.py
    │   │   └── log.py
    │   ├── schemas/          # Pydantic v2 sxemalari
    │   │   ├── user.py
    │   │   ├── auth.py
    │   │   └── response.py
    │   ├── services/         # Biznes mantiq
    │   │   ├── user_service.py
    │   │   └── auth_service.py
    │   ├── api/              # FastAPI routerlar
    │   │   ├── deps.py
    │   │   └── v1/
    │   │       ├── api_router.py
    │   │       ├── auth.py
    │   │       ├── users.py
    │   │       └── health.py
    │   ├── bot/              # Aiogram 3 Telegram Bot
    │   │   ├── bot_instance.py
    │   │   ├── dispatcher.py
    │   │   ├── keyboards/
    │   │   │   ├── reply.py
    │   │   │   └── inline.py
    │   │   ├── middlewares/
    │   │   │   ├── db_session.py
    │   │   │   └── auth.py
    │   │   └── handlers/
    │   │       ├── start.py
    │   │       ├── user_menu.py
    │   │       └── admin_menu.py
    │   └── scheduler/        # APScheduler moduli
    │       └── setup.py
    └── tests/                # Testlar to'plami
        ├── conftest.py
        ├── test_api.py
        ├── test_auth.py
        ├── test_bot_handlers.py
        ├── test_models.py
        └── test_user_service.py
```

---

## 🛠 O'rnatish va Ishga Tushirish

### 1. Muhitni tayyorlash
```powershell
cd C:\Users\Jamshidbek\.gemini\antigravity\scratch\uninotify
# Virtual muhitni faollashtirish
.\.venv\Scripts\Activate.ps1
```

### 2. Konfiguratsiya
`.env` faylida haqiqiy Telegram Bot tokeni va admin ID'larini kiriting:
```ini
BOT_TOKEN="sizning_telegram_bot_tokeningiz"
ADMIN_IDS="sizning_telegram_id_ingiz"
DATABASE_URL="sqlite+aiosqlite:///./uninotify.db"
TIMEZONE="Asia/Tashkent"
```

### 3. Migratsiyalarni qo'llash
```powershell
cd backend
python -m alembic upgrade head
```

### 4. Server va Botni ishga tushirish
```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Swagger UI hujjatlari: `http://localhost:8000/docs`

### 5. Testlarni o'tkazish
```powershell
cd backend
python -m pytest -v
```

---

## 🔮 Keyingi Bosqichlar (Roadmap)
- **Phase 2:** Universitet, fakultet, guruh, bino va xona ma’lumotlarini boshqarish CRUD API va bot integratsiyasi.
- **Phase 3:** Screenshot yuborish va admin review workflow.
- **Phase 4:** AI orqali screenshotdan dars jadvalini ajratish (Gemini Multimodal / OCR service).
- **Phase 5:** Dars eslatmalari (15 daqiqa oldin) va APScheduler jobs.
- **Phase 6:** Telegram Mini App frontend (React, Vite, Tailwind CSS, Telegram WebApp SDK).
- **Phase 7:** Mini App dars jadvali va talaba dashboardi.
- **Phase 8:** Shaxsiy vazifalar, kalendar va bildirishnomalar.
- **Phase 9:** AI student assistant.
- **Phase 10:** Production deployment, monitoring va performance xavfsizlik auditi.
