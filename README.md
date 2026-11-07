# UniNotify — Universal University Student Platform

**UniNotify** — barcha oliy ta'lim muassasalari uchun mo‘ljallangan, Telegram Bot va zamonaviy Telegram Mini App asosida ishlaydigan universal talabalar ekotizimi.

---

## 🌟 Asosiy Imkoniyatlar va Arxitektura

### 1. Telegram Bot (Aiogram 3)
- **Avtomatik Ro'yxatdan O'tish**: `/start` bosilganda talaba `USER` sifatida avtomatik ro'yxatga olinadi.
- **Admin Boshqaruvi**: Faqat `.env` ichidagi `ADMIN_IDS` ga tegishli foydalanuvchilar maxsus Administrator boshqaruv paneliga ega bo'ladi.
- **Dars jadvali screenshotlarini qabul qilish**: Talaba rasm yuborganida, Sun'iy intellekt (AI) uni darhol tahlil qilib, darslarni ajratib oladi va tasdiqlash uchun admin navbatiga qo'yadi.
- **Tezkor buyruqlar**: Bugungi darslar, ertangi darslar, shaxsiy vazifalar, jadval holati va sozlamalar.
- **Admin inline tasdiqlash**: Adminlar yangi screenshotlarni to'g'ridan-to'g'ri Telegram bot ichida birgina tugma orqali tasdiqlashi yoki rad etishi mumkin.

### 2. Telegram Mini App (React + TypeScript + Vite + Tailwind CSS)
- **Mobile-First & Telegram Theme Moslashuvi**: Telegram ranglari va tungi/kunduzgi rejim (Dark/Light mode) bilan to'liq integratsiya.
- **Home Dashboard**: Salomlashish, keyingi dars va unga qolgan vaqt countdown'i, bugungi darslar, shaxsiy vazifalar va universitet e'lonlari.
- **Dars Jadvali**: Kunlar bo'yicha qulay tablar (Dush, Sesh, Chor, Pay, Juma, Shan), fan, o'qituvchi, bino, qavat va auditoriya ma'lumotlari.
- **Dars Tafsilotlari**: Har bir darsni bosganda to'liq ma'lumot ko'rsatuvchi interaktiv oyna.
- **Shaxsiy Vazifalar (Tasks)**: Vazifa yaratish, deadline, muhimlik darajasi (Low, Medium, High), checkbox orqali bajarish va o'chirish.
- **Shaxsiy Kalendar**: Imtihonlar, topshiriq muddatlari (deadline) va uchrashuvlar.
- **Universitet E'lonlari**: Muhim e'lonlar pin qilingan holda taqdim etiladi.
- **Profil Sozlamalari**: Universitet, fakultet va guruhni tanlash, dars jadvali screenshotini yuklash va eslatmalarni boshqarish.

### 3. AI Dars Jadvalini Tahlil Qilish & Talaba Yordamchisi
- **AI Provayder Abstraksiyasi (`BaseAIProvider`)**:
  - `MockAIProvider`: API kalitsiz yoki offline test rejimida realistik dars jadvali va smart qoidalar asosidagi javoblar.
  - `GeminiAIProvider`: Google Gemini Multimodal Vision API orqali rasm ichidagi matnlarni va jadvallarni toza JSON formatida ajratib olish.
- **AI Talaba Yordamchisi**:
  - *"Bugun nechta darsim bor?"*
  - *"Keyingi darsim qachon va qaysi xonada?"*
  - *"Ertaga qaysi fanlar bor?"*
  - *"Qaysi vazifalarim yaqin?"*
  - *"Bugungi kun uchun reja tuzib ber"* kabi savollarga talabaning bazadagi joriy holatiga qarab aniq javob beradi.

### 4. Dars Eslatmalari (APScheduler)
- **Asia/Tashkent** vaqt zonasi bo'yicha har bir tasdiqlangan dars boshlanishidan **15 daqiqa oldin** talabaning Telegramiga avtomatik xabar yuboriladi.
- Takroriy xabarlarning oldini olish uchun `NotificationLog` tizimi mavjud.

---

## 📁 Loyiha Strukturasi

```
uninotify/
├── docker-compose.yml                         # To'liq stack (PostgreSQL, Backend, Frontend)
├── .env.example                               # Barcha muhit parametrlari
├── requirements.txt                           # Python kutubxonalari
├── backend/
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── pytest.ini
│   ├── alembic/                               # Database migrations
│   ├── app/
│   │   ├── main.py                            # FastAPI + Lifespan (Bot + Scheduler)
│   │   ├── core/                              # config, database, security (HMAC-SHA256, JWT)
│   │   ├── models/                            # SQLAlchemy 2.0 relying modellar
│   │   ├── schemas/                           # Pydantic v2 sxemalari
│   │   ├── services/                          # Biznes mantiq (University, Schedule, Task, AI)
│   │   ├── api/v1/                            # REST API routerlari
│   │   ├── bot/                               # Aiogram 3 bot (Handlers, Keyboards, Middlewares)
│   │   └── scheduler/                         # APScheduler dars eslatmalari
│   └── tests/                                 # 22 ta avtomatlashtirilgan test
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    └── src/
        ├── App.tsx                            # React router
        ├── context/AuthContext.tsx            # Telegram WebApp auth
        ├── services/api.ts                    # Backend API mijozi
        ├── components/                        # Header, BottomNav, Skeleton, Layout
        └── pages/                             # Home, Schedule, Tasks, Calendar, AIAssistant, Profile
```

---

## 🚀 Ishga Tushirish Yo'riqnomasi

### Usul 1: Docker Compose Orqali (Tavsiya etiladi)

1. Muhit parametrlarini sozlang:
   ```bash
   cp .env.example .env
   # .env ichida BOT_TOKEN va ADMIN_IDS qiymatlarini kiriting
   ```

2. Barcha xizmatlarni bitta buyruq bilan ishga tushiring:
   ```bash
   docker-compose up -d --build
   ```

- **Telegram Mini App (Frontend):** `http://localhost:3000`
- **Backend API (Swagger Docs):** `http://localhost:8000/docs`
- **PostgreSQL Baza:** `localhost:5432`

---

### Usul 2: Lokal Ishga Tushirish

#### 1. Backend & Bot
```powershell
cd backend
# Virtual muhitni faollashtiring
..\.venv\Scripts\Activate.ps1

# Migratsiyalarni bazaga qo'llash
python -m alembic upgrade head

# Testlarni tekshirish (22 ta test)
python -m pytest -q

# Server va Botni ishga tushirish
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Telegram Mini App (Frontend)
```powershell
cd frontend
# Paketlarni o'rnatish
npm install

# Dasturchi rejimida ishga tushirish
npm run dev
# yoki Production build:
npm run build
```

---

## 🛡 Xavfsizlik Tamoyillari
1. **Telegram WebApp HMAC-SHA256**: Frontend tomonidan yuborilgan har bir `initData` serverda rasmiy Telegram kriptografik standarti bo'yicha tekshiriladi.
2. **Rolga asoslangan ruxsat (RBAC)**: Administrator operatsiyalari (`POST /universities`, `POST /schedules`, screenshotlarni tasdiqlash) server-side darajasida tekshiriladi.
3. **Data Isolation**: Talabalar faqat o'zlarining shaxsiy vazifalari va kalendar tadbirlariga kira oladi.
4. **AI Xavfsizligi**: AI API kalitlari hech qachon mijoz (frontend) tomoniga chiqmaydi va faqat backend xizmatida saqlanadi.
