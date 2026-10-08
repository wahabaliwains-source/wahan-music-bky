import asyncio
import json
import os
import random

from pyrogram import filters
from pyrogram.types import Message

import config
from WahabX import app

STICKER_FILE = os.path.join("tempdb", "com_e_girl_stickers.json")
MAX_STICKERS = 300

# Prevent two sticker-save commands from running at the same time.
_SAVE_LOCK = asyncio.Lock()
_PROCESSED_COMMANDS = set()


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
        json.dump(clean[-MAX_STICKERS:], f, ensure_ascii=False)


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
    # Best case: command is a direct reply to the sticker.
    target = message.reply_to_message
    if target and target.sticker:
        return target

    # Also support: sticker sent first, then /savestickerpack separately.
    # Search recent history for the owner's latest sticker.
    try:
        async for item in client.get_chat_history(message.chat.id, limit=100):
            if item.id >= message.id:
                continue
            if not item.sticker:
                continue
            if item.from_user and message.from_user:
                if item.from_user.id == message.from_user.id:
                    return item
    except Exception as e:
        print(f"[STICKER] history lookup failed: {type(e).__name__}: {e}")

    return None


@app.on_message(filters.sticker & ~filters.service)
async def sticker_reply_handler(client, message: Message):
    # Never react to our own sticker messages; this prevents a sticker loop.
    if not message.from_user or message.from_user.is_bot:
        return

    replied = message.reply_to_message
    if not replied or not replied.sticker:
        return

    # Only stickers that were actually saved in our pack are triggers.
    saved = _load()
    replied_file_id = getattr(replied.sticker, "file_id", None)
    if not replied_file_id or replied_file_id not in saved:
        return

    # Pick one saved sticker and reply to the user's sticker.
    chosen = random.choice(saved)
    try:
        await message.reply_sticker(chosen, quote=True)
    except Exception as e:
        print(f"[STICKER] reply failed: {type(e).__name__}: {e}")


@app.on_message(filters.command(["sticker", "savestickerpack"]))
async def sticker_manager(client, message: Message):
    # OWNER ONLY. No sudo/admin user can save or modify the pack.
    if not message.from_user or message.from_user.id not in config.OWNER_ID:
        return

    # Never process the same Telegram command twice.
    command_key = (message.chat.id, message.id)
    if command_key in _PROCESSED_COMMANDS:
        return
    _PROCESSED_COMMANDS.add(command_key)
    if len(_PROCESSED_COMMANDS) > 500:
        _PROCESSED_COMMANDS.clear()
        _PROCESSED_COMMANDS.add(command_key)

    async with _SAVE_LOCK:
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
                pack_stickers = getattr(sticker_set, "stickers", None) or []

                for item in pack_stickers:
                    file_id = getattr(item, "file_id", None)
                    if file_id and file_id not in items:
                        items.append(file_id)
                    if len(items) >= MAX_STICKERS:
                        break

                pack_loaded = bool(pack_stickers)
            except Exception as e:
                print(f"[STICKER] pack load failed: {type(e).__name__}: {e}")

        # Always save at least the sticker used with the command.
        file_id = getattr(sticker, "file_id", None)
        if file_id and file_id not in items and len(items) < MAX_STICKERS:
            items.append(file_id)

        _save(items)
        final_items = _load()
        added = max(0, len(final_items) - before)

        if pack_name and pack_loaded:
            pack_text = f"Pack: {pack_name}"
        elif pack_name:
            pack_text = f"Pack: {pack_name} (single sticker saved)"
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
• Pack available ho to maximum 300 stickers save honge.
• Same command dobara process nahi hoga, isliye save/reply loop nahi banega.
• COM E GIRLE saved pack se kabhi-kabhi random sticker bhejegi.
• Sticker save commands OWNER ONLY hain.
"""
