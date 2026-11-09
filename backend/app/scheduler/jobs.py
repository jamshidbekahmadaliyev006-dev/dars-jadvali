from datetime import datetime
import math
import pytz
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.bot.bot_instance import get_bot
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import logger
from app.models.enums import DayOfWeek, NotificationType, TeacherStatus, WeekParity
from app.models.teacher import TeacherLesson, TeacherProfile
from app.models.log import NotificationLog
from app.models.schedule import ReminderSetting, Schedule
from app.models.university import Group, Room
from app.models.user import User
from app.bot.i18n import lang_of
from app.bot.text_utils import format_reminder, format_teacher_reminder
from app.services.schedule_service import week_parity_for


# Eslatma sozlamasida ruxsat etilgan eng katta oldindan vaqt (daqiqa)
MAX_REMINDER_WINDOW_MINUTES = 180

# Telegram'ning qayta urinish befoyda bo'lgan javoblari
PERMANENT_SEND_ERRORS = (
    "forbidden",
    "chat not found",
    "user is deactivated",
    "bot was blocked",
    "bot can't initiate",
)


# Oldingi dars tugashi bilan keyingisi orasidagi oraliq shundan oshmasa - "ketma-ket dars" hisoblanadi
CONSECUTIVE_GAP_MINUTES = 30


def _to_minutes(value: str) -> int:
    hours, minutes = map(int, value.split(":")[:2])
    return hours * 60 + minutes


def _same_room_continuations(lessons) -> set:
    """
    lessons: (owner, start, end, room, id). Bir egasining (guruh / o'qituvchi) darsi uning oldingi
    darsidan keyin darhol (30 daqiqagacha tanaffus) va AYNAN SHU XONADA bo'lsa - eslatma yuborilmaydi:
    talaba/o'qituvchi allaqachon o'sha xonada o'tiribdi. Xona boshqa bo'lsa - eslatma odatdagidek ketadi.
    """
    skip = set()
    by_owner = {}
    for owner, start, end, room, lesson_id in lessons:
        try:
            by_owner.setdefault(owner, []).append((_to_minutes(start), _to_minutes(end), room, lesson_id))
        except Exception:
            continue
    for items in by_owner.values():
        items.sort()
        for prev, cur in zip(items, items[1:]):
            same_room = (
                prev[2] is not None and cur[2] is not None
                and str(prev[2]).strip().lower() == str(cur[2]).strip().lower()
            )
            consecutive = 0 <= cur[0] - prev[1] <= CONSECUTIVE_GAP_MINUTES
            if same_room and consecutive:
                skip.add(cur[3])
    return skip


async def check_and_send_lesson_reminders():
    """
    Har 60 soniyada ishga tushib, yaqinlashib kelayotgan darslar uchun talabalarga
    Telegram orqali avtomatik eslatma yuboruvchi scheduler vazifasi.
    """
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    weekday_idx = now.weekday()
    day_names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    today_enum = DayOfWeek[day_names[weekday_idx]]

    try:
        async with AsyncSessionLocal() as session:
            # Bugungi faol darslarni olish
            stmt = (
                select(Schedule)
                .options(
                    selectinload(Schedule.subject),
                    selectinload(Schedule.teacher),
                    selectinload(Schedule.group).selectinload(Group.university),
                    selectinload(Schedule.room).selectinload(Room.building),
                )
                .where(
                    Schedule.day_of_week == today_enum,
                    Schedule.is_active == True,
                    Schedule.week_parity.in_([WeekParity.ALL, week_parity_for(now.date())]),
                )
            )
            res = await session.execute(stmt)
            schedules = res.scalars().all()
            await _process_schedules(session, schedules, now)
            await _process_teacher_lessons(session, today_enum, now)
    except Exception as e:
        # Vazifa ichidagi kutilmagan xatolik (masalan, DB vaqtincha mavjud emas) butun
        # schedulerni to'xtatib qo'ymasligi uchun shu yerda ushlab, log qilib qo'yamiz
        logger.error(f"check_and_send_lesson_reminders job failed: {e}")


