from typing import Optional
from pydantic import BaseModel
from app.schemas.user import UserResponse


class TelegramAuthRequest(BaseModel):
    init_data: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenPayload(BaseModel):
    sub: str  # telegram_id as string
    user_id: int
    role: str
