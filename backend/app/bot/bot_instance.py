from typing import Optional
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonDefault
from app.core.config import settings
from app.core.logging import logger

bot: Optional[Bot] = None


async def reset_menu_button(bot: Bot) -> None:
    """
    Chat qatorining chap burchagidagi Mini App tugmasini olib tashlaydi. Telegram oldin
    o'rnatilgan tugmani eslab qoladi, shuning uchun uni har ishga tushishda standart holatga
    qaytaramiz - hozircha Mini App kerak emas, hamma narsa bot menyusi orqali ishlaydi.
    """
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
        logger.info("Chat menyusidagi Mini App tugmasi olib tashlandi.")
    except Exception as e:
        logger.error(f"Chat menu tugmasini tiklashda xatolik: {e}")


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
