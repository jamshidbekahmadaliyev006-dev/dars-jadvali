from typing import Optional
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonWebApp, WebAppInfo
from app.core.config import settings
from app.core.logging import logger

bot: Optional[Bot] = None


async def setup_mini_app_menu_button(bot: Bot) -> None:
    """
    Chat input qatorining chap tomonidagi doimiy "Open"/menyu tugmasini to'g'ridan-to'g'ri
    Mini App'ni ochadigan qilib sozlaydi (Telegram'ning o'zi taqdim etadigan imkoniyat).
    Faqat MINI_APP_URL HTTPS bo'lganda ishlaydi - Telegram boshqa holatda qabul qilmaydi.
    """
    if not settings.MINI_APP_URL.lower().startswith("https://"):
        logger.warning(
            "Chat menyusidagi 'Open' tugmasi sozlanmadi: MINI_APP_URL HTTPS emas "
            f"('{settings.MINI_APP_URL}'). HTTPS manzil qo'yilgach, server qayta "
            "ishga tushirilganda avtomatik yoqiladi."
        )
        return

    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="UniNotify",
                web_app=WebAppInfo(url=settings.MINI_APP_URL),
            )
        )
        logger.info("Chat menyusining 'Open' tugmasi Mini App'ga ulandi.")
    except Exception as e:
        logger.error(f"Chat menu tugmasini sozlashda xatolik: {e}")


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
