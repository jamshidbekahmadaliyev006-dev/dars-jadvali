from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import logger
from app.core.security import create_access_token, validate_telegram_init_data
from app.schemas.auth import TokenResponse
from app.schemas.user import UserResponse
from app.services.user_service import UserService


class AuthService:
    @staticmethod
    async def authenticate_webapp(
        session: AsyncSession,
        init_data: str,
    ) -> Optional[TokenResponse]:
        """
        Telegram WebApp initData orqali xavfsiz autentifikatsiya qilish.
        Faqat frontend yuborgan id'ga ishonilmaydi, Telegram HMAC-SHA256 tekshiriladi.
        """
        validated_data = validate_telegram_init_data(init_data)
        if not validated_data or "user" not in validated_data:
            logger.warning("Webapp auth failed: Invalid initData or hash mismatch")
            return None

        tg_user = validated_data["user"]
        telegram_id = int(tg_user["id"])
        first_name = tg_user.get("first_name", "Student")
        last_name = tg_user.get("last_name")
        username = tg_user.get("username")
        language_code = tg_user.get("language_code", "uz")

        user, _ = await UserService.get_or_create_user(
            session=session,
            telegram_id=telegram_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            language_code=language_code,
        )

        # JWT Token yaratish
        payload = {
            "sub": str(user.telegram_id),
            "user_id": user.id,
            "role": user.role.value,
        }
        token = create_access_token(payload)

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )
