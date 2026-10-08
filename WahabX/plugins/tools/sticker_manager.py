import asyncio
import json
import os
import random

from pyrogram import filters
from pyrogram.enums import ChatAction
from pyrogram.types import Message

import config
from WahabX import app

STICKER_FILE = os.path.join("tempdb", "com_e_girl_stickers.json")
PACK_FILE = os.path.join("tempdb", "com_e_girl_sticker_packs.json")

# This pack is fixed in code. No manual /savestickerpack command is needed.
PACK_SHORT_NAME = "zngetu_by_Making_Stickers_Bot"
PACK_LINK = "https://t.me/addstickers/zngetu_by_Making_Stickers_Bot"
MAX_STICKERS = 300

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
        json.dump(clean[:MAX_STICKERS], f, ensure_ascii=False)


def _save_pack_name(pack_name=PACK_SHORT_NAME):
    os.makedirs(os.path.dirname(PACK_FILE), exist_ok=True)
    with open(PACK_FILE, "w", encoding="utf-8") as f:
        json.dump([pack_name], f, ensure_ascii=False)


def _clear_old_saved_stickers():
    # Remove every old/manual sticker list before loading the new fixed pack.
    for path in (STICKER_FILE, PACK_FILE):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"[STICKER] old data cleanup failed: {type(e).__name__}: {e}")


def random_sticker():
    items = _load()
    return random.choice(items) if items else None


async def _show_sticker_choosing(client, chat_id):
    try:
        # Telegram displays "choosing a sticker" while the bot is selecting one.
        await client.send_chat_action(chat_id, ChatAction.CHOOSE_STICKER)
        await asyncio.sleep(0.8)
    except Exception:
        pass


async def preload_fixed_sticker_pack(client):
    """
    Clear all old saved sticker data and automatically load the complete
    configured public sticker pack from Telegram. This runs once at startup.
    """
    async with _SAVE_LOCK:
        _clear_old_saved_stickers()

        try:
            sticker_set = await client.get_sticker_set(PACK_SHORT_NAME)
            stickers = list(getattr(sticker_set, "stickers", None) or [])

            file_ids = []
            for sticker in stickers:
                file_id = getattr(sticker, "file_id", None)
                if file_id:
                    file_ids.append(file_id)
                if len(file_ids) >= MAX_STICKERS:
                    break

            if not file_ids:
                raise RuntimeError("Telegram returned the pack but no usable file_ids")

            _save(file_ids)
            _save_pack_name(PACK_SHORT_NAME)
            print(
                f"[STICKER] Auto-loaded {len(file_ids)} stickers from "
                f"{PACK_LINK}"
            )
            return len(file_ids)

        except Exception as e:
            print(
                f"[STICKER] Auto-load failed for {PACK_LINK}: "
                f"{type(e).__name__}: {e}"
            )
            return 0


async def send_random_sticker(message: Message, probability: float = 0.12):
    if random.random() > probability:
        return False

    sticker = random_sticker()
    if not sticker:
        return False

    try:
        await _show_sticker_choosing(message._client, message.chat.id)
        await message.reply_sticker(
            sticker,
            reply_to_message_id=message.id,
            quote=True,
        )
        return True
    except Exception as e:
        print(f"[STICKER] random sticker failed: {type(e).__name__}: {e}")
        return False


@app.on_message(filters.sticker & ~filters.service)
async def sticker_reply_handler(client, message: Message):
    """
    Reply with a random sticker from the fixed pack whenever a user replies
    to ANY sticker. We intentionally do not require set_name/file_id matching
    because Telegram/Pyrogram can omit or change those fields.
    """
    if not message.from_user or message.from_user.is_bot:
        return

    replied = message.reply_to_message
    if not replied or not replied.sticker:
        return

    saved = _load()
    if not saved:
        print("[STICKER] Reply ignored: saved sticker pack is empty")
        return

    replied_file_id = getattr(replied.sticker, "file_id", None)
    choices = [x for x in saved if x != replied_file_id] or saved
    chosen = random.choice(choices)

    try:
        await _show_sticker_choosing(client, message.chat.id)
        await message.reply_sticker(chosen, quote=True)
        print("[STICKER] Replied to sticker with saved pack sticker")
    except Exception as e:
        print(f"[STICKER] sticker reply failed: {type(e).__name__}: {e}")




# Kept only as a harmless compatibility command. The pack itself is now
# automatic and fixed, so users never need to manually save stickers.
@app.on_message(filters.command(["sticker", "savestickerpack"]))
async def sticker_manager_compat(client, message: Message):
    if not message.from_user or message.from_user.id not in config.OWNER_ID:
        return

    command_key = (message.chat.id, message.id)
    if command_key in _PROCESSED_COMMANDS:
        return
    _PROCESSED_COMMANDS.add(command_key)

    await message.reply_text(
        "Sticker pack automatic hai 💗\n"
        f"Pack: {PACK_LINK}\n"
        "Bot startup par purane saved stickers delete karke poora pack khud load karta hai."
    )


__MODULE__ = "Sᴛɪᴄᴋᴇʀ Pᴀᴄᴋ Mᴀɴᴀɢᴇʀ"
__HELP__ = """
**Sticker Pack Manager:**
• Fixed pack automatically loads at startup.
• Old/manual saved sticker data is deleted first.
• Maximum 300 stickers are kept.
• Replying to a sticker from the configured pack makes the bot reply with another saved sticker.
• Telegram shows the "choosing a sticker" action before the sticker is sent.
• Sticker saving commands are no longer required.
"""
