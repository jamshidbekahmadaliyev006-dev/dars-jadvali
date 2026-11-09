"""
Eski bot uchun yo'naltiruvchi: unga kim nima yozsa (yoki tugma bossa), yangi botga o'tish
haqida xabar va tugma bilan javob beradi. Asosiy bot bilan bir vaqtda alohida jarayon sifatida ishlaydi.

Ishga tushirish:
    OLD_BOT_TOKEN=... NEW_BOT_USERNAME=qulayjadval_bot python scripts/old_bot_redirect.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

TOKEN = os.environ.get("OLD_BOT_TOKEN", "").strip()
NEW_BOT = os.environ.get("NEW_BOT_USERNAME", "qulayjadval_bot").strip().lstrip("@")
API = f"https://api.telegram.org/bot{TOKEN}"

TEXT = {
    "uz": (
        "📢 <b>Bot yangi manzilga ko'chdi!</b>\n\n"
        f"Dars jadvali va eslatmalar endi shu botda: @{NEW_BOT}\n\n"
        "Ma'lumotlaringiz saqlangan - yangi botga o'tib <b>/start</b> bosing."
    ),
    "ru": (
        "📢 <b>Бот переехал!</b>\n\n"
        f"Расписание и напоминания теперь здесь: @{NEW_BOT}\n\n"
        "Ваши данные сохранены - перейдите в новый бот и нажмите <b>/start</b>."
    ),
}
BUTTON = {"uz": "➡️ Yangi botga o'tish", "ru": "➡️ Перейти в новый бот"}


def call(method: str, payload: dict, timeout: int = 40) -> dict:
    req = urllib.request.Request(
        f"{API}/{method}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res)


def reply(chat_id: int, lang_code: str) -> None:
    lang = "ru" if (lang_code or "").lower().startswith("ru") else "uz"
    call("sendMessage", {
        "chat_id": chat_id,
        "text": TEXT[lang],
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": [[{"text": BUTTON[lang], "url": f"https://t.me/{NEW_BOT}?start=moved"}]]},
    })


def main() -> None:
    if not TOKEN:
        sys.exit("OLD_BOT_TOKEN berilmagan")
    print(f"Eski bot yo'naltiruvchisi ishga tushdi -> @{NEW_BOT}", flush=True)
    offset = None
    while True:
        try:
            payload = {"timeout": 30, "allowed_updates": ["message", "callback_query"]}
            if offset:
                payload["offset"] = offset
            updates = call("getUpdates", payload, timeout=45).get("result", [])
            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message")
                cq = upd.get("callback_query")
                try:
                    if msg and msg.get("chat", {}).get("type") == "private":
                        reply(msg["chat"]["id"], msg.get("from", {}).get("language_code"))
                    elif cq:
                        call("answerCallbackQuery", {"callback_query_id": cq["id"]})
                        reply(cq["from"]["id"], cq["from"].get("language_code"))
                    print(f"javob berildi: update {upd['update_id']}", flush=True)
                except urllib.error.HTTPError as e:
                    print(f"yuborilmadi: update {upd['update_id']} HTTP {e.code}", flush=True)
        except Exception as e:  # tarmoq uzilishi va h.k. - biroz kutib davom etamiz
            print(f"xato: {type(e).__name__}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
