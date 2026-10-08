import asyncio
import json
import os
import random

from pyrogram import filters, raw
from pyrogram.enums import ChatAction
from pyrogram.file_id import FileId, FileType
from pyrogram.types import Message

import config
from WahabX import app

STICKER_FILE = os.path.join("tempdb", "com_e_girl_stickers.json")
PACK_FILE = os.path.join("tempdb", "com_e_girl_sticker_packs.json")

PACK_SHORT_NAME = "zngetu_by_Making_Stickers_Bot"
PACK_LINK = "https://t.me/addstickers/zngetu_by_Making_Stickers_Bot"

# Sticker file_ids are tiny strings, so keep the whole public pack.
MAX_STICKERS = 5000

# User supplied a known-good sticker file_id; it is also a safety fallback if
# Telegram temporarily refuses the pack request.
SEED_STICKER_FILE_ID = "CAACAgUAAxkBAAESAqJqxxoSQJTiXVWHQfOeqLcGYd3nvgACHh8AAsZXYVSCyQOjLbwt-D0E"

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
    # Old manually saved packs must never remain mixed with the fixed pack.
    for path in (STICKER_FILE, PACK_FILE):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"[STICKER] old data cleanup failed: {type(e).__name__}: {e}")


def random_sticker():
    items = _load()
    return random.choice(items) if items else SEED_STICKER_FILE_ID


async def _show_sticker_choosing(client, chat_id):
    try:
        await client.send_chat_action(chat_id, ChatAction.CHOOSE_STICKER)
        await asyncio.sleep(0.55)
    except Exception:
        pass


def _document_to_sticker_file_id(document, sticker_set):
    """
    Telegram's raw GetStickerSet returns raw Document objects, which do not
    expose the high-level file_id property. Build the exact reusable Pyrogram
    sticker file_id from the document + sticker-set identifiers.
    """
    try:
        if not isinstance(document, raw.types.Document):
            return None

        return FileId(
            file_type=FileType.STICKER,
            dc_id=document.dc_id,
            media_id=document.id,
            access_hash=document.access_hash,
            file_reference=document.file_reference,
            sticker_set_id=sticker_set.id,
            sticker_set_access_hash=sticker_set.access_hash,
        ).encode()
    except Exception as e:
        print(f"[STICKER] file_id conversion failed: {type(e).__name__}: {e}")
        return None


async def _fetch_complete_pack_file_ids(client):
    result = await client.invoke(
        raw.functions.messages.GetStickerSet(
            stickerset=raw.types.InputStickerSetShortName(
                short_name=PACK_SHORT_NAME
            ),
            hash=0,
        )
    )

    sticker_set = getattr(result, "set", None)
    documents = list(getattr(result, "documents", None) or [])

    if not sticker_set:
        raise RuntimeError("Telegram returned no sticker-set metadata")
    if not documents:
        raise RuntimeError("Telegram returned no sticker documents")

    file_ids = []
    for document in documents:
        file_id = _document_to_sticker_file_id(document, sticker_set)
        if file_id:
            file_ids.append(file_id)

    file_ids = list(dict.fromkeys(file_ids))
    if not file_ids:
        raise RuntimeError("Could not convert any pack document into a sticker file_id")

    return file_ids


async def preload_fixed_sticker_pack(client):
    """
    On every startup:
      1. delete all old/manual sticker data;
      2. fetch every sticker document from the fixed Telegram pack;
      3. convert every raw document to a reusable sticker file_id;
      4. save the complete list for instant random replies.
    """
    async with _SAVE_LOCK:
        _clear_old_saved_stickers()

        try:
            file_ids = await _fetch_complete_pack_file_ids(client)
            _save(file_ids)
            _save_pack_name(PACK_SHORT_NAME)
            print(
                f"[STICKER] Auto-loaded complete pack: {len(file_ids)} stickers "
                f"from {PACK_LINK}"
            )
            return len(file_ids)

        except Exception as e:
            # Never leave the bot without a sticker. The supplied valid file_id
            # is kept as a one-sticker emergency fallback.
            _save([SEED_STICKER_FILE_ID])
            _save_pack_name(PACK_SHORT_NAME)
            print(
                f"[STICKER] Full pack fetch failed: {type(e).__name__}: {e}. "
                "Using the supplied fallback sticker."
            )
            return 1


async def send_random_sticker(message: Message, probability: float = 0.12):
    if random.random() > probability:
        return False

    sticker = random_sticker()
    if not sticker:
        return False

    try:
        await _show_sticker_choosing(message._client, message.chat.id)
        await message.reply_sticker(sticker, quote=True)
        return True
    except Exception as e:
        print(f"[STICKER] random sticker failed: {type(e).__name__}: {e}")
        return False


@app.on_message(filters.sticker & ~filters.service)
async def sticker_reply_handler(client, message: Message):
    """
    Whenever a user sends a sticker as a reply to another sticker, reply with
    a different random sticker from the fixed pack. No set_name/file_id
    matching is required, so stickers from Telegram's UI also work.
    """
    if not message.from_user or message.from_user.is_bot:
        return

    replied = message.reply_to_message
    if not replied or not replied.sticker:
        return

    saved = _load()
    if not saved:
        return

    replied_file_id = getattr(replied.sticker, "file_id", None)
    choices = [x for x in saved if x != replied_file_id] or saved
    chosen = random.choice(choices)

    try:
        await _show_sticker_choosing(client, message.chat.id)
        await message.reply_sticker(chosen, quote=True)
        print("[STICKER] Sticker-to-sticker random reply sent")
    except Exception as e:
        print(f"[STICKER] sticker reply failed: {type(e).__name__}: {e}")


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
        "Startup par purane stickers delete hoke poora pack automatically fetch hota hai."
    )


__MODULE__ = "Sᴛɪᴄᴋᴇʀ Pᴀᴄᴋ Mᴀɴᴀɢᴇʀ"
__HELP__ = """
**Sticker Pack Manager:**
• Fixed pack automatically fetches at startup.
• Old/manual sticker data is deleted first.
• Every pack sticker is converted to a reusable Telegram file_id.
• Replying to a sticker with a sticker makes the bot send another random pack sticker.
• Telegram shows "choosing a sticker" while selecting the reply.
• No manual sticker saving is required.
"""
