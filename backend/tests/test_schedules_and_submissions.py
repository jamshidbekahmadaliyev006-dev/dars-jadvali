import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enums import DayOfWeek, LessonType, SubmissionStatus, UserRole
from app.models.user import User
from app.schemas.schedule import ReminderSettingUpdate, ScheduleCreate, ScheduleSubmissionCreate, ScheduleSubmissionReview, ScheduleUpdate
from app.schemas.university import FacultyCreate, GroupCreate, SubjectCreate, UniversityCreate
from app.services.schedule_service import ScheduleService
from app.services.university_service import UniversityService


@pytest.mark.asyncio
async def test_schedule_service_flow(db_session: AsyncSession):
    # Dastlabki ma'lumotlar
    univ = await UniversityService.create_university(db_session, UniversityCreate(name="TATU Urganch filiali"))
    fac = await UniversityService.create_faculty(db_session, FacultyCreate(name="AKT", university_id=univ.id))
    grp = await UniversityService.create_group(db_session, GroupCreate(name="941-21", university_id=univ.id, faculty_id=fac.id))
    subj = await UniversityService.create_subject(db_session, SubjectCreate(name="Kiberxavfsizlik", university_id=univ.id))

    student = User(telegram_id=98712345, first_name="Sanjar", role=UserRole.USER, university_id=univ.id, group_id=grp.id)
    admin = User(telegram_id=123456789, first_name="Admin", role=UserRole.ADMIN)
    db_session.add_all([student, admin])
    await db_session.commit()

    # 1. Schedule yaratish
    sched = await ScheduleService.create_schedule(
        db_session,
        ScheduleCreate(
            university_id=univ.id,
            group_id=grp.id,
            subject_id=subj.id,
            day_of_week=DayOfWeek.MONDAY,
            start_time="09:00",
            end_time="10:20",
            lesson_type=LessonType.LECTURE,
        ),
    )
    assert sched.id is not None

    # 2. Schedule filter
    list_sched = await ScheduleService.get_schedules(db_session, group_id=grp.id, day_of_week=DayOfWeek.MONDAY)
    assert len(list_sched) == 1
    assert list_sched[0].start_time == "09:00"

    # 3. Reminder settings
    rem = await ScheduleService.update_reminder_setting(db_session, student.id, ReminderSettingUpdate(is_enabled=True, minutes_before=20))
    assert rem.minutes_before == 20

    # 4. Schedule submission workflow
    sub = await ScheduleService.create_submission(
        db_session,
        student.id,
        ScheduleSubmissionCreate(university_id=univ.id, group_id=grp.id, image_file_id="img_abc_123"),
    )
    assert sub.id is not None
    assert sub.status == SubmissionStatus.PENDING

    # 5. Review & Approve
    review_data = ScheduleSubmissionReview(
        status=SubmissionStatus.APPROVED,
        admin_notes="Barcha darslar to'g'ri",
        approved_schedules=[
            {
                "subject_id": subj.id,
                "day_of_week": "TUESDAY",
                "start_time": "10:30",
                "end_time": "11:50",
                "lesson_type": "PRACTICE",
            }
        ],
    )
    reviewed_sub = await ScheduleService.review_submission(db_session, sub.id, admin.id, review_data)
    assert reviewed_sub.status == SubmissionStatus.APPROVED

    # Approved bo'lgach yangi dars bazaga qo'shilganini tekshirish
    tuesday_schedules = await ScheduleService.get_schedules(db_session, group_id=grp.id, day_of_week=DayOfWeek.TUESDAY)
    assert len(tuesday_schedules) == 1
    assert tuesday_schedules[0].start_time == "10:30"
