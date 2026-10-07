# Group management commands + new-member welcome.
import time
from collections import defaultdict

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatPermissions, Message

import config
from WahabX import app

_WARNINGS = defaultdict(lambda: defaultdict(int))

async def _is_admin(message):
    if not message.from_user:
        return False
    if message.from_user.id in config.OWNER_ID:
        return True
    try:
        m = await app.get_chat_member(message.chat.id, message.from_user.id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False

async def _target(message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if len(message.command) > 1:
        try:
            return await app.get_users(message.command[1])
        except Exception:
            return None
    return None

@app.on_message(filters.new_chat_members & filters.group)
async def welcome_new_members(client, message: Message):
    for user in message.new_chat_members:
        if user.is_bot:
            continue
        name = user.mention
        await message.reply_text(
            f"Welcome {name} 💗✨\nCOM E GIRLE 💋 yahan hai, enjoy karo aur music bajao 🎶"
        )

@app.on_message(filters.command(["ban", "kick", "mute", "unmute", "unban", "promote", "demote", "warn"]) & filters.group)
async def group_management(client, message: Message):
    if not await _is_admin(message):
        return
    target = await _target(message)
    if not target:
        return await message.reply_text("Reply karo jis member par action chahiye 💗")
    if target.id in config.OWNER_ID:
        return await message.reply_text("Ye mere owner hain 😌 inko touch nahi kar sakti 💋")
    try:
        command = message.command[0].lower()
        if command == "ban":
            await app.ban_chat_member(message.chat.id, target.id)
            return await message.reply_text(f"🚫 {target.mention} ban kar diya.")
        if command == "unban":
            await app.unban_chat_member(message.chat.id, target.id)
            return await message.reply_text(f"♻️ {target.mention} unban ho gaya.")
        if command == "kick":
            await app.ban_chat_member(message.chat.id, target.id)
            await app.unban_chat_member(message.chat.id, target.id)
            return await message.reply_text(f"👢 {target.mention} kick kar diya.")
        if command == "mute":
            await app.restrict_chat_member(
                message.chat.id, target.id, ChatPermissions(can_send_messages=False)
            )
            return await message.reply_text(f"🔇 {target.mention} mute ho gaya.")
        if command == "unmute":
            await app.restrict_chat_member(
                message.chat.id, target.id, ChatPermissions(can_send_messages=True)
            )
            return await message.reply_text(f"🔊 {target.mention} unmute ho gaya.")
        if command == "promote":
            await app.promote_chat_member(
                message.chat.id, target.id, can_manage_chat=True, can_delete_messages=True,
                can_restrict_members=True, can_invite_users=True, can_pin_messages=True,
            )
            return await message.reply_text(f"⬆️ {target.mention} promote ho gaya.")
        if command == "demote":
            await app.promote_chat_member(
                message.chat.id, target.id, is_anonymous=False, can_manage_chat=False,
                can_delete_messages=False, can_restrict_members=False, can_invite_users=False,
                can_pin_messages=False,
            )
            return await message.reply_text(f"⬇️ {target.mention} demote ho gaya.")
        if command == "warn":
            _WARNINGS[message.chat.id][target.id] += 1
            count = _WARNINGS[message.chat.id][target.id]
            if count >= 3:
                await app.ban_chat_member(message.chat.id, target.id)
                _WARNINGS[message.chat.id][target.id] = 0
                return await message.reply_text(f"⚠️ 3 warnings complete — {target.mention} banned.")
            return await message.reply_text(f"⚠️ {target.mention} warning {count}/3.")
    except Exception as e:
        return await message.reply_text(f"❌ Action nahi ho saka: {str(e)[:120]}")

__MODULE__ = "Gʀᴏᴜᴘ Mᴀɴᴀɢᴇᴍᴇɴᴛ"
__HELP__ = """
**Gʀᴏᴜᴘ Mᴀɴᴀɢᴇᴍᴇɴᴛ:**
• /ban /unban /kick
• /mute /unmute
• /promote /demote
• /warn — 3 warnings par ban
• New members ko automatic welcome
• Commands reply karke ya username ke saath use ho sakti hain.
"""
