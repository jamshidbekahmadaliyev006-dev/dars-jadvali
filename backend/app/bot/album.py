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


def image_size(data: bytes):
    """(kenglik, balandlik) yoki None. PNG, JPEG va WEBP sarlavhasidan o'qiladi - rasm to'liq ochilmaydi."""
    import struct

    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", data[16:24])
        if data[:2] == b"\xff\xd8":
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return w, h
                i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            if data[12:16] == b"VP8X":
                return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
            if data[12:16] == b"VP8 ":
                w, h = struct.unpack("<HH", data[26:30])
                return w & 0x3FFF, h & 0x3FFF
    except Exception:
        return None
    return None


MIN_SIDE_FOR_SMALL_TEXT = 650  # qisqa tomoni shundan kichik rasmda mayda yozuvlar (xona, vaqt) ko'pincha xato o'qiladi


def looks_too_small(images) -> bool:
    for data in images:
        size = image_size(data)
        if size and min(size) < MIN_SIDE_FOR_SMALL_TEXT:
            return True
    return False


MIN_PX_PER_DAY = 150  # bir kun ustuniga shuncha pikseldan kam tushsa, yozuv (xona, vaqt) ishonchli o'qilmaydi
MIN_DAYS_FOR_RULE = 3  # qoida faqat ko'p kunli (butun hafta) rasmga qo'llanadi: 1-2 kunlik kattalashtirilgan rasm normal


def too_small_for_lessons(image: bytes, lessons) -> bool:
    """
    Bitta rasm uchun: kengligi / o'qilgan kunlar soni. 576 px kenglikka 5 kun sig'sa (115 px/kun) matn 9-10 px bo'ladi -
    xira. Aniq rasmda 200+ px/kun. O'lcham bilib bo'lmasa yoki kunlar kam bo'lsa - rad etilmaydi.
    """
    from app.services.schedule_service import resolve_day_of_week

    size = image_size(image)
    days = {resolve_day_of_week(item.get("day")) for item in lessons}
    days.discard(None)
    if not size or len(days) < MIN_DAYS_FOR_RULE:
        return False
    return min(size) / len(days) < MIN_PX_PER_DAY if size[0] <= size[1] else size[0] / len(days) < MIN_PX_PER_DAY
