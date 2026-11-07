from typing import Any, Dict
from aiogram.types import WebAppInfo
from app.core.logging import logger

_warned_urls = set()


def mini_app_button_kwargs(url: str) -> Dict[str, Any]:
    """
    Telegram faqat HTTPS manzillarga WebApp tugmasini ochishga ruxsat beradi - aks holda
    butun xabar yuborilmay, handler xatolik bilan yiqiladi (masalan http://localhost:3000
    bilan lokal ishlab chiqishda). Shu sababli HTTPS bo'lmasa, WebApp o'rniga oddiy havola
    tugmasiga tushamiz - bot hech bo'lmasa ishlayveradi, Mini App esa HTTPS olinganda
    avtomatik ravishda haqiqiy WebApp sifatida ochiladi.
    """
    if url.lower().startswith("https://"):
        return {"web_app": WebAppInfo(url=url)}

    if url not in _warned_urls:
        _warned_urls.add(url)
        logger.warning(
            f"MINI_APP_URL ('{url}') HTTPS emas - Telegram WebApp tugmasini qabul qilmaydi. "
            "Vaqtincha oddiy havola tugmasi ishlatilmoqda. Mini App to'liq ishlashi uchun uni "
            "HTTPS orqali (masalan ngrok/cloudflared tunnel yoki haqiqiy domen bilan) joylashtiring."
        )
    return {"url": url}
