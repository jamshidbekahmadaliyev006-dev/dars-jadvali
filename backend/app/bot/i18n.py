from typing import Any, Dict, Set
from app.models.enums import DayOfWeek, SubmissionStatus, WeekParity

DEFAULT_LANG = "uz"
LANGUAGES = ("uz", "ru", "en")

DAY_LABELS: Dict[str, Dict[DayOfWeek, str]] = {
    "uz": {
        DayOfWeek.MONDAY: "Dushanba",
        DayOfWeek.TUESDAY: "Seshanba",
        DayOfWeek.WEDNESDAY: "Chorshanba",
        DayOfWeek.THURSDAY: "Payshanba",
        DayOfWeek.FRIDAY: "Juma",
        DayOfWeek.SATURDAY: "Shanba",
        DayOfWeek.SUNDAY: "Yakshanba",
    },
    "ru": {
        DayOfWeek.MONDAY: "Понедельник",
        DayOfWeek.TUESDAY: "Вторник",
        DayOfWeek.WEDNESDAY: "Среда",
        DayOfWeek.THURSDAY: "Четверг",
        DayOfWeek.FRIDAY: "Пятница",
        DayOfWeek.SATURDAY: "Суббота",
        DayOfWeek.SUNDAY: "Воскресенье",
    },
}

DAY_LABELS["en"] = {
    DayOfWeek.MONDAY: "Monday", DayOfWeek.TUESDAY: "Tuesday", DayOfWeek.WEDNESDAY: "Wednesday",
    DayOfWeek.THURSDAY: "Thursday", DayOfWeek.FRIDAY: "Friday", DayOfWeek.SATURDAY: "Saturday",
    DayOfWeek.SUNDAY: "Sunday",
}

PARITY_LABELS: Dict[str, Dict[WeekParity, str]] = {
    "uz": {WeekParity.ODD: "toq hafta", WeekParity.EVEN: "juft hafta"},
    "ru": {WeekParity.ODD: "нечётная неделя", WeekParity.EVEN: "чётная неделя"},
}

STATUS_LABELS: Dict[str, Dict[SubmissionStatus, str]] = {
    "uz": {
        SubmissionStatus.PENDING: "⏳ Qabul qilindi",
        SubmissionStatus.AI_PROCESSING: "⏳ O'qilmoqda",
        SubmissionStatus.AI_COMPLETED: "⏳ O'qildi",
        SubmissionStatus.ADMIN_REVIEW: "🔍 Admin tekshiruvida",
        SubmissionStatus.APPROVED: "✅ Tasdiqlangan",
        SubmissionStatus.REJECTED: "❌ Rad etilgan",
        SubmissionStatus.NEEDS_CORRECTION: "⚠️ O'qib bo'lmadi",
    },
    "ru": {
        SubmissionStatus.PENDING: "⏳ Принято",
        SubmissionStatus.AI_PROCESSING: "⏳ Распознаётся",
        SubmissionStatus.AI_COMPLETED: "⏳ Распознано",
        SubmissionStatus.ADMIN_REVIEW: "🔍 На проверке у админа",
        SubmissionStatus.APPROVED: "✅ Подтверждено",
        SubmissionStatus.REJECTED: "❌ Отклонено",
        SubmissionStatus.NEEDS_CORRECTION: "⚠️ Не удалось распознать",
    },
}

PARITY_LABELS["en"] = {WeekParity.ODD: "odd week", WeekParity.EVEN: "even week"}
STATUS_LABELS["en"] = {
    SubmissionStatus.PENDING: "⏳ Received",
    SubmissionStatus.AI_PROCESSING: "⏳ Reading",
    SubmissionStatus.AI_COMPLETED: "⏳ Read",
    SubmissionStatus.ADMIN_REVIEW: "🔍 Under admin review",
    SubmissionStatus.APPROVED: "✅ Approved",
    SubmissionStatus.REJECTED: "❌ Rejected",
    SubmissionStatus.NEEDS_CORRECTION: "⚠️ Could not read",
}

NL = chr(10)  # matnlarda qator ko'chishi

