import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, unquote
import jwt
from app.core.config import settings
from app.core.logging import logger


def validate_telegram_init_data(init_data: str, bot_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Telegram Mini App initData ni rasmiy Telegram xavfsizlik standarti bo'yicha tekshirish.
    
    1. init_data query string pars qilinadi.
    2. 'hash' parametri ajratib olinadi.
    3. Qolgan barcha parametrlar alifbo tartibida 'key=value\n' shaklida birlashtiriladi.
    4. bot_token yordamida 'WebAppData' kalitiga HMAC-SHA256 hisoblanadi.
    5. Olingan secret key bilan ma'lumotlar satriga HMAC-SHA256 qo'llanadi.
    6. Natija 'hash' bilan solishtiriladi.
    """
    token = bot_token or settings.BOT_TOKEN
    if not init_data or not token:
        return None

    try:
        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed_data.pop("hash", None)
        if not received_hash:
            return None

        # Ma'lumotlarni alifbo tartibida saralash
        data_check_string = "\n".join(
            f"{key}={value}" for key, value in sorted(parsed_data.items(), key=lambda x: x[0])
        )

        # Telegram spec: secret_key = HMAC_SHA256("WebAppData", bot_token)
        secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
        
        # Hisoblangan hash
        calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if hmac.compare_digest(calculated_hash, received_hash):
            # Auth date tekshiruvi (masalan, 24 soat ichida bo'lishi)
            auth_date = int(parsed_data.get("auth_date", 0))
            current_time = int(time.time())
            # 86400 soniya (24 soat)
            if current_time - auth_date > 86400 and not settings.DEBUG:
                logger.warning("Telegram initData expired")
                return None

            # User obyektini JSON'dan dict'ga aylantirish
            if "user" in parsed_data:
                parsed_data["user"] = json.loads(parsed_data["user"])

            return parsed_data
        else:
            logger.warning("Telegram initData hash mismatch")
            return None
    except Exception as e:
        logger.error(f"Error validating telegram init data: {e}")
        return None


def create_access_token(data: Dict[str, Any], expires_delta_seconds: Optional[int] = None) -> str:
    """JWT Access token yaratish"""
    to_encode = data.copy()
    expire_seconds = expires_delta_seconds or (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    expire_timestamp = int(time.time()) + expire_seconds
    to_encode.update({"exp": expire_timestamp})
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """JWT Access tokenni dekod qilish va tekshirish"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError as e:
        logger.warning(f"JWT decode error: {e}")
        return None