async def _process_schedules(session: AsyncSession, schedules, now: datetime) -> None:
    """Berilgan darslar ro'yxati bo'yicha har bir talabaga eslatma yuborish kerakligini tekshiradi"""
    bot = get_bot()
    same_room_skip = _same_room_continuations(
        [(s.group_id, s.start_time, s.end_time, s.room_id, s.id) for s in schedules]
    )

    for sched in schedules:
        if sched.id in same_room_skip:
            continue  # talaba oldingi darsdan beri shu xonada - eslatma shart emas
        try:
            # Dars boshlanish vaqtini pars qilish (masalan "09:00")
            sched_h, sched_m = map(int, sched.start_time.split(":"))
            lesson_start_dt = now.replace(hour=sched_h, minute=sched_m, second=0, microsecond=0)

            # Dars o'tib ketgan bo'lsa o'tkazib yuborish
            time_diff = lesson_start_dt - now
            diff_minutes = int(time_diff.total_seconds() / 60)

            # Eng uzun eslatma oynasidan (180 daqiqa) uzoqdagi yoki o'tib ketgan darslar uchun talabalarni
            # umuman yuklamaymiz - foydalanuvchilar ko'payganda har daqiqadagi bazaga yuklama kichik qoladi
            if diff_minutes < 0 or diff_minutes > MAX_REMINDER_WINDOW_MINUTES:
                continue

            # Guruh talabalarini va ularning sozlamalarini BITTA so'rovda olish
            stmt_users = select(User).where(User.group_id == sched.group_id, User.is_active == True)
            students = (await session.execute(stmt_users)).scalars().all()
            if not students:
                continue
            settings_by_user = {
                st.user_id: st for st in (await session.execute(
                    select(ReminderSetting).where(ReminderSetting.user_id.in_([u.id for u in students]))
                )).scalars().all()
            }

            for student in students:
                setting = settings_by_user.get(student.id)
                minutes_before = setting.minutes_before if setting else 15
                is_enabled = setting.is_enabled if setting else True

                if not is_enabled:
                    continue

                # Dars boshlanishiga aynan minutes_before oralig'i to'g'ri kelsa (masalan 14-16 min oraliqda)
                if 0 <= diff_minutes <= minutes_before:
                    # Takroriy yuborishni oldini olish
                    # created_at UTC'da saqlanadi. Sarlavha aniq solishtiriladi: bir kunda bir xil
                    # fan ikki marta bo'lsa yoki nomi boshqasining boshi bo'lsa, eslatma yo'qolmaydi.
                    log_title = f"Dars: {sched.subject.name if sched.subject else 'Fan nomi'} ({sched.start_time})"
                    # Yuborilgan yoki yuborib BO'LMAYDIGAN (talaba botni bloklagan / yangi botda hali
                    # /start bosmagan) eslatma qayta urinilmaydi - aks holda har daqiqada xato yoziladi.
                    # Vaqtinchalik tarmoq xatolarida esa keyingi daqiqada yana urinib ko'riladi.
                    stmt_log = select(NotificationLog.id).where(
                        NotificationLog.user_id == student.id,
                        NotificationLog.title == log_title,
                        # Aynan shu kungi shu dars (boshlanish vaqti bo'yicha) - created_at/UTC'ga bog'liq emas
                        NotificationLog.scheduled_for == lesson_start_dt.replace(tzinfo=None),
                        or_(
                            NotificationLog.is_success == True,
                            *[NotificationLog.error_message.ilike(f"%{marker}%") for marker in PERMANENT_SEND_ERRORS],
                        ),
                    ).limit(1)
                    res_log = await session.execute(stmt_log)
                    already_sent = res_log.first()

                    if not already_sent:
                        # Sekundlar yaxlitlanadi, sozlamadan ko'p ko'rsatilmaydi
                        minutes_left = min(minutes_before, max(0, math.ceil(time_diff.total_seconds() / 60)))
                        msg_text = format_reminder(
                            sched, minutes_left, lang_of(student), lesson_date=lesson_start_dt.date()
                        )

                        sent_success = False
                        error_txt = None
                        if bot:
                            try:
                                await bot.send_message(
                                    chat_id=student.telegram_id,
                                    text=msg_text,
                                    parse_mode="HTML",
                                )
                                sent_success = True
                            except Exception as e:
                                error_txt = str(e)
                                logger.error(f"Failed to send reminder to {student.telegram_id}: {e}")
                        else:
                            # Mock / test muhitida muvaffaqiyatli deb qayd etiladi
                            sent_success = True

                        # Tarixga yozish
                        notif_log = NotificationLog(
                            user_id=student.id,
                            notification_type=NotificationType.LESSON_REMINDER,
                            title=log_title,
                            body=msg_text,
                            scheduled_for=lesson_start_dt.replace(tzinfo=None),  # mahalliy (Toshkent) vaqt
                            sent_at=now,
                            is_success=sent_success,
                            error_message=error_txt,
                        )
                        session.add(notif_log)
                        await session.commit()
                        logger.info(f"Sent reminder for schedule {sched.id} to student {student.id}")
        except Exception as e:
            logger.error(f"Error checking schedule {sched.id}: {e}")