TEXTS: Dict[str, Dict[str, str]] = {
    # Menyu tugmalari
    "btn_week": {"uz": "📅 Dars jadvali", "ru": "📅 Расписание"},
    "btn_today": {"uz": "📖 Bugun", "ru": "📖 Сегодня"},
    "btn_tomorrow": {"uz": "📆 Ertaga", "ru": "📆 Завтра"},
    "btn_reminder": {"uz": "⏰ Eslatma", "ru": "⏰ Напоминание"},
    "btn_profile": {"uz": "👤 Profil", "ru": "👤 Профиль"},
    "btn_contact": {"uz": "✉️ Murojaat", "ru": "✉️ Обращение"},
    "btn_send": {"uz": "📤 Jadval yuborish", "ru": "📤 Отправить расписание"},
    "btn_language": {"uz": "🌐 Til", "ru": "🌐 Язык"},
    "btn_status": {"uz": "📊 Jadval holati", "ru": "📊 Статус расписания"},
    "btn_new_shots": {"uz": "📥 Jadvallar", "ru": "📥 Расписания"},
    "btn_stats": {"uz": "📈 Statistika", "ru": "📈 Статистика"},
    "btn_groups": {"uz": "👥 Guruhlar", "ru": "👥 Группы"},
    "btn_users": {"uz": "👤 Foydalanuvchilar", "ru": "👤 Пользователи"},
    "btn_announce": {"uz": "📢 E'lon yuborish", "ru": "📢 Отправить объявление"},
    "btn_student_view": {"uz": "🎓 Talaba rejimi", "ru": "🎓 Режим студента"},
    "btn_admin_back": {"uz": "🛠 Admin paneliga qaytish", "ru": "🛠 Вернуться в админ-панель"},
    # Inline tugmalar
    "btn_approve": {"uz": "✅ Tasdiqlash", "ru": "✅ Подтвердить"},
    "btn_reject": {"uz": "❌ Rad etish", "ru": "❌ Отклонить"},
    "btn_send_now": {"uz": "✅ Yuborish", "ru": "✅ Отправить"},
    "btn_cancel": {"uz": "❌ Bekor qilish", "ru": "❌ Отмена"},
    "btn_15": {"uz": "15 daqiqa", "ru": "15 минут"},
    "btn_30": {"uz": "Yarim soat", "ru": "Полчаса"},
    "btn_45": {"uz": "45 daqiqa", "ru": "45 минут"},
    "btn_60": {"uz": "1 soat", "ru": "1 час"},
    "btn_change_group": {"uz": "🔄 Guruhni o'zgartirish", "ru": "🔄 Сменить группу"},
    "btn_change_language": {"uz": "🌐 Tilni o'zgartirish", "ru": "🌐 Сменить язык"},
    "btn_week_all": {"uz": "🗓 Hafta", "ru": "🗓 Неделя"},
    "btn_reply": {"uz": "↩️ Javob berish", "ru": "↩️ Ответить"},
    # Murojaat
    "contact_prompt": {
        "uz": "✉️ <b>Murojaat</b>\n\nSavol, taklif yoki muammoingizni yozing — u adminga yuboriladi.",
        "ru": "✉️ <b>Обращение</b>\n\nНапишите вопрос, предложение или проблему — оно уйдёт администратору.",
    },
    "contact_sent": {
        "uz": "✅ Murojaatingiz adminga yuborildi. Javob shu yerga keladi.",
        "ru": "✅ Обращение отправлено администратору. Ответ придёт сюда.",
    },
    "contact_cancelled": {
        "uz": "↩️ Murojaat bekor qilindi. Kerakli tugmani qayta bosing.",
        "ru": "↩️ Обращение отменено. Нажмите нужную кнопку ещё раз.",
    },
    "contact_no_admin": {
        "uz": "⚠️ Hozircha admin ulanmagan. Keyinroq urinib ko'ring.",
        "ru": "⚠️ Администратор пока не подключён. Попробуйте позже.",
    },
    "contact_new": {
        "uz": "✉️ <b>Yangi murojaat</b>\n\n👤 {who}\n\n{text}",
        "ru": "✉️ <b>Новое обращение</b>\n\n👤 {who}\n\n{text}",
    },
    "contact_reply_prompt": {
        "uz": "↩️ {who} uchun javob matnini yozing:",
        "ru": "↩️ Напишите ответ для {who}:",
    },
    "contact_reply_sent": {"uz": "✅ Javob yuborildi.", "ru": "✅ Ответ отправлен."},
    "contact_reply_failed": {"uz": "❗ Javobni yetkazib bo'lmadi.", "ru": "❗ Не удалось доставить ответ."},
    "contact_from_admin": {
        "uz": "💬 <b>Admin javobi</b>\n\n{text}",
        "ru": "💬 <b>Ответ администратора</b>\n\n{text}",
    },
    "issues_header": {
        "uz": "⚠️ <b>Jadvalingizda tekshirish kerak bo'lgan joylar:</b>",
        "ru": "⚠️ <b>В расписании есть места, которые нужно проверить:</b>",
    },
    "issues_more": {"uz": "… va yana {n} ta", "ru": "… и ещё {n}"},
    "issues_footer": {
        "uz": "Xato bo'lsa: 📅 Dars jadvali → <b>🔄 Jadval o'zgardi</b> orqali to'g'ri rasm yoki matn yuboring.",
        "ru": "Если есть ошибка: 📅 Расписание → <b>🔄 Расписание изменилось</b> и отправьте верное фото или текст.",
    },
    "issues_file_tip": {
        "uz": "🏢 Bino rasmda ikonka bilan chizilgan yoki juda mayda. Jadvalni <b>fayl qilib</b> yuborsangiz "
              "(📎 → Fayl → rasm), Telegram uni siqmaydi va bino ham o'qilishi mumkin.",
        "ru": "🏢 Корпус на фото нарисован иконкой или слишком мелкий. Отправьте расписание <b>файлом</b> "
              "(📎 → Файл → фото) - Telegram не сожмёт его, и корпус может распознаться.",
    },
    "issue_day": {"uz": "kun aniqlanmadi (saqlanmadi)", "ru": "день не распознан (не сохранено)"},
    "issue_time": {"uz": "vaqt to'liq emas (saqlanmadi)", "ru": "время неполное (не сохранено)"},
    "issue_time_order": {"uz": "tugash vaqti boshlanishidan oldin", "ru": "конец раньше начала"},
    "issue_room": {"uz": "xona ko'rsatilmagan", "ru": "аудитория не указана"},
    "issue_building": {"uz": "bino aniqlanmadi", "ru": "корпус не распознан"},
    "issue_building_many": {
        "uz": "{n} ta darsda bino aniqlanmadi (xonalar: {rooms})",
        "ru": "у {n} занятий не распознан корпус (аудитории: {rooms})",
    },
    "issue_overlap": {
        "uz": "«{a}» va «{b}» vaqti ustma-ust tushadi",
        "ru": "«{a}» и «{b}» пересекаются по времени",
    },
    "btn_schedule_changed": {"uz": "🔄 Jadval o'zgardi", "ru": "🔄 Расписание изменилось"},
    "review_buttons": {
        "uz": "👆 <b>Jadval #{id}</b> — {n} ta rasm. Tekshirib, qaror qiling:",
        "ru": "👆 <b>Расписание #{id}</b> — фото: {n}. Проверьте и решите:",
    },
    "schedule_partial": {
        "uz": "⚠️ <b>Bu jadval to'liq emas</b>, shuning uchun saqlanmadi."+NL+NL+"Rasmda faqat: {days} ({lessons}) ko'rindi."+NL+NL+"Iltimos, <b>butun haftalik jadvalni</b> (Dushanbadan Shanbagacha, hamma kunlar) yuboring. Jadval bir rasmga sig'masa, bir nechta rasmni <b>birga</b> (albom qilib) yuboring - bot ularni bitta jadval qilib o'qiydi.",
        "ru": "⚠️ <b>Расписание неполное</b>, поэтому не сохранено."+NL+NL+"На фото видно только: {days} ({lessons})."+NL+NL+"Пожалуйста, отправьте <b>расписание на всю неделю</b> (с понедельника по субботу, все дни). Если оно не помещается на одно фото, отправьте несколько фото <b>вместе</b> (альбомом) - бот прочитает их как одно расписание.",
    },
    "schedule_blurry": {
        "uz": "📷 <b>Rasm mayda ko'rinyapti</b> - xona raqami yoki vaqt noto'g'ri o'qilgan bo'lishi mumkin."+NL+NL+"Jadvalni tekshiring. Xato bo'lsa, <b>yaqinroqdan, tiniqroq</b> qayta yuboring: jadvalni telefonda kattalashtirib skrinshot oling yoki rasmni <b>fayl</b> qilib yuboring (📎 → Fayl).",
        "ru": "📷 <b>Фото выглядит мелким</b> - номер аудитории или время могли прочитаться неточно."+NL+NL+"Проверьте расписание. Если есть ошибки, отправьте <b>крупнее и чётче</b>: увеличьте таблицу на телефоне и сделайте скриншот или отправьте фото <b>файлом</b> (📎 → Файл).",
    },
    "schedule_text_incomplete": {
        "uz": "✍️ Bu to'liq jadval emas. Kamida <b>3 ta dars</b> yozing (har qatorda kun, vaqt va fan) yoki jadval <b>rasmini</b> yuboring."+NL+NL+"<code>Dushanba 08:00-09:30 Matematika A-327</code>"+NL+"<code>Dushanba 09:30-11:00 Fizika A-210</code>"+NL+"<code>Seshanba 08:00-09:30 Ingliz tili B-105</code>",
        "ru": "✍️ Это не полное расписание. Напишите минимум <b>3 занятия</b> (в каждой строке день, время и предмет) или отправьте <b>фото</b> расписания."+NL+NL+"<code>Понедельник 08:00-09:30 Математика A-327</code>"+NL+"<code>Понедельник 09:30-11:00 Физика A-210</code>"+NL+"<code>Вторник 08:00-09:30 Английский B-105</code>",
    },
    "schedule_lookalike": {
        "uz": "⚠️ Bu jadval <b>{group}</b> guruhining jadvaliga aynan o'xshaydi. Guruhingiz to'g'riligini admin tekshiradi.",
        "ru": "⚠️ Это расписание полностью совпадает с расписанием группы <b>{group}</b>. Админ проверит, что оно ваше.",
    },
    "group_mismatch": {
        "uz": "⚠️ Rasmda boshqa guruh ko'rinyapti: <b>{seen}</b>. Jadval admin tekshiruvidan keyin saqlanadi.",
        "ru": "⚠️ На фото другая группа: <b>{seen}</b>. Расписание сохранится после проверки админом.",
    },
    "schedule_change_prompt": {
        "uz": "🔄 <b>Jadval o'zgardimi?</b>"+NL+"Yangi jadval rasmini yoki matnini yuboring.",
        "ru": "🔄 <b>Расписание изменилось?</b>"+NL+"Отправьте фото или текст нового расписания.",
    },
    "file_too_big": {"uz": "❗ Fayl juda katta (15 MB dan kichik bo'lsin).", "ru": "❗ Файл слишком большой (до 15 МБ)."},
    # O'qituvchilar
    "choose_role": {
        "uz": "Tanlang:",
        "ru": "Выберите:",
    },
    "btn_role_student": {"uz": "Talaba", "ru": "Студент"},
    "btn_role_teacher": {"uz": "O'qituvchi", "ru": "Преподаватель"},
    "teacher_ask_university": {
        "uz": "👨‍🏫 <b>O'qituvchi sifatida ro'yxatdan o'tish</b>\n\n🏛 Universitetingiz nomini yozing.\nMasalan: TATU",
        "ru": "👨‍🏫 <b>Регистрация преподавателя</b>\n\n🏛 Напишите название университета.\nНапример: ТУИТ",
    },
    "teacher_ask_name": {
        "uz": "👤 To'liq ismingizni yozing (F.I.Sh.).\nMasalan: Karimov Anvar Rustamovich",
        "ru": "👤 Напишите ваше полное имя (Ф.И.О.).\nНапример: Каримов Анвар Рустамович",
    },
    "teacher_ask_department": {
        "uz": "🎓 Kafedra yoki fakultetingizni yozing.\nMasalan: Kiberxavfsizlik",
        "ru": "🎓 Напишите кафедру или факультет.\nНапример: Кибербезопасность",
    },
    "teacher_bad_name": {"uz": "❗ To'liq ismingizni yozing (kamida 2 so'z).", "ru": "❗ Напишите полное имя (минимум 2 слова)."},
    "teacher_pending": {
        "uz": "⏳ <b>So'rovingiz adminga yuborildi.</b>\n\nTasdiqlangach shu yerga xabar keladi, keyin dars jadvalingizni yuborasiz.",
        "ru": "⏳ <b>Заявка отправлена администратору.</b>\n\nПосле подтверждения придёт сообщение, затем отправите своё расписание.",
    },
    "teacher_still_pending": {
        "uz": "⏳ So'rovingiz hali ko'rib chiqilmoqda. Tasdiqlangach xabar beramiz.",
        "ru": "⏳ Заявка ещё на рассмотрении. Сообщим после подтверждения.",
    },
    "teacher_request_admin": {
        "uz": "👨‍🏫 <b>Yangi o'qituvchi so'rovi</b>\n\n👤 {name}\n🏛 {university}\n🎓 {department}\n📱 Telegram: {who}",
        "ru": "👨‍🏫 <b>Новая заявка преподавателя</b>\n\n👤 {name}\n🏛 {university}\n🎓 {department}\n📱 Telegram: {who}",
    },
    "btn_teachers": {"uz": "👨‍🏫 O'qituvchilar", "ru": "👨‍🏫 Преподаватели"},
    "teachers_admin_title": {
        "uz": "👨‍🏫 <b>O'qituvchilar</b>"+NL+NL+"✅ Tasdiqlangan: <b>{approved}</b>"+NL+"⏳ Tasdiq kutmoqda: <b>{pending}</b>"+NL+"❌ Rad etilgan: <b>{rejected}</b>",
        "ru": "👨‍🏫 <b>Преподаватели</b>"+NL+NL+"✅ Подтверждены: <b>{approved}</b>"+NL+"⏳ Ждут подтверждения: <b>{pending}</b>"+NL+"❌ Отклонены: <b>{rejected}</b>",
    },
    "teacher_card": {
        "uz": "{icon} <b>{name}</b>"+NL+"🎓 {department}"+NL+"📱 {who}",
        "ru": "{icon} <b>{name}</b>"+NL+"🎓 {department}"+NL+"📱 {who}",
    },
    "teachers_pending_title": {"uz": "⏳ <b>Tasdiq kutayotganlar:</b>", "ru": "⏳ <b>Ждут подтверждения:</b>"},
    "teachers_approved_title": {"uz": "✅ <b>Tasdiqlangan o'qituvchilar:</b>", "ru": "✅ <b>Подтверждённые преподаватели:</b>"},
    "btn_teacher_ok": {"uz": "✅ Tasdiqlash", "ru": "✅ Подтвердить"},
    "btn_teacher_no": {"uz": "❌ Rad etish", "ru": "❌ Отклонить"},
    "admin_teacher_approved": {"uz": "✅ O'qituvchi tasdiqlandi: {name}", "ru": "✅ Преподаватель подтверждён: {name}"},
    "admin_teacher_rejected": {"uz": "❌ O'qituvchi so'rovi rad etildi: {name}", "ru": "❌ Заявка отклонена: {name}"},
    "teacher_approved": {
        "uz": "✅ <b>Siz o'qituvchi sifatida tasdiqlandingiz!</b>",
        "ru": "✅ <b>Вы подтверждены как преподаватель!</b>",
    },
    "teacher_rejected": {
        "uz": "❌ O'qituvchi so'rovingiz rad etildi. Savol bo'lsa: ✉️ Murojaat. Talaba sifatida davom etish uchun /start bosing.",
        "ru": "❌ Заявка преподавателя отклонена. Вопросы: ✉️ Обращение. Чтобы продолжить как студент, нажмите /start.",
    },
    "teacher_send_schedule": {
        "uz": "📸 Dars jadvalingiz <b>rasmini</b> (yoki faylini) yuboring yoki ✍️ <b>yozib</b> yuboring. "
              "Har bir darsda guruhni ham yozing, masalan:\n\n"
              "<code>Dushanba 08:00-09:30 Matematika 712-24 A-327\nDushanba 09:30-11:00 Fizika 732-24 B-210</code>",
        "ru": "📸 Отправьте <b>фото</b> (или файл) своего расписания или ✍️ <b>напишите</b> его текстом. "
              "У каждого занятия укажите группу, например:\n\n"
              "<code>Понедельник 08:00-09:30 Математика 712-24 A-327\nПонедельник 09:30-11:00 Физика 732-24 B-210</code>",
    },
    "teacher_saved": {
        "uz": "✅ <b>Jadvalingiz saqlandi</b>\n\n📚 {lessons} · 👥 {groups} ta guruh\n⏰ Eslatma darsdan {time} oldin keladi.",
        "ru": "✅ <b>Расписание сохранено</b>\n\n📚 {lessons} · 👥 групп: {groups}\n⏰ Напоминание придёт за {time} до занятия.",
    },
    "teacher_no_schedule": {
        "uz": "📭 Jadvalingiz hali yo'q.",
        "ru": "📭 Вашего расписания пока нет.",
    },
    "teacher_week_title": {"uz": "👨‍🏫 <b>Mening dars jadvalim</b>", "ru": "👨‍🏫 <b>Моё расписание</b>"},
    "teacher_week_summary": {"uz": "📚 {lessons} · 👥 {groups} ta guruh", "ru": "📚 {lessons} · 👥 групп: {groups}"},
    "teacher_profile": {
        "uz": "👨‍🏫 <b>{name}</b>\n\n🏛 Universitet: {university}\n🎓 Kafedra: {department}\n📚 {lessons} · 👥 {groups} ta guruh\n⏰ Eslatma: darsdan {time} oldin",
        "ru": "👨‍🏫 <b>{name}</b>\n\n🏛 Университет: {university}\n🎓 Кафедра: {department}\n📚 {lessons} · 👥 групп: {groups}\n⏰ Напоминание: за {time} до занятия",
    },
    "issue_group": {"uz": "guruh ko'rsatilmagan", "ru": "группа не указана"},
    "fallback_hint": {"uz": "🤔 Tushunmadim. Kerakli bo'limni pastdagi menyudan tanlang 👇", "ru": "🤔 Не понял. Выберите раздел в меню ниже 👇"},
    "start_your_data": {"uz": "📋 <b>Ma'lumotlaringiz saqlangan:</b>", "ru": "📋 <b>Ваши данные сохранены:</b>"},
    "profile_university": {"uz": "🏛 Universitet: {name}", "ru": "🏛 Университет: {name}"},
    "profile_faculty": {"uz": "🎓 Fakultet: {name}", "ru": "🎓 Факультет: {name}"},
    "profile_lang": {"uz": "🌐 Til: O'zbekcha", "ru": "🌐 Язык: Русский"},
    # Kirish va til
    "choose_language": {"uz": "🌐 Tilni tanlang\nВыберите язык", "ru": "🌐 Tilni tanlang\nВыберите язык"},
    "language_saved": {"uz": "✅ Til: O'zbekcha", "ru": "✅ Язык: Русский"},
    "welcome_student": {
        "uz": "👋 <b>Salom, {name}!</b>\n\nMen dars jadvalingizni saqlayman va har bir darsdan oldin eslatib turaman.",
        "ru": "👋 <b>Привет, {name}!</b>\n\nЯ сохраню ваше расписание и буду напоминать о каждом занятии.",
    },
    "welcome_admin": {
        "uz": "👋 <b>Salom, {name}!</b>\n\nSiz administratorsiz. Kerakli bo'limni tanlang.",
        "ru": "👋 <b>Привет, {name}!</b>\n\nВы администратор. Выберите нужный раздел.",
    },
    # Ro'yxatdan o'tish
    "ask_university": {
        "uz": "🏛 <b>Universitetingiz nomini yozing</b>\n\nMasalan: TATU",
        "ru": "🏛 <b>Напишите название университета</b>\n\nНапример: ТУИТ",
    },
    "ask_faculty": {
        "uz": "🎓 <b>Fakultetingiz nomini yozing</b>\n\nMasalan: Kiberxavfsizlik",
        "ru": "🎓 <b>Напишите название факультета</b>\n\nНапример: Кибербезопасность",
    },
    "ask_group": {
        "uz": "👥 <b>Guruhingizni yozing</b>\n\nMasalan: 712-24",
        "ru": "👥 <b>Напишите вашу группу</b>\n\nНапример: 712-24",
    },
    "bad_university": {"uz": "❗ Iltimos, to'g'ri ma'lumot kiriting.\nUniversitetingizning haqiqiy nomini yozing. Masalan: TATU yoki Toshkent axborot texnologiyalari universiteti", "ru": '❗ Пожалуйста, введите верные данные.\nНапишите настоящее название университета. Например: ТУИТ или Ташкентский университет информационных технологий'},
    "bad_faculty": {"uz": "❗ Iltimos, to'g'ri ma'lumot kiriting.\nFakultetingizning haqiqiy nomini yozing. Masalan: Kiberxavfsizlik", "ru": '❗ Пожалуйста, введите верные данные.\nНапишите настоящее название факультета. Например: Кибербезопасность'},
    "bad_group": {"uz": "❗ Iltimos, to'g'ri ma'lumot kiriting.\nGuruh raqamini yozing. Masalan: 712-24", "ru": '❗ Пожалуйста, введите верные данные.\nНапишите номер группы. Например: 712-24'},
    "registered": {"uz": "✅ <b>Tayyor!</b>", "ru": "✅ <b>Готово!</b>"},
    "group_ready": {
        "uz": "Guruhingiz jadvali tayyor, rasm yuborish shart emas. Eslatmalar yoqildi.",
        "ru": "Расписание вашей группы уже есть, фото отправлять не нужно. Напоминания включены.",
    },
    "send_photo_now": {
        "uz": "Guruhingiz jadvali hali bazada yo'q.\n\n📸 Dars jadvali <b>rasmini</b> yuboring\n"
              "yoki ✍️ jadvalni <b>yozib</b> yuboring, masalan:\n\n"
              "<code>Dushanba 08:00-09:30 Matematika A-327\nDushanba 09:30-11:00 Fizika A-210</code>",
        "ru": "Расписания вашей группы пока нет в базе.\n\n📸 Отправьте <b>фото</b> расписания\n"
              "или ✍️ <b>напишите</b> его текстом, например:\n\n"
              "<code>Понедельник 08:00-09:30 Математика A-327\nПонедельник 09:30-11:00 Физика A-210</code>",
    },
    # Jadval
    "week_today": {"uz": "📅 Bugun: {date}", "ru": "📅 Сегодня: {date}"},
    "today_title": {"uz": "Bugun, {day}", "ru": "Сегодня, {day}"},
    "tomorrow_title": {"uz": "Ertaga, {day}", "ru": "Завтра, {day}"},
    "day_empty": {"uz": "Dars yo'q 🎉", "ru": "Занятий нет 🎉"},
    "week_title": {"uz": "🗓 <b>Haftalik jadval</b>", "ru": "🗓 <b>Расписание на неделю</b>"},
    "week_now": {"uz": "Hozir: {parity}", "ru": "Сейчас: {parity}"},
    "no_schedule": {
        "uz": "🗓 Jadvalingiz hali yo'q.\n\nJadval rasmini shu yerga yuboring.",
        "ru": "🗓 Расписания пока нет.\n\nОтправьте фото расписания сюда.",
    },
    "send_prompt": {"uz": "📸 Jadval rasmini shu yerga yuboring.", "ru": "📸 Отправьте фото расписания сюда."},
    # Rasm yuborish
    "reading": {
        "uz": "⏳ Jadval o'qilmoqda, bir necha soniya kuting...",
        "ru": "⏳ Распознаю расписание, подождите несколько секунд...",
    },
    "read_failed": {
        "uz": "⚠️ <b>Jadvalni o'qib bo'lmadi</b>\n\nHech narsa saqlanmadi. Aniqroq rasm yuboring yoki jadvalni yozib yuboring (kun, vaqt, fan).",
        "ru": "⚠️ <b>Не удалось распознать расписание</b>\n\nНичего не сохранено. Отправьте более чёткое фото или напишите расписание текстом (день, время, предмет).",
    },
    "sent_to_review": {
        "uz": "🔍 <b>Admin tekshiruviga yuborildi</b>\n\n{summary}\n\nGuruhingiz jadvali allaqachon bor. Admin tasdiqlasa, yangisi bilan almashtiriladi.",
        "ru": "🔍 <b>Отправлено на проверку админу</b>\n\n{summary}\n\nУ вашей группы уже есть расписание. После подтверждения оно будет заменено.",
    },
    "saved": {
        "uz": "✅ <b>Jadval saqlandi</b>\n\n{summary}\n\n{subjects}\n\n⏰ Eslatma har darsdan {time} oldin keladi.",
        "ru": "✅ <b>Расписание сохранено</b>\n\n{summary}\n\n{subjects}\n\n⏰ Напоминание придёт за {time} до каждого занятия.",
    },
    "upload_error": {
        "uz": "⚠️ <b>Xatolik yuz berdi</b>\n\nJadval saqlanmadi. Birozdan so'ng qayta yuboring.",
        "ru": "⚠️ <b>Произошла ошибка</b>\n\nРасписание не сохранено. Попробуйте позже.",
    },
    "status_empty": {"uz": "📊 Siz hali jadval yubormagansiz.", "ru": "📊 Вы ещё не отправляли расписание."},
    "status_title": {"uz": "📊 <b>Oxirgi yuborgan jadvallaringiz</b>\n", "ru": "📊 <b>Ваши последние расписания</b>\n"},
    # Eslatma
    "reminder_prompt": {
        "uz": "⏰ <b>Eslatma vaqti</b>\n\nHozir: darsdan {time} oldin.\n\nYangi vaqtni tanlang yoki daqiqada yozing (1–180):",
        "ru": "⏰ <b>Время напоминания</b>\n\nСейчас: за {time} до занятия.\n\nВыберите новое время или напишите в минутах (1–180):",
    },
    "btn_remind_off": {"uz": "🔕 Eslatmani o'chirish", "ru": "🔕 Выключить напоминания"},
    "btn_remind_on": {"uz": "🔔 Eslatmani yoqish", "ru": "🔔 Включить напоминания"},
    "reminder_turned_off": {
        "uz": "🔕 <b>Eslatmalar o'chirildi.</b> Qayta yoqish: ⏰ Eslatma.",
        "ru": "🔕 <b>Напоминания выключены.</b> Включить снова: ⏰ Напоминание.",
    },
    "reminder_prompt_off": {
        "uz": "⏰ <b>Eslatma</b>"+NL+NL+"Hozir: 🔕 o'chirilgan."+NL+NL+"Yoqish uchun vaqtni tanlang:",
        "ru": "⏰ <b>Напоминание</b>"+NL+NL+"Сейчас: 🔕 выключено."+NL+NL+"Чтобы включить, выберите время:",
    },
    "profile_reminder_off": {"uz": "⏰ Eslatma: o'chirilgan", "ru": "⏰ Напоминание: выключено"},
    "reminder_saved": {
        "uz": "✅ Eslatma endi darsdan <b>{time}</b> oldin keladi.",
        "ru": "✅ Теперь напоминание придёт за <b>{time}</b> до занятия.",
    },
    "reminder_bad": {"uz": "❗ 1 dan 180 gacha son yozing. Masalan: 30", "ru": "❗ Напишите число от 1 до 180. Например: 30"},
    "reminder_in": {"uz": "⏰ <b>Darsga {time} qoldi</b>", "ru": "⏰ <b>Занятие через {time}</b>"},
    "reminder_now": {"uz": "⏰ <b>Dars hozir boshlanadi</b>", "ru": "⏰ <b>Занятие начинается</b>"},
    # Profil
    "profile_group": {"uz": "👥 Guruh: {group}", "ru": "👥 Группа: {group}"},
    "profile_no_group": {"uz": "👥 Guruh tanlanmagan", "ru": "👥 Группа не выбрана"},
    "profile_no_schedule": {"uz": "📚 Jadval hali yo'q", "ru": "📚 Расписания пока нет"},
    "profile_reminder": {"uz": "⏰ Eslatma: darsdan {time} oldin", "ru": "⏰ Напоминание: за {time} до занятия"},
    "profile_change": {"uz": "", "ru": ""},
    # Admin
    "admin_only": {
        "uz": "⚠️ Bu bo'lim faqat tizim administratorlari uchun.",
        "ru": "⚠️ Этот раздел только для администраторов.",
    },
    "admin_student_menu": {"uz": "🎓 Talaba menyusi ochildi.", "ru": "🎓 Открыто меню студента."},
    "admin_menu_opened": {"uz": "🛠 Admin menyusi ochildi.", "ru": "🛠 Открыто меню администратора."},
    "stats": {
        "uz": (
            "📈 <b>Statistika</b>\n\n"
            "🏛 Universitetlar: <b>{universities}</b> ta\n"
            "🎓 Fakultetlar: <b>{faculties}</b> ta\n"
            "👨‍🏫 O'qituvchilar: <b>{teachers}</b> ta\n"
            "👥 Guruhlar: <b>{groups}</b> ta\n"
            "📚 Fanlar: <b>{subjects}</b> ta <i>(har bir fan bir marta sanalgan)</i>"
        ),
        "ru": (
            "📈 <b>Статистика</b>\n\n"
            "🏛 Университеты: <b>{universities}</b>\n"
            "🎓 Факультеты: <b>{faculties}</b>\n"
            "👨‍🏫 Преподаватели: <b>{teachers}</b>\n"
            "👥 Группы: <b>{groups}</b>\n"
            "📚 Предметы: <b>{subjects}</b> <i>(каждый предмет учтён один раз)</i>"
        ),
    },
    "live_at": {"uz": "🕒 Hozirgi holat: {time}", "ru": "🕒 Актуально на: {time}"},
    "btn_refresh": {"uz": "🔄 Yangilash", "ru": "🔄 Обновить"},
    "users_pending": {"uz": "⏳ Tasdiq kutayotgan o'qituvchilar: <b>{n}</b> ta", "ru": "⏳ Преподаватели ждут подтверждения: <b>{n}</b>"},
    "users_unregistered": {"uz": "🚪 Ro'yxatdan o'tishni tugatmagan: <b>{n}</b> ta", "ru": "🚪 Не завершили регистрацию: <b>{n}</b>"},
    "users_stats": {
        "uz": "👤 <b>Foydalanuvchilar</b>"+NL+NL+"👥 Jami: <b>{total}</b> ta"+NL+"👨‍🏫 O'qituvchilar: <b>{teachers}</b> ta"+NL+"🎓 Talabalar: <b>{students}</b> ta",
        "ru": "👤 <b>Пользователи</b>"+NL+NL+"👥 Всего: <b>{total}</b>"+NL+"👨‍🏫 Преподаватели: <b>{teachers}</b>"+NL+"🎓 Студенты: <b>{students}</b>",
    },
    "new_schedule": {"uz": "📸 <b>Yangi jadval #{id}</b>", "ru": "📸 <b>Новое расписание #{id}</b>"},
    "admin_saved": {"uz": "✅ Saqlandi", "ru": "✅ Сохранено"},
    "admin_read_failed": {"uz": "⚠️ AI o'qiy olmadi", "ru": "⚠️ ИИ не смог распознать"},
    "review_title": {"uz": "📥 <b>Jadval #{id}</b> (navbatda: {left} ta)\n", "ru": "📥 <b>Расписание #{id}</b> (в очереди: {left})\n"},
    "review_empty": {"uz": "✅ Tekshiruv kutayotgan jadval yo'q.", "ru": "✅ Нет расписаний на проверке."},
    "no_permission": {"uz": "Ruxsat berilmagan!", "ru": "Нет доступа!"},
    "review_missing": {"uz": "Jadval topilmadi", "ru": "Расписание не найдено"},
    "review_done_before": {"uz": "Bu jadval allaqachon ko'rib chiqilgan", "ru": "Это расписание уже рассмотрено"},
    "review_approved": {"uz": "✅ <b>Jadval #{id} tasdiqlandi</b>", "ru": "✅ <b>Расписание #{id} подтверждено</b>"},
    "review_rejected": {"uz": "❌ <b>Jadval #{id} rad etildi</b>", "ru": "❌ <b>Расписание #{id} отклонено</b>"},
    "student_approved": {
        "uz": "✅ <b>Jadvalingiz tasdiqlandi</b>\n\nGuruh jadvali yangilandi.",
        "ru": "✅ <b>Ваше расписание подтверждено</b>\n\nРасписание группы обновлено.",
    },
    "group_schedule_updated": {
        "uz": "📅 <b>{group}</b> guruhining dars jadvali yangilandi (admin tasdiqladi)."+NL+"Ko'rish: 📅 Dars jadvali",
        "ru": "📅 Расписание группы <b>{group}</b> обновлено (подтверждено админом)."+NL+"Смотреть: 📅 Расписание",
    },
    "student_rejected": {
        "uz": "❌ <b>Jadvalingiz rad etildi</b>\n\nAniqroq rasm yuborib ko'ring.",
        "ru": "❌ <b>Ваше расписание отклонено</b>\n\nПопробуйте отправить более чёткое фото.",
    },
    "groups_empty": {"uz": "👥 Hali guruh yo'q.", "ru": "👥 Групп пока нет."},
    "groups_summary": {
        "uz": "🎓 Fakultetlar: {faculties} · 👥 Guruhlar: {groups} · 📅 Jadvali bor: {with_schedule}",
        "ru": "🎓 Факультетов: {faculties} · 👥 Групп: {groups} · 📅 С расписанием: {with_schedule}",
    },
    "groups_legend": {
        "uz": "✅ jadval bor · ⚪️ jadval yo'q · 👤 talabalar · 📚 darslar"+NL+"⚠️ — jadvali shu guruhnikiga deyarli bir xil (adashgan bo'lishi mumkin)",
        "ru": "✅ есть расписание · ⚪️ нет · 👤 студенты · 📚 занятия"+NL+"⚠️ — расписание почти совпадает с указанной группой (возможна ошибка)",
    },
    "groups_title": {"uz": "👥 <b>Guruhlar</b>\n", "ru": "👥 <b>Группы</b>\n"},
    "group_counts": {"uz": "{students} talaba · {lessons} dars", "ru": "студентов: {students} · занятий: {lessons}"},
    "users_title": {"uz": "👤 <b>Foydalanuvchilar</b>: {total} ta\n", "ru": "👤 <b>Пользователи</b>: {total}\n"},
    "no_group": {"uz": "guruhsiz", "ru": "без группы"},
    "announce_need_university": {
        "uz": "❗ Avval /register orqali universitetingizni tanlang.",
        "ru": "❗ Сначала выберите университет через /register.",
    },
    "announce_prompt": {
        "uz": "📢 E'lon matnini yozing. U universitetingiz talabalariga yuboriladi.",
        "ru": "📢 Напишите текст объявления. Его получат студенты вашего университета.",
    },
    "announce_choose": {"uz": "📢 <b>E'lon kimga?</b>", "ru": "📢 <b>Кому объявление?</b>"},
    "announce_to_all": {"uz": "🌐 Hammaga", "ru": "🌐 Всем"},
    "announce_to_group": {"uz": "🎯 Faqat <b>{group}</b> guruhiga", "ru": "🎯 Только группе <b>{group}</b>"},
    "announce_prompt_to": {
        "uz": "📢 {audience} — <b>{count}</b> kishi."+NL+"E'lon matnini yozing:",
        "ru": "📢 {audience} — <b>{count}</b> чел."+NL+"Напишите текст объявления:",
    },
    "announce_fail_blocked": {"uz": "🚫 Botni bloklaganlar ({n}): {names}", "ru": "🚫 Заблокировали бота ({n}): {names}"},
    "announce_fail_not_started": {"uz": "❓ Botni ishga tushirmaganlar ({n}): {names}", "ru": "❓ Не запускали бота ({n}): {names}"},
    "announce_fail_other": {"uz": "⚠️ Boshqa xato ({n}): {names}", "ru": "⚠️ Другая ошибка ({n}): {names}"},
    "announce_fail_note": {
        "uz": "ℹ️ Telegram qoidasi: botni bloklagan yoki /start bosmagan odamga bot yoza olmaydi. Qolganlariga xabar yetkazildi.",
        "ru": "ℹ️ Правило Telegram: бот не может писать тем, кто заблокировал его или не нажал /start. Остальным доставлено.",
    },
    "block_usage": {
        "uz": "Foydalanish: <code>/block @username</code> yoki <code>/block ID</code> (qaytarish: /unblock)",
        "ru": "Использование: <code>/block @username</code> или <code>/block ID</code> (вернуть: /unblock)",
    },
    "block_done": {"uz": "🚫 {who} bloklandi. Qaytarish: /unblock", "ru": "🚫 {who} заблокирован. Вернуть: /unblock"},
    "unblock_done": {"uz": "✅ {who} blokdan chiqarildi.", "ru": "✅ {who} разблокирован."},
    "block_admin_refused": {"uz": "Adminni bloklab bo'lmaydi.", "ru": "Администратора заблокировать нельзя."},
    "btn_block": {"uz": "🚫 Bloklash", "ru": "🚫 Заблокировать"},
    "announce_cancelled": {"uz": "❌ E'lon bekor qilindi.", "ru": "❌ Объявление отменено."},
    "announce_missing": {"uz": "E'lon topilmadi, qaytadan yozing", "ru": "Объявление не найдено, напишите заново"},
    "announce_sending": {"uz": "⏳ E'lon yuborilmoqda...", "ru": "⏳ Отправляю объявление..."},
    "announce_done": {
        "uz": "✅ E'lon yuborildi: {sent} ta. Yetib bormadi: {failed} ta.",
        "ru": "✅ Объявление отправлено: {sent}. Не доставлено: {failed}.",
    },
    "announce_preview": {
        "uz": "📢 <b>Tekshiring</b>\n\n{text}\n\n<i>{count} ta talabaga yuboriladi.</i>",
        "ru": "📢 <b>Проверьте</b>\n\n{text}\n\n<i>Получателей: {count}.</i>",
    },
    "announce_header": {"uz": "📢 <b>E'lon</b>\n\n{text}", "ru": "📢 <b>Объявление</b>\n\n{text}"},
}


