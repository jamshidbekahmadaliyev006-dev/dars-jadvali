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


_URL_PREFIX = "tg://file/"
_URL_LIMIT = 500  # schedule_submissions.image_url ustuni uzunligi


def pack_file_ids(file_ids: List[str]) -> str:
    """image_url uchun: faqat to'liq sig'adigan file_id'lar (kesilgan id buzuq bo'lardi)"""
    packed = ""
    for fid in file_ids:
        piece = _URL_PREFIX + fid
        candidate = f"{packed},{piece}" if packed else piece
        if len(candidate) > _URL_LIMIT:
            break
        packed = candidate
    return packed


def unpack_file_ids(image_url: Optional[str], fallback: Optional[str] = None) -> List[str]:
    ids = [p[len(_URL_PREFIX):] for p in (image_url or "").split(",") if p.startswith(_URL_PREFIX)]
    if not ids and fallback and fallback != "text" and not fallback.startswith("file_"):
        ids = [fallback]
    return ids


async def send_submission_files(bot, chat_id: int, file_ids: List[str], caption: str, as_document: bool = False) -> None:
    """Bir nechta rasm/faylni bitta albom qilib yuboradi (sarlavha birinchisida)"""
    from aiogram.types import InputMediaDocument, InputMediaPhoto

    media_cls = InputMediaDocument if as_document else InputMediaPhoto
    media = [
        media_cls(media=fid, caption=caption if index == 0 else None, parse_mode="HTML" if index == 0 else None)
        for index, fid in enumerate(file_ids[:MAX_ALBUM_FILES])
    ]
    await bot.send_media_group(chat_id=chat_id, media=media)
