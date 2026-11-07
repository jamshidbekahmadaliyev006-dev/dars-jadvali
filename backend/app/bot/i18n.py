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
    "btn_today": {"uz": "📖 Bugungi darslar", "ru": "📖 Занятия сегодня"},
    "btn_tomorrow": {"uz": "📆 Ertangi darslar", "ru": "📆 Занятия завтра"},
    "btn_week": {"uz": "🗓 Umumiy jadval", "ru": "🗓 Всё расписание"},
    "btn_reminder": {"uz": "⏰ Eslatma sozlamalari", "ru": "⏰ Напоминания"},
    "btn_send": {"uz": "📤 Jadval yuborish", "ru": "📤 Отправить расписание"},
    "btn_profile": {"uz": "👤 Profilim", "ru": "👤 Профиль"},
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
    "btn_10": {"uz": "10 daqiqa", "ru": "10 минут"},
    "btn_15": {"uz": "15 daqiqa", "ru": "15 минут"},
    "btn_30": {"uz": "Yarim soat", "ru": "Полчаса"},
    "btn_60": {"uz": "1 soat", "ru": "1 час"},
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
        "uz": "🏛 <b>Universitetingiz?</b>\n\nTanlang yoki nomini yozing:",
        "ru": "🏛 <b>Ваш университет?</b>\n\nВыберите или напишите название:",
    },
    "ask_faculty": {
        "uz": "🏢 <b>Fakultetingiz?</b>\n\nTanlang yoki nomini yozing:",
        "ru": "🏢 <b>Ваш факультет?</b>\n\nВыберите или напишите название:",
    },
    "ask_group": {
        "uz": "👥 <b>Guruhingiz?</b>\n\nTanlang yoki nomini yozing:",
        "ru": "👥 <b>Ваша группа?</b>\n\nВыберите или напишите название:",
    },
    "bad_university": {"uz": "❗ Universitet nomini yozing.", "ru": "❗ Напишите название университета."},
    "bad_faculty": {"uz": "❗ Fakultet nomini yozing.", "ru": "❗ Напишите название факультета."},
    "bad_group": {"uz": "❗ Guruh nomini yozing.", "ru": "❗ Напишите название группы."},
    "registered": {"uz": "✅ <b>Tayyor!</b>", "ru": "✅ <b>Готово!</b>"},
    "group_ready": {
        "uz": "Guruhingiz jadvali tayyor, rasm yuborish shart emas. Eslatmalar yoqildi.",
        "ru": "Расписание вашей группы уже есть, фото отправлять не нужно. Напоминания включены.",
    },
    "send_photo_now": {"uz": "📸 Endi dars jadvali rasmini yuboring.", "ru": "📸 Теперь отправьте фото расписания."},
    # Jadval
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
        "uz": "⚠️ <b>Jadvalni o'qib bo'lmadi</b>\n\nHech narsa saqlanmadi. Aniqroq rasm yuboring yoki birozdan so'ng qayta urinib ko'ring.",
        "ru": "⚠️ <b>Не удалось распознать расписание</b>\n\nНичего не сохранено. Отправьте более чёткое фото или попробуйте позже.",
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
    "profile_change": {"uz": "\nGuruhni o'zgartirish: /register", "ru": "\nСменить группу: /register"},
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
    return set(TEXTS[key].values())


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