def _attach_english() -> None:
    from app.bot.i18n_en import EN

    for key, values in TEXTS.items():
        values["en"] = EN.get(key) or values["uz"]
    TEXTS["choose_language"]["en"] = TEXTS["choose_language"]["uz"]


_attach_english()


def lang_of(user: Any) -> str:
    """Foydalanuvchi tili; tanlanmagan yoki noma'lum bo'lsa o'zbekcha"""
    code = (getattr(user, "language_code", None) or "").lower()
    if code.startswith("ru"):
        return "ru"
    if code.startswith("en"):
        return "en"
    return DEFAULT_LANG


def t(lang: str, key: str, **kwargs: Any) -> str:
    text = TEXTS[key][lang if lang in LANGUAGES else DEFAULT_LANG]
    return text.format(**kwargs) if kwargs else text


def labels(key: str) -> Set[str]:
    """Tugma ikkala tilda ham bir handlerga tushishi uchun barcha yozuvlari"""
    return set(TEXTS[key].values()) | LEGACY_LABELS.get(key, set())


# Eski menyu yozuvlari: foydalanuvchida eski klaviatura qolgan bo'lsa ham tugma ishlashi uchun
LEGACY_LABELS: Dict[str, Set[str]] = {
    "btn_today": {"📖 Bugungi darslar", "📖 Занятия сегодня"},
    "btn_tomorrow": {"📆 Ertangi darslar", "📆 Занятия завтра"},
    "btn_week": {"🗓 Umumiy jadval", "🗓 Всё расписание"},
    "btn_reminder": {"⏰ Eslatma sozlamalari", "⏰ Напоминания"},
    "btn_profile": {"👤 Profilim"},
    "btn_new_shots": {"📥 Yangi screenshotlar", "📥 Новые расписания"},
    "btn_student_view": {"🎓 Talaba ko'rinishiga o'tish", "🎓 Меню студента"},
}


