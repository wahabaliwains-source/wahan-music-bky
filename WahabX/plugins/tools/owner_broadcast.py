import asyncio

from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message

import config
from WahabX import app
from WahabX.utils.database import get_served_chats, get_served_users


async def _send_one(target_id, source_message, text, pin_mode):
    try:
        if source_message is not None:
            sent = await app.copy_message(
                target_id,
                source_message.chat.id,
                source_message.id,
            )
        else:
            sent = await app.send_message(target_id, text)

        if pin_mode and sent:
            try:
                await app.pin_chat_message(
                    target_id,
                    sent.id,
                    disable_notification=(pin_mode == "pin"),
                )
            except Exception:
                pass
        return True
    except FloodWait as e:
        await asyncio.sleep(int(e.value))
        return await _send_one(target_id, source_message, text, pin_mode)
    except Exception:
        return False


@app.on_message(filters.command(["broadcast", "gcast"]))
async def owner_broadcast(client, message: Message):
    # Broadcast is OWNER ONLY. Sudo/admin users cannot use it.
    if not message.from_user or message.from_user.id not in config.OWNER_ID:
        return

    args = list(message.command[1:]) if message.command else []
    pin_mode = None
    user_mode = False

    while args and args[0].lower() in ("-pin", "-pinloud", "-user", "-nobot"):
        option = args.pop(0).lower()
        if option in ("-pin", "-pinloud"):
            pin_mode = option[1:]
        elif option == "-user":
            user_mode = True

    source_message = message.reply_to_message
    text = " ".join(args).strip()

    if not source_message and not text:
        return await message.reply_text(
            "Use: /broadcast message\n"
            "Ya kisi message ko reply karke /broadcast karo 💗\n\n"
            "Options: -user -pin -pinloud -nobot"
        )

    status = await message.reply_text(
        "📣 Broadcast start ho raha hai...\n"
        "👑 Sirf owner is command ko use kar sakta hai."
    )

    try:
        if user_mode:
            targets = await get_served_users()
            target_ids = [
                int(item["user_id"])
                for item in targets
                if isinstance(item, dict) and item.get("user_id")
            ]
            target_label = "users"
        else:
            targets = await get_served_chats()
            target_ids = [
                int(item["chat_id"])
                for item in targets
                if isinstance(item, dict) and item.get("chat_id")
            ]
            target_label = "groups"
    except Exception as e:
        return await status.edit_text(
            f"❌ Broadcast database load failed: {type(e).__name__}"
        )

    success = 0
    failed = 0

    for target_id in target_ids:
        if await _send_one(target_id, source_message, text, pin_mode):
            success += 1
        else:
            failed += 1

    await status.edit_text(
        "📣 Broadcast complete 💗\n"
        f"Target: {target_label}\n"
        f"✅ Sent: {success}\n"
        f"❌ Failed: {failed}"
    )


__MODULE__ = "Oᴡɴᴇʀ Bʀᴏᴀᴅᴄᴀsᴛ"
__HELP__ = """
**Owner Broadcast:**
• /broadcast message — groups mein broadcast.
• /gcast message — groups mein broadcast.
• /broadcast -user message — started users ko broadcast.
• Message ko reply karke /broadcast bhi use kar sakte ho.
• -pin / -pinloud supported.
• Broadcast commands OWNER ONLY hain.
"""
