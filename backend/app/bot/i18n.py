from typing import Any, Dict, Set
from app.models.enums import DayOfWeek, SubmissionStatus, WeekParity

DEFAULT_LANG = "uz"
LANGUAGES = ("uz", "ru")

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
    "btn_new_shots": {"uz": "📥 Yangi screenshotlar", "ru": "📥 Новые расписания"},
    "btn_stats": {"uz": "📈 Statistika", "ru": "📈 Статистика"},
    "btn_groups": {"uz": "👥 Guruhlar", "ru": "👥 Группы"},
    "btn_users": {"uz": "👤 Foydalanuvchilar", "ru": "👤 Пользователи"},
    "btn_announce": {"uz": "📢 E'lon yuborish", "ru": "📢 Отправить объявление"},
    "btn_student_view": {"uz": "🎓 Talaba ko'rinishiga o'tish", "ru": "🎓 Меню студента"},
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
    "schedule_change_prompt": {
        "uz": "🔄 <b>Jadval o'zgardimi?</b>\n\nYangi jadvalning <b>rasmini</b> (yoki faylini) yuboring, "
              "yoki o'zgarishni <b>yozib</b> yuboring. Butun haftani yozing, masalan:\n\n"
              "<code>Dushanba 08:00-09:30 Matematika A-327</code>\n\n"
              "AI o'qib chiqadi, admin tasdiqlagach guruhingiz jadvali yangilanadi.",
        "ru": "🔄 <b>Расписание изменилось?</b>\n\nОтправьте <b>фото</b> (или файл) нового расписания "
              "или <b>напишите</b> его текстом за всю неделю, например:\n\n"
              "<code>Понедельник 08:00-09:30 Математика A-327</code>\n\n"
              "AI распознает его, и после подтверждения админом расписание группы обновится.",
    },
    "file_too_big": {"uz": "❗ Fayl juda katta (15 MB dan kichik bo'lsin).", "ru": "❗ Файл слишком большой (до 15 МБ)."},
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
    "bad_university": {"uz": "❗ Universitet nomini yozing.", "ru": "❗ Напишите название университета."},
    "bad_faculty": {"uz": "❗ Fakultet nomini yozing.", "ru": "❗ Напишите название факультета."},
    "bad_group": {"uz": "❗ Guruh nomini yozing.", "ru": "❗ Напишите название группы."},
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
            "👤 Talabalar: {users} ta ({linked} tasi guruhga ulangan)\n"
            "👥 Guruhlar: {groups} ta ({with_schedule} tasida jadval bor)\n"
            "📚 Faol darslar: {lessons} ta\n"
            "📥 Tekshiruv kutmoqda: {pending} ta\n"
            "⏰ Bugungi eslatmalar: {sent} ta yuborildi, {failed} ta xato"
        ),
        "ru": (
            "📈 <b>Статистика</b>\n\n"
            "👤 Студенты: {users} (в группах: {linked})\n"
            "👥 Группы: {groups} (с расписанием: {with_schedule})\n"
            "📚 Активные занятия: {lessons}\n"
            "📥 Ждут проверки: {pending}\n"
            "⏰ Напоминания сегодня: отправлено {sent}, ошибок {failed}"
        ),
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
    "student_rejected": {
        "uz": "❌ <b>Jadvalingiz rad etildi</b>\n\nAniqroq rasm yuborib ko'ring.",
        "ru": "❌ <b>Ваше расписание отклонено</b>\n\nПопробуйте отправить более чёткое фото.",
    },
    "groups_empty": {"uz": "👥 Hali guruh yo'q.", "ru": "👥 Групп пока нет."},
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


def lang_of(user: Any) -> str:
    """Foydalanuvchi tili; tanlanmagan yoki noma'lum bo'lsa o'zbekcha"""
    code = (getattr(user, "language_code", None) or "").lower()
    return "ru" if code.startswith("ru") else DEFAULT_LANG


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
    if lang == "ru":
        subject_word = _ru_plural(subjects, "предмет", "предмета", "предметов")
        lesson_word = _ru_plural(lessons, "занятие", "занятия", "занятий")
        return f"{subjects} {subject_word} · {lessons} {lesson_word}"
    return f"{subjects} ta fan · {lessons} ta dars"


def format_lesson_count(lessons: int, lang: str = DEFAULT_LANG) -> str:
    if lang == "ru":
        return f"{lessons} {_ru_plural(lessons, 'занятие', 'занятия', 'занятий')}"
    return f"{lessons} ta dars"