def _ru_plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def format_minutes(minutes: int, lang: str = DEFAULT_LANG) -> str:
    """Daqiqani tushunarli shaklga o'tkazadi: 30 -> '30 daqiqa (yarim soat)'"""
    hours, rest = divmod(minutes, 60)
    if lang == "en":
        base = f"{minutes} minute" + ("" if minutes == 1 else "s")
        if minutes == 30:
            return f"{base} (half an hour)"
        if minutes > 0 and rest == 0:
            return f"{base} ({hours} h)"
        if minutes > 60:
            return f"{base} ({hours} h {rest} min)"
        return base
    if lang == "ru":
        base = f"{minutes} {_ru_plural(minutes, 'минуту', 'минуты', 'минут')}"
        if minutes == 30:
            return f"{base} (полчаса)"
        if minutes > 0 and rest == 0:
            return f"{base} ({hours} ч)"
        if minutes > 60:
            return f"{base} ({hours} ч {rest} мин)"
        return base

    base = f"{minutes} daqiqa"
    if minutes == 30:
        return f"{base} (yarim soat)"
    if minutes > 0 and rest == 0:
        return f"{base} ({hours} soat)"
    if minutes > 60:
        return f"{base} ({hours} soat {rest} daqiqa)"
    return base


def format_counts(subjects: int, lessons: int, lang: str = DEFAULT_LANG) -> str:
    if lang == "en":
        return f"{subjects} subject{'' if subjects == 1 else 's'} · {lessons} lesson{'' if lessons == 1 else 's'}"
    if lang == "ru":
        subject_word = _ru_plural(subjects, "предмет", "предмета", "предметов")
        lesson_word = _ru_plural(lessons, "занятие", "занятия", "занятий")
        return f"{subjects} {subject_word} · {lessons} {lesson_word}"
    return f"{subjects} ta fan · {lessons} ta dars"


def format_lesson_count(lessons: int, lang: str = DEFAULT_LANG) -> str:
    if lang == "en":
        return f"{lessons} lesson{'' if lessons == 1 else 's'}"
    if lang == "ru":
        return f"{lessons} {_ru_plural(lessons, 'занятие', 'занятия', 'занятий')}"
    return f"{lessons} ta dars"
