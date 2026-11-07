from datetime import datetime, timedelta
import pytz
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.bot_instance import get_bot
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import logger
from app.models.enums import DayOfWeek, NotificationType
from app.models.log import NotificationLog
from app.models.schedule import ReminderSetting, Schedule
from app.models.user import User


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
                .where(Schedule.day_of_week == today_enum, Schedule.is_active == True)
            )
            res = await session.execute(stmt)
            schedules = res.scalars().all()
            await _process_schedules(session, schedules, now)
    except Exception as e:
        # Vazifa ichidagi kutilmagan xatolik (masalan, DB vaqtincha mavjud emas) butun
        # schedulerni to'xtatib qo'ymasligi uchun shu yerda ushlab, log qilib qo'yamiz
        logger.error(f"check_and_send_lesson_reminders job failed: {e}")


async def _process_schedules(session: AsyncSession, schedules, now: datetime) -> None:
    """Berilgan darslar ro'yxati bo'yicha har bir talabaga eslatma yuborish kerakligini tekshiradi"""
    bot = get_bot()

    for sched in schedules:
        try:
            # Dars boshlanish vaqtini pars qilish (masalan "09:00")
            sched_h, sched_m = map(int, sched.start_time.split(":"))
            lesson_start_dt = now.replace(hour=sched_h, minute=sched_m, second=0, microsecond=0)

            # Dars o'tib ketgan bo'lsa o'tkazib yuborish
            time_diff = lesson_start_dt - now
            diff_minutes = int(time_diff.total_seconds() / 60)

            # Guruh talabalarini olish
            stmt_users = select(User).where(User.group_id == sched.group_id, User.is_active == True)
            res_users = await session.execute(stmt_users)
            students = res_users.scalars().all()

            for student in students:
                # Talabaning eslatma sozlamasini tekshirish
                stmt_setting = select(ReminderSetting).where(ReminderSetting.user_id == student.id)
                res_setting = await session.execute(stmt_setting)
                setting = res_setting.scalar_one_or_none()
                minutes_before = setting.minutes_before if setting else 15
                is_enabled = setting.is_enabled if setting else True

                if not is_enabled:
                    continue

                # Dars boshlanishiga aynan minutes_before oralig'i to'g'ri kelsa (masalan 14-16 min oraliqda)
                if 0 <= diff_minutes <= minutes_before:
                    # Takroriy yuborishni oldini olish
                    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    stmt_log = select(NotificationLog).where(
                        NotificationLog.user_id == student.id,
                        NotificationLog.title.contains(f"Dars: {sched.subject.name if sched.subject else ''}"),
                        NotificationLog.created_at >= today_start,
                    )
                    res_log = await session.execute(stmt_log)
                    already_sent = res_log.scalar_one_or_none()

                    if not already_sent:
                        # Eslatma matnini tayyorlash
                        univ_name = sched.group.university.name if (sched.group and sched.group.university) else "Universitet"
                        subj_name = sched.subject.name if sched.subject else "Fan nomi"
                        teacher_name = sched.teacher.full_name if sched.teacher else "O'qituvchi belgilanmagan"
                        bld_name = sched.room.building.name if (sched.room and sched.room.building) else "Bino"
                        floor_num = sched.room.floor if sched.room and sched.room.floor else "-"
                        room_num = sched.room.number if sched.room else "Xona belgilanmagan"

                        msg_text = (
                            f"⏰ <b>Dars eslatmasi ({diff_minutes} daqiqadan so'ng)!</b>\n\n"
                            f"🏛 <b>Universitet:</b> {univ_name}\n"
                            f"📚 <b>Fan:</b> {subj_name}\n"
                            f"👨‍🏫 <b>O'qituvchi:</b> {teacher_name}\n"
                            f"🏢 <b>Bino:</b> {bld_name} (Qavat: {floor_num})\n"
                            f"🚪 <b>Xona:</b> {room_num}\n"
                            f"🕒 <b>Boshlanish vaqti:</b> {sched.start_time} - {sched.end_time}\n\n"
                            f"<i>Darsga kechikmasdan boring!</i>"
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
                            title=f"Dars: {subj_name} ({sched.start_time})",
                            body=msg_text,
                            scheduled_for=lesson_start_dt,
                            sent_at=now,
                            is_success=sent_success,
                            error_message=error_txt,
                        )
                        session.add(notif_log)
                        await session.commit()
                        logger.info(f"Sent reminder for lesson {subj_name} to student {student.id}")
        except Exception as e:
            logger.error(f"Error checking schedule {sched.id}: {e}")
