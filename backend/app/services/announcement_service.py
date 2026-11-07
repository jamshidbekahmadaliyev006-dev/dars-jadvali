from typing import List, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.log import Announcement
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate


class AnnouncementService:
    @staticmethod
    async def get_announcements_for_user(
        session: AsyncSession,
        university_id: int,
        group_id: Optional[int] = None,
    ) -> List[Announcement]:
        stmt = (
            select(Announcement)
            .where(
                Announcement.university_id == university_id,
                or_(
                    Announcement.target_group_id.is_(None),
                    Announcement.target_group_id == group_id,
                ),
            )
            .order_by(Announcement.is_pinned.desc(), Announcement.id.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_all_announcements(
        session: AsyncSession,
        university_id: Optional[int] = None,
    ) -> List[Announcement]:
        stmt = select(Announcement)
        if university_id:
            stmt = stmt.where(Announcement.university_id == university_id)
        stmt = stmt.order_by(Announcement.is_pinned.desc(), Announcement.id.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_announcement(session: AsyncSession, payload: AnnouncementCreate) -> Announcement:
        ann = Announcement(**payload.model_dump())
        session.add(ann)
        await session.commit()
        await session.refresh(ann)
        return ann

    @staticmethod
    async def update_announcement(session: AsyncSession, announcement_id: int, payload: AnnouncementUpdate) -> Optional[Announcement]:
        stmt = select(Announcement).where(Announcement.id == announcement_id)
        result = await session.execute(stmt)
        ann = result.scalar_one_or_none()
        if not ann:
            return None
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(ann, k, v)
        await session.commit()
        await session.refresh(ann)
        return ann

    @staticmethod
    async def delete_announcement(session: AsyncSession, announcement_id: int) -> bool:
        stmt = select(Announcement).where(Announcement.id == announcement_id)
        result = await session.execute(stmt)
        ann = result.scalar_one_or_none()
        if not ann:
            return False
        await session.delete(ann)
        await session.commit()
        return True
