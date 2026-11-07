from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import UserUpdate


class UserService:
    @staticmethod
    async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
        """Telegram ID bo'yicha foydalanuvchini olish"""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
        """Ichki database ID bo'yicha foydalanuvchini olish"""
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create_user(
        session: AsyncSession,
        telegram_id: int,
        first_name: str,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
        language_code: str = "uz",
    ) -> tuple[User, bool]:
        """
        Foydalanuvchini olish yoki yangi yaratish.
        ADMIN_IDS ro'yxatida bo'lsa, avtomatik ADMIN roli belgilanadi.
        Qaytadi: (user, created: bool)
        """
        user = await UserService.get_by_telegram_id(session, telegram_id)
        
        # Admin huquqini tekshirish
        is_system_admin = settings.is_admin(telegram_id)
        role = UserRole.ADMIN if is_system_admin else UserRole.USER

        if user:
            # Mavjud user - profil ma'lumotlarini yangilash
            updated = False
            if user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if user.last_name != last_name:
                user.last_name = last_name
                updated = True
            if user.username != username:
                user.username = username
                updated = True
            
            # Agar foydalanuvchi ADMIN_IDS ga qo'shilgan bo'lsa, rolini yangilash
            if is_system_admin and user.role != UserRole.ADMIN:
                user.role = UserRole.ADMIN
                updated = True

            if updated:
                await session.commit()
                await session.refresh(user)
                logger.info(f"User {telegram_id} updated: role={user.role}")
            return user, False
        else:
            # Yangi foydalanuvchi ro'yxatdan o'tkazish
            new_user = User(
                telegram_id=telegram_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                language_code=language_code or "uz",
                role=role,
                is_active=True,
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            logger.info(f"New user registered: id={new_user.id}, tg_id={telegram_id}, role={role}")
            return new_user, True

    @staticmethod
    async def list_users(session: AsyncSession, skip: int = 0, limit: int = 50) -> List[User]:
        """Foydalanuvchilar ro'yxatini olish"""
        stmt = select(User).offset(skip).limit(limit).order_by(User.id.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_my_profile(session: AsyncSession, user: User, payload: UserUpdate) -> User:
        """
        Talabaning o'z profilini (til, universitet/fakultet/guruh) yangilashi.
        Rol va faollik holati bu orqali o'zgartirilmaydi - xavfsizlik uchun faqat
        admin API (/users/{id}/role) orqali amalga oshiriladi.
        """
        data = payload.model_dump(exclude_unset=True)
        data.pop("is_active", None)

        group_id = data.get("group_id")
        if group_id:
            # Noto'g'ri qo'lda yuborilgan university_id/faculty_id o'rniga guruhning
            # haqiqiy universitet/fakultetiga avtomatik moslashtiramiz
            from app.services.university_service import UniversityService

            group = await UniversityService.get_group_by_id(session, group_id)
            if not group:
                raise ValueError("Tanlangan guruh topilmadi")
            data["university_id"] = group.university_id
            data["faculty_id"] = group.faculty_id

        for key, value in data.items():
            setattr(user, key, value)

        await session.commit()
        await session.refresh(user)
        logger.info(f"User {user.telegram_id} updated own profile: {data}")
        return user

    @staticmethod
    async def update_role(session: AsyncSession, user_id: int, new_role: UserRole) -> Optional[User]:
        """Foydalanuvchi rolini o'zgartirish (Faqat admin tomonidan)"""
        user = await UserService.get_by_id(session, user_id)
        if not user:
            return None
        user.role = new_role
        await session.commit()
        await session.refresh(user)
        logger.info(f"User {user_id} role updated to {new_role}")
        return user
