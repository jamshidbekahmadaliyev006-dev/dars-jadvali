from datetime import datetime, timedelta
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enums import DayOfWeek, LessonType, NotificationType, SubmissionStatus, UserRole
from app.models.log import NotificationLog
from app.models.schedule import Schedule, ScheduleSubmission
from app.models.university import Faculty, Group, Subject, University
from app.models.user import User
from app.services.maintenance import run_cleanup


async def _age(db: AsyncSession, model, row_id: int, days: float):
    old = datetime.utcnow() - timedelta(days=days)
    await db.execute(update(model).where(model.id == row_id).values(created_at=old, updated_at=old))
    await db.commit()


@pytest.mark.asyncio
async def test_cleanup_removes_junk_and_keeps_what_is_needed(db_session: AsyncSession):
    univ = University(name="TATU")
    db_session.add(univ)
    await db_session.commit()
    fac = Faculty(name="KX", university_id=univ.id)
    subj = Subject(name="Matematika", university_id=univ.id)
    db_session.add_all([fac, subj])
    await db_session.commit()
    grp = Group(name="712-24", university_id=univ.id, faculty_id=fac.id)
    user = User(telegram_id=1, first_name="T", role=UserRole.USER)
    db_session.add_all([grp, user])
    await db_session.commit()

    def sub(status, image="AgAC123", js='[{"day":"Dushanba"}]'):
        return ScheduleSubmission(
            user_id=user.id, university_id=univ.id, group_id=grp.id, image_file_id=image,
            image_url=f"tg://file/{image}", status=status, ai_extracted_json=js,
        )

    pending, approved_old, approved_new, stale, ancient = (
        sub(SubmissionStatus.ADMIN_REVIEW), sub(SubmissionStatus.APPROVED), sub(SubmissionStatus.APPROVED),
        sub(SubmissionStatus.AI_PROCESSING), sub(SubmissionStatus.REJECTED),
    )
    active = Schedule(university_id=univ.id, group_id=grp.id, subject_id=subj.id, day_of_week=DayOfWeek.MONDAY,
                      start_time="08:00", end_time="09:30", lesson_type=LessonType.LECTURE, is_active=True)
    replaced = Schedule(university_id=univ.id, group_id=grp.id, subject_id=subj.id, day_of_week=DayOfWeek.TUESDAY,
                        start_time="08:00", end_time="09:30", lesson_type=LessonType.LECTURE, is_active=False)
    old_log = NotificationLog(user_id=user.id, notification_type=NotificationType.LESSON_REMINDER, title="eski", body="x", is_success=True)
    new_log = NotificationLog(user_id=user.id, notification_type=NotificationType.LESSON_REMINDER, title="yangi", body="x", is_success=True)
    db_session.add_all([pending, approved_old, approved_new, stale, ancient, active, replaced, old_log, new_log])
    await db_session.commit()

    ids = {
        "pending": pending.id, "approved_new": approved_new.id, "approved_old": approved_old.id,
        "stale": stale.id, "ancient": ancient.id, "active": active.id, "replaced": replaced.id,
        "user": user.id, "grp": grp.id,
    }
    await _age(db_session, ScheduleSubmission, approved_old.id, 3)
    await _age(db_session, ScheduleSubmission, stale.id, 2)
    await _age(db_session, ScheduleSubmission, ancient.id, 40)
    await _age(db_session, Schedule, replaced.id, 20)
    await _age(db_session, NotificationLog, old_log.id, 40)

    result = await run_cleanup(db_session)
    db_session.expire_all()

    # Admin hali ko'rmagan jadvalning rasmi QOLADI (tekshirish uchun kerak)
    p = await db_session.get(ScheduleSubmission, ids["pending"])
    assert p.image_file_id == "AgAC123" and p.ai_extracted_json
    # Yangi qaror qilingan (1 kundan kam) - hali tegilmaydi; eskisi - rasm havolasi va xom natija o'chdi
    assert (await db_session.get(ScheduleSubmission, ids["approved_new"])).image_file_id == "AgAC123"
    a = await db_session.get(ScheduleSubmission, ids["approved_old"])
    assert a.image_file_id == "-" and a.image_url is None and a.ai_extracted_json is None and a.status == SubmissionStatus.APPROVED
    # Qotib qolgan so'rov yopildi, 40 kunlik qaror yozuvi o'chdi
    assert (await db_session.get(ScheduleSubmission, ids["stale"])).status == SubmissionStatus.NEEDS_CORRECTION
    assert await db_session.get(ScheduleSubmission, ids["ancient"]) is None
    # Faol dars QOLADI, almashtirilgan eskisi o'chdi
    assert await db_session.get(Schedule, ids["active"]) is not None
    assert await db_session.get(Schedule, ids["replaced"]) is None
    # Eski log o'chdi, yangisi qoldi
    titles = (await db_session.execute(select(NotificationLog.title))).scalars().all()
    assert titles == ["yangi"]
    assert result["notification_logs_deleted"] == 1 and result["inactive_lessons_deleted"] == 1
    # Foydalanuvchi va guruh tegilmagan
    assert await db_session.get(User, ids["user"]) is not None and await db_session.get(Group, ids["grp"]) is not None


@pytest.mark.asyncio
async def test_decision_clears_the_photo_reference_immediately(db_session: AsyncSession):
    from app.schemas.schedule import ScheduleSubmissionReview
    from app.services.schedule_service import ScheduleService

    univ = University(name="TATU")
    db_session.add(univ)
    await db_session.commit()
    user = User(telegram_id=2, first_name="T", role=UserRole.USER)
    db_session.add(user)
    await db_session.commit()
    s = ScheduleSubmission(user_id=user.id, university_id=univ.id, image_file_id="AgACxyz", image_url="tg://file/AgACxyz",
                           status=SubmissionStatus.ADMIN_REVIEW)
    db_session.add(s)
    await db_session.commit()

    done = await ScheduleService.review_submission(
        db_session, s.id, user.id, ScheduleSubmissionReview(status=SubmissionStatus.REJECTED, admin_notes="x")
    )
    assert done.image_file_id == "-" and done.image_url is None
