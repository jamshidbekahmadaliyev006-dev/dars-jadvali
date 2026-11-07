import os
from functools import lru_cache
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "UniNotify"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Telegram Bot
    BOT_TOKEN: str = Field(default="fake_token_for_init", description="Telegram Bot API Token")
    ADMIN_IDS_RAW: str = Field(default="", alias="ADMIN_IDS")

    # Mini App
    MINI_APP_URL: str = "https://uninotify.app"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./uninotify.db"

    # Security
    SECRET_KEY: str = "uninotify-dev-secret-key-phase1-super-secure-token"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Timezone
    TIMEZONE: str = "Asia/Tashkent"

    # AI Provider Settings
    AI_PROVIDER: str = Field(default="mock", description="AI Provider: mock, gemini, openai")
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Google Gemini API Key")

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def admin_id_list(self) -> List[int]:
        if not self.ADMIN_IDS_RAW:
            return []
        ids = []
        for item in self.ADMIN_IDS_RAW.split(","):
            cleaned = item.strip()
            if cleaned and cleaned.isdigit():
                ids.append(int(cleaned))
        return ids

    def is_admin(self, telegram_id: int) -> bool:
        return telegram_id in self.admin_id_list


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
