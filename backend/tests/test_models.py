import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enums import DayOfWeek, LessonType, SubmissionStatus, TaskPriority, UserRole
from app.models.schedule import ReminderSetting, Schedule, ScheduleSubmission
from app.models.task import PersonalEvent, PersonalTask
from app.models.university import Building, Faculty, Group, Room, Subject, Teacher, University
from app.models.user import User


@pytest.mark.asyncio
async def test_full_university_hierarchy(db_session: AsyncSession):
    # 1. Universitet yaratish
    univ = University(name="Toshkent Axborot Texnologiyalari Universiteti", short_name="TATU")
    db_session.add(univ)
    await db_session.commit()
    await db_session.refresh(univ)
    assert univ.id is not None

    # 2. Fakultet
    faculty = Faculty(university_id=univ.id, name="Dasturiy injiniring", short_name="DI")
    db_session.add(faculty)
    await db_session.commit()
    await db_session.refresh(faculty)

    # 3. Guruh
    group = Group(university_id=univ.id, faculty_id=faculty.id, name="DI-21-04", course_number=3)
    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)

    # 4. Bino va Xona
    building = Building(university_id=univ.id, name="E-Bino", address="Amir Temur 108")
    db_session.add(building)
    await db_session.commit()
    await db_session.refresh(building)

    room = Room(building_id=building.id, number="404", floor=4, capacity=30)
    db_session.add(room)
    await db_session.commit()
    await db_session.refresh(room)

    # 5. Fan va O'qituvchi
    subject = Subject(university_id=univ.id, name="Sun'iy intellekt asoslari", code="AI-301")
    teacher = Teacher(university_id=univ.id, full_name="Dr. Alisher Navoiy")
    db_session.add_all([subject, teacher])
    await db_session.commit()
    await db_session.refresh(subject)
    await db_session.refresh(teacher)

    # 6. Talaba
    student = User(
        telegram_id=987654321,
        first_name="Jasur",
        role=UserRole.USER,
        university_id=univ.id,
        faculty_id=faculty.id,
        group_id=group.id,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)

    # 7. Dars jadvali
    schedule = Schedule(
        university_id=univ.id,
        group_id=group.id,
        subject_id=subject.id,
        teacher_id=teacher.id,
        room_id=room.id,
        day_of_week=DayOfWeek.MONDAY,
        start_time="09:00",
        end_time="10:20",
        lesson_type=LessonType.LECTURE,
    )
    db_session.add(schedule)

    # 8. Shaxsiy vazifalar va tadbirlar
    task = PersonalTask(
        user_id=student.id,
        title="AI bo'yicha mustaqil ish topshirish",
        priority=TaskPriority.HIGH,
    )
    reminder = ReminderSetting(
        user_id=student.id,
        is_enabled=True,
        minutes_before=15,
    )
    db_session.add_all([task, reminder])
    await db_session.commit()

    assert schedule.id is not None
    assert task.id is not None
    assert reminder.minutes_before == 15
    assert student.university_id == univ.id
