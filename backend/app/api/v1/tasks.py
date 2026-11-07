from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.task import (
    PersonalEventCreate, PersonalEventResponse, PersonalEventUpdate,
    PersonalTaskCreate, PersonalTaskResponse, PersonalTaskUpdate,
)
from app.services.task_service import TaskService

router = APIRouter(tags=["Personal Tasks & Calendar Events"])


# --- Personal Tasks ---
@router.get("/tasks", response_model=List[PersonalTaskResponse])
async def list_my_tasks(
    is_completed: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await TaskService.get_user_tasks(session, current_user.id, is_completed)


@router.post("/tasks", response_model=PersonalTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: PersonalTaskCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await TaskService.create_task(session, current_user.id, payload)


@router.put("/tasks/{task_id}", response_model=PersonalTaskResponse)
async def update_task(
    task_id: int,
    payload: PersonalTaskUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await TaskService.update_task(session, task_id, current_user.id, payload)
    if not task:
        raise HTTPException(status_code=404, detail="Vazifa topilmadi")
    return task


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = await TaskService.delete_task(session, task_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Vazifa topilmadi")
    return None


# --- Personal Events (Calendar) ---
@router.get("/events", response_model=List[PersonalEventResponse])
async def list_my_events(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await TaskService.get_user_events(session, current_user.id)


@router.post("/events", response_model=PersonalEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: PersonalEventCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await TaskService.create_event(session, current_user.id, payload)


@router.put("/events/{event_id}", response_model=PersonalEventResponse)
async def update_event(
    event_id: int,
    payload: PersonalEventUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = await TaskService.update_event(session, event_id, current_user.id, payload)
    if not event:
        raise HTTPException(status_code=404, detail="Kalendar tadbiri topilmadi")
    return event


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = await TaskService.delete_event(session, event_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Kalendar tadbiri topilmadi")
    return None
