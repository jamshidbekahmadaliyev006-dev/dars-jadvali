from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enums import TaskPriority, UserRole
from app.models.user import User
from app.schemas.task import PersonalEventCreate, PersonalTaskCreate, PersonalTaskUpdate
from app.services.task_service import TaskService


@pytest.mark.asyncio
async def test_personal_task_and_event_isolation(db_session: AsyncSession):
    user1 = User(telegram_id=11111, first_name="User1", role=UserRole.USER)
    user2 = User(telegram_id=22222, first_name="User2", role=UserRole.USER)
    db_session.add_all([user1, user2])
    await db_session.commit()

    # User 1 vazifa yaratadi
    task1 = await TaskService.create_task(
        db_session,
        user1.id,
        PersonalTaskCreate(title="Fizika masalalarini yechish", priority=TaskPriority.HIGH),
    )
    assert task1.id is not None

    # User 2 o'z vazifalarini ko'rganda bo'sh bo'lishi kerak (Data Isolation)
    u2_tasks = await TaskService.get_user_tasks(db_session, user2.id)
    assert len(u2_tasks) == 0

    # User 1 o'z vazifasini o'zgartiradi
    updated_task = await TaskService.update_task(
        db_session,
        task1.id,
        user1.id,
        PersonalTaskUpdate(is_completed=True),
    )
    assert updated_task.is_completed is True

    # User 2 boshqa odamning vazifasini o'zgartira olmaydi
    hacked = await TaskService.update_task(
        db_session,
        task1.id,
        user2.id,
        PersonalTaskUpdate(title="Xakerlik"),
    )
    assert hacked is None

    # Calendar Event testi
    now = datetime.now(timezone.utc)
    event1 = await TaskService.create_event(
        db_session,
        user1.id,
        PersonalEventCreate(title="Oraliq nazorat imtihoni", event_type="exam", start_time=now),
    )
    assert event1.id is not None
    u1_events = await TaskService.get_user_events(db_session, user1.id)
    assert len(u1_events) == 1
