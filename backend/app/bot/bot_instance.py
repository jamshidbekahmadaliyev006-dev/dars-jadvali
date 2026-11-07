from typing import Optional
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from app.core.config import settings
from app.core.logging import logger

bot: Optional[Bot] = None


def get_bot() -> Optional[Bot]:
    global bot
    if bot is not None:
        return bot

    token = settings.BOT_TOKEN
    if not token or "fake" in token.lower() or token.startswith("0000"):
        logger.warning("Bot token is not configured or is a placeholder. Bot instance is idle.")
        return None

    try:
        bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        return bot
    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}")
        return None