async def _process_teacher_lessons(session: AsyncSession, today_enum: DayOfWeek, now: datetime) -> None:
    """Tasdiqlangan o'qituvchilarga o'z darslari oldidan eslatma (talabalar bilan bir xil qoidalar)"""
    stmt = (
        select(TeacherLesson, TeacherProfile, User)
        .join(TeacherProfile, TeacherProfile.id == TeacherLesson.teacher_id)
        .join(User, User.id == TeacherProfile.user_id)
        .where(
            TeacherLesson.day_of_week == today_enum,
            TeacherLesson.is_active == True,
            TeacherLesson.week_parity.in_([WeekParity.ALL, week_parity_for(now.date())]),
            TeacherProfile.status == TeacherStatus.APPROVED,
            User.is_active == True,
        )
    )
    rows = (await session.execute(stmt)).all()
    if not rows:
        return
    bot = get_bot()
    same_room_skip = _same_room_continuations(
        [(lesson.teacher_id, lesson.start_time, lesson.end_time, lesson.room, lesson.id) for lesson, _, _ in rows]
    )

    for lesson, profile, user in rows:
        if lesson.id in same_room_skip:
            continue
        try:
            hour, minute = map(int, lesson.start_time.split(":"))
            lesson_start_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            time_diff = lesson_start_dt - now
            diff_minutes = int(time_diff.total_seconds() / 60)

            setting = (await session.execute(
                select(ReminderSetting).where(ReminderSetting.user_id == user.id)
            )).scalar_one_or_none()
            minutes_before = setting.minutes_before if setting else 15
            if setting and not setting.is_enabled:
                continue
            if not (0 <= diff_minutes <= minutes_before):
                continue

            log_title = f"Ustoz: {lesson.subject} ({lesson.start_time}) {lesson.group_name or ''}".strip()[:200]
            already = (await session.execute(
                select(NotificationLog.id).where(
                    NotificationLog.user_id == user.id,
                    NotificationLog.title == log_title,
                    NotificationLog.scheduled_for == lesson_start_dt.replace(tzinfo=None),
                    or_(
                        NotificationLog.is_success == True,
                        *[NotificationLog.error_message.ilike(f"%{m}%") for m in PERMANENT_SEND_ERRORS],
                    ),
                ).limit(1)
            )).first()
            if already:
                continue

            minutes_left = min(minutes_before, max(0, math.ceil(time_diff.total_seconds() / 60)))
            text = format_teacher_reminder(lesson, minutes_left, lang_of(user), lesson_start_dt.date())
            sent_success, error_txt = False, None
            if bot:
                try:
                    await bot.send_message(chat_id=user.telegram_id, text=text, parse_mode="HTML")
                    sent_success = True
                except Exception as e:
                    error_txt = str(e)
                    logger.error(f"Failed to send teacher reminder to {user.telegram_id}: {e}")
            else:
                sent_success = True

            session.add(NotificationLog(
                user_id=user.id,
                notification_type=NotificationType.LESSON_REMINDER,
                title=log_title,
                body=text,
                scheduled_for=lesson_start_dt.replace(tzinfo=None),
                sent_at=now,
                is_success=sent_success,
                error_message=error_txt,
            ))
            await session.commit()
        except Exception as e:
            logger.error(f"Error checking teacher lesson {lesson.id}: {e}")
