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
        if not isinstance(data, list):
            return []
        return list(dict.fromkeys(x for x in data if isinstance(x, str) and x))
    except Exception:
        return []


def _save(items):
    os.makedirs(os.path.dirname(STICKER_FILE), exist_ok=True)
    clean = list(dict.fromkeys(x for x in items if isinstance(x, str) and x))
    with open(STICKER_FILE, "w", encoding="utf-8") as f:
        json.dump(clean[-MAX_STICKERS:], f)


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


async def _find_sticker_target(client, message: Message):
    # Normal/recommended usage: reply directly to the sticker.
    target = message.reply_to_message
    if target and target.sticker:
        return target

    # Also support the flow shown by the owner: send a sticker, then
    # send /savestickerpack as a separate message. Pick the latest sticker
    # sent by the owner before this command.
    try:
        async for item in client.get_chat_history(message.chat.id, limit=30):
            if item.id >= message.id:
                continue
            if not item.sticker:
                continue
            if item.from_user and item.from_user.id == message.from_user.id:
                return item
    except Exception as e:
        print(f"[STICKER] history lookup failed: {type(e).__name__}: {e}")

    return None


@app.on_message(filters.command(["sticker", "savestickerpack"]))
async def sticker_manager(client, message: Message):
    # Sticker management is OWNER ONLY.
    if not message.from_user or message.from_user.id not in config.OWNER_ID:
        return

    args = (message.text or "").split(maxsplit=1)
    command_name = (message.command[0] if message.command else "").lower()
    action = args[1].strip().lower() if len(args) > 1 else ""

    if command_name == "sticker" and action not in ("save", "pack"):
        await message.reply_text(
            "Sticker ko reply karke /sticker save ya /savestickerpack karo 💗"
        )
        return

    target = await _find_sticker_target(client, message)
    if not target or not target.sticker:
        await message.reply_text(
            "Pehle sticker bhejo, phir /savestickerpack karo 💗\n"
            "Ya sticker ko reply karke command bhejo."
        )
        return

    sticker = target.sticker
    items = _load()
    before = len(items)
    pack_name = getattr(sticker, "set_name", None)
    pack_loaded = False

    if pack_name:
        try:
            sticker_set = await client.get_sticker_set(pack_name)
            for item in getattr(sticker_set, "stickers", []) or []:
                file_id = getattr(item, "file_id", None)
                if file_id and file_id not in items:
                    items.append(file_id)
                if len(items) >= MAX_STICKERS:
                    break
            pack_loaded = True
        except Exception as e:
            print(
                f"[STICKER] pack load failed: {type(e).__name__}: {e}"
            )

    # Always save the sticker that triggered the command, even if Telegram
    # does not let us fetch the whole pack.
    file_id = sticker.file_id
    if file_id and file_id not in items and len(items) < MAX_STICKERS:
        items.append(file_id)

    _save(items)
    final_items = _load()
    added = max(0, len(final_items) - before)

    if pack_name and pack_loaded:
        pack_text = f"Pack: {pack_name}"
    elif pack_name:
        pack_text = f"Pack: {pack_name} (fallback sticker saved)"
    else:
        pack_text = "Single sticker"

    await message.reply_text(
        f"Sticker save ho gaye 💗\n"
        f"{pack_text}\n"
        f"New: {added}\n"
        f"Total: {len(final_items)}/{MAX_STICKERS}"
    )


__MODULE__ = "Sᴛɪᴄᴋᴇʀ Pᴀᴄᴋ Mᴀɴᴀɢᴇʀ"
__HELP__ = """
**Sticker Pack Manager:**
• Owner sticker ko reply karke /savestickerpack use kare.
• Sticker bhej kar uske baad separate /savestickerpack bhi kaam karega.
• Telegram pack available ho to pack ke stickers save honge.
• COM E GIRLE kabhi-kabhi direct reply par saved pack se random sticker bhejegi.
• Maximum 300 sticker file IDs local tempdb mein rakhe jaate hain.
• Sticker save commands OWNER ONLY hain.
"""
