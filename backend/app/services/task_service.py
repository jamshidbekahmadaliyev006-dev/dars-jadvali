from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.task import PersonalEvent, PersonalTask
from app.schemas.task import PersonalEventCreate, PersonalEventUpdate, PersonalTaskCreate, PersonalTaskUpdate


class TaskService:
    # --- Personal Tasks ---
    @staticmethod
    async def get_user_tasks(
        session: AsyncSession,
        user_id: int,
        is_completed: Optional[bool] = None,
    ) -> List[PersonalTask]:
        stmt = select(PersonalTask).where(PersonalTask.user_id == user_id)
        if is_completed is not None:
            stmt = stmt.where(PersonalTask.is_completed == is_completed)
        stmt = stmt.order_by(PersonalTask.is_completed.asc(), PersonalTask.due_date.asc(), PersonalTask.id.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_task_by_id(session: AsyncSession, task_id: int, user_id: int) -> Optional[PersonalTask]:
        stmt = select(PersonalTask).where(PersonalTask.id == task_id, PersonalTask.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_task(session: AsyncSession, user_id: int, payload: PersonalTaskCreate) -> PersonalTask:
        task = PersonalTask(user_id=user_id, **payload.model_dump())
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def update_task(session: AsyncSession, task_id: int, user_id: int, payload: PersonalTaskUpdate) -> Optional[PersonalTask]:
        task = await TaskService.get_task_by_id(session, task_id, user_id)
        if not task:
            return None
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(task, k, v)
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def delete_task(session: AsyncSession, task_id: int, user_id: int) -> bool:
        task = await TaskService.get_task_by_id(session, task_id, user_id)
        if not task:
            return False
        await session.delete(task)
        await session.commit()
        return True

    # --- Personal Events (Calendar) ---
    @staticmethod
    async def get_user_events(session: AsyncSession, user_id: int) -> List[PersonalEvent]:
        stmt = select(PersonalEvent).where(PersonalEvent.user_id == user_id).order_by(PersonalEvent.start_time.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_event_by_id(session: AsyncSession, event_id: int, user_id: int) -> Optional[PersonalEvent]:
        stmt = select(PersonalEvent).where(PersonalEvent.id == event_id, PersonalEvent.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_event(session: AsyncSession, user_id: int, payload: PersonalEventCreate) -> PersonalEvent:
        event = PersonalEvent(user_id=user_id, **payload.model_dump())
        session.add(event)
        await session.commit()
        await session.refresh(event)
        return event

    @staticmethod
    async def update_event(session: AsyncSession, event_id: int, user_id: int, payload: PersonalEventUpdate) -> Optional[PersonalEvent]:
        event = await TaskService.get_event_by_id(session, event_id, user_id)
        if not event:
            return None
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(event, k, v)
        await session.commit()
        await session.refresh(event)
        return event

    @staticmethod
    async def delete_event(session: AsyncSession, event_id: int, user_id: int) -> bool:
        event = await TaskService.get_event_by_id(session, event_id, user_id)
        if not event:
            return False
        await session.delete(event)
        await session.commit()
        return True
