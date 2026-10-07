import json
import os
import random
from pyrogram import filters
from pyrogram.types import Message
import config
from WahabX import app

STICKER_FILE = os.path.join("tempdb", "com_e_girl_stickers.json")

def _load():
    try:
        os.makedirs(os.path.dirname(STICKER_FILE), exist_ok=True)
        if not os.path.exists(STICKER_FILE):
            return []
        with open(STICKER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return list(dict.fromkeys(x for x in data if isinstance(x, str) and x))
    except Exception:
        return []

def _save(items):
    os.makedirs(os.path.dirname(STICKER_FILE), exist_ok=True)
    with open(STICKER_FILE, "w", encoding="utf-8") as f:
        json.dump(items[-300:], f)

def random_sticker():
    items = _load()
    return random.choice(items) if items else None

async def send_random_sticker(message: Message, probability: float = 0.12):
    if random.random() > probability:
        return False
    sticker = random_sticker()
    if not sticker:
        return False
    try:
        await message.reply_sticker(sticker, quote=True)
        return True
    except Exception:
        return False

@app.on_message(filters.command("sticker") & filters.group)
async def sticker_manager(client, message: Message):
    if not message.from_user or message.from_user.id not in config.OWNER_ID:
        return
    if message.chat.id != config.LOGGER_ID:
        return

    args = (message.text or "").split(maxsplit=1)
    action = args[1].strip().lower() if len(args) > 1 else ""
    if action != "save":
        await message.reply_text("Use: /sticker save — sticker ko reply karke 💗")
        return

    target = message.reply_to_message
    if not target or not target.sticker:
        await message.reply_text("Sticker message ko reply karke /sticker save karo 💗")
        return

    items = _load()
    file_id = target.sticker.file_id
    if file_id not in items:
        items.append(file_id)
        _save(items)
    await message.reply_text(f"Sticker save ho gaya 💗\nSaved stickers: {len(items)}")

__MODULE__ = "Sᴛɪᴄᴋᴇʀ Mᴀɴᴀɢᴇʀ"
__HELP__ = """
**Sticker Manager:**
• Owner can reply to a sticker in LOGGER_ID and use /sticker save.
• COM E GIRLE kabhi-kabhi saved stickers reply mein bhejegi.
• Stickers local file IDs ke through save hote hain; bot koi sticker pack create nahi karta.
"""
