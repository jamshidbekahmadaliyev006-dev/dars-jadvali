"""
Telegram bir nechta rasmni (albom) har birini alohida xabar qilib yuboradi, faqat ularda umumiy
media_group_id bo'ladi. Bu yordamchi albomning barcha rasmlarini yig'ib, bitta jadval sifatida
bir marta qayta ishlashga beradi.
"""
import asyncio
from typing import Dict, List, Optional
from aiogram.types import Message

ALBUM_WAIT_SECONDS = 1.5
MAX_ALBUM_FILES = 10
_ALBUMS: Dict[str, List[str]] = {}


async def collect_album(message: Message, file_id: str) -> Optional[List[str]]:
    """
    Albomsiz rasm: [file_id] darhol qaytadi.
    Albom: birinchi xabar qolganlarini kutadi va hammasini qaytaradi; keyingi xabarlar None qaytaradi
    (ular birinchisiga qo'shildi, alohida qayta ishlanmaydi).
    """
    group_id = getattr(message, "media_group_id", None)
    if not group_id:
        return [file_id]

    key = f"{message.chat.id}:{group_id}"
    if key in _ALBUMS:
        if len(_ALBUMS[key]) < MAX_ALBUM_FILES:
            _ALBUMS[key].append(file_id)
        return None

    _ALBUMS[key] = [file_id]
    await asyncio.sleep(ALBUM_WAIT_SECONDS)
    return _ALBUMS.pop(key, [file_id])
