import os
from datetime import date
from functools import lru_cache
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Qulay Jadval"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Telegram Bot
    BOT_TOKEN: str = Field(default="fake_token_for_init", description="Telegram Bot API Token")
    ADMIN_IDS_RAW: str = Field(default="", alias="ADMIN_IDS")
    ADMIN_USERNAMES_RAW: str = Field(default="", alias="ADMIN_USERNAMES")
    ADMIN_PHONES_RAW: str = Field(default="", alias="ADMIN_PHONES")

    # Mini App
    MINI_APP_URL: str = "https://uninotify.app"
    # Admin sayt manzili (botdagi "Admin sayt" tugmasi shu yerni ochadi). Bo'sh bo'lsa tugma ishlamaydi.
    ADMIN_WEB_URL: str = ""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./uninotify.db"

    # Security
    SECRET_KEY: str = "uninotify-dev-secret-key-phase1-super-secure-token"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Timezone
    TIMEZONE: str = "Asia/Tashkent"

    # Toq hafta boshlanadigan istalgan dushanba. Universitet hisobi ISO hafta raqamiga mos
    # kelmaydi (2026-11-09 ISO bo'yicha 46-hafta, universitetda esa toq), shuning uchun shu
    # sanadan sanaladi. Yangi semestrda hisob surilsa, shu qiymat yangilanadi.
    WEEK_PARITY_ODD_MONDAY: date = date(2026, 11, 9)

    # AI Provider Settings
    AI_PROVIDER: str = Field(default="mock", description="AI Provider: mock, gemini, groq")
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Google Gemini API Key")
    GROQ_API_KEY: Optional[str] = Field(default=None, description="Groq (OpenAI-compatible) API Key")
    GROQ_MODEL: str = Field(default="openai/gpt-oss-120b", description="Groq matnli chat uchun model nomi")

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

    @property
    def admin_username_list(self) -> List[str]:
        """
        @ belgisisiz, kichik harflarda normallashtirilgan admin username'lar ro'yxati.

        DIQQAT: Bu faqat ma'lumot/eslatma uchun ishlatiladi (operatorga "bu username ADMIN_IDS'ga
        qo'shilishi kerak" deb eslatish uchun) - haqiqiy ADMIN huquqini berishda HECH QACHON
        ishlatilmaydi, chunki Telegram username'ni istalgan foydalanuvchi istalgan vaqtda
        o'zgartirib, o'zini admin sifatida ko'rsatishi mumkin edi. Rol faqat o'zgarmas
        telegram_id (ADMIN_IDS) orqali beriladi.
        """
        if not self.ADMIN_USERNAMES_RAW:
            return []
        return [
            item.strip().lstrip("@").lower()
            for item in self.ADMIN_USERNAMES_RAW.split(",")
            if item.strip()
        ]

    def is_admin(self, telegram_id: int) -> bool:
        """ADMIN huquqi faqat o'zgarmas Telegram ID orqali beriladi - username bo'yicha EMAS"""
        return telegram_id in self.admin_id_list


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
