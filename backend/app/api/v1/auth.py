from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.auth import TelegramAuthRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/telegram-webapp", response_model=TokenResponse)
async def auth_telegram_webapp(
    payload: TelegramAuthRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Telegram Mini App initData orqali xavfsiz autentifikatsiya.
    Telegram HMAC hash tekshiriladi, muvaffaqiyatli bo'lsa JWT token qaytariladi.
    """
    result = await AuthService.authenticate_webapp(session, payload.init_data)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autentifikatsiya muvaffaqiyatsiz bo'ldi. Yaroqsiz Telegram initData.",
        )
    return result
