import json
import os
import random

from pyrogram import filters
from pyrogram.types import Message

import config
from WahabX import app

STICKER_FILE = os.path.join("tempdb", "com_e_girl_stickers.json")
MAX_STICKERS = 300


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
        json.dump(list(dict.fromkeys(items))[-MAX_STICKERS:], f)


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


@app.on_message(filters.command(["sticker", "savestickerpack"]) & filters.group)
async def sticker_manager(client, message: Message):
    if not message.from_user or message.from_user.id not in config.OWNER_ID:
        return

    args = (message.text or "").split(maxsplit=1)
    command_name = (message.command[0] if message.command else "").lower()
    action = args[1].strip().lower() if len(args) > 1 else ""

    target = message.reply_to_message
    if not target or not target.sticker:
        await message.reply_text("Sticker ko reply karke /savestickerpack karo 💗")
        return

    if command_name == "sticker" and action not in ("save", "pack"):
        await message.reply_text(
            "Use: sticker ko reply karke /sticker save ya /savestickerpack 💗"
        )
        return

    sticker = target.sticker
    items = _load()
    before = len(items)
    pack_name = getattr(sticker, "set_name", None)

    if pack_name:
        try:
            sticker_set = await client.get_sticker_set(pack_name)
            for item in getattr(sticker_set, "stickers", []) or []:
                file_id = getattr(item, "file_id", None)
                if file_id and file_id not in items:
                    items.append(file_id)
                    if len(items) >= MAX_STICKERS:
                        break
        except Exception as e:
            print(f"[STICKER] pack load failed: {type(e).__name__}: {e}")

    file_id = sticker.file_id
    if file_id not in items and len(items) < MAX_STICKERS:
        items.append(file_id)

    _save(items)
    final_items = _load()
    added = max(0, len(final_items) - before)
    pack_text = f"Pack: {pack_name}" if pack_name else "Single sticker"
    await message.reply_text(
        f"Sticker save ho gaye 💗\n{pack_text}\nNew: {added}\nTotal: {len(final_items)}/{MAX_STICKERS}"
    )


__MODULE__ = "Sᴛɪᴄᴋᴇʀ Pᴀᴄᴋ Mᴀɴᴀɢᴇʀ"
__HELP__ = """
**Sticker Pack Manager:**
• Owner sticker ko reply karke /savestickerpack use kare.
• Agar sticker Telegram pack ka hai to pack ke stickers save honge.
• COM E GIRLE kabhi-kabhi apne message ke direct reply par saved pack se random sticker bhejegi.
• Maximum 300 sticker file IDs local tempdb mein rakhe jaate hain.
"""
