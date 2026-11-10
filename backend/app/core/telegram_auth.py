"""
Telegram Mini App (WebApp) orqali kelgan so'rovni tekshirish.

Admin sayt faqat bot ichidagi tugma orqali ochiladi. Telegram har ochilishda `initData`
satrini beradi va uni bot tokeni bilan imzolaydi. Server shu imzoni tekshiradi:
imzo to'g'ri, eskirmagan va foydalanuvchi ADMIN_IDS ro'yxatida bo'lsagina ruxsat beriladi.
Tashqaridan (brauzerda havolani ochib) yoki boshqa foydalanuvchi bilan kirib bo'lmaydi.
"""
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl

# initData shu muddatdan eski bo'lsa qabul qilinmaydi (soniya)
MAX_AGE_SECONDS = 24 * 60 * 60


class TelegramAuthError(Exception):
    pass


def verify_init_data(init_data: str, bot_token: str, max_age: int = MAX_AGE_SECONDS, now: Optional[float] = None) -> Dict[str, Any]:
    """Imzo to'g'ri bo'lsa Telegram foydalanuvchisini (dict) qaytaradi, aks holda TelegramAuthError"""
    if not init_data or not bot_token:
        raise TelegramAuthError("initData yo'q")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise TelegramAuthError("hash yo'q")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise TelegramAuthError("imzo noto'g'ri")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        raise TelegramAuthError("auth_date noto'g'ri")
    if ((now or time.time()) - auth_date) > max_age:
        raise TelegramAuthError("sessiya eskirgan")

    try:
        user = json.loads(pairs.get("user") or "{}")
    except ValueError:
        raise TelegramAuthError("user noto'g'ri")
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        raise TelegramAuthError("foydalanuvchi yo'q")
    return user


def sign_init_data(fields: Dict[str, str], bot_token: str) -> str:
    """Testlar uchun: Telegram qanday imzolasa, xuddi shunday imzolangan initData satri"""
    from urllib.parse import urlencode

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": signature})
