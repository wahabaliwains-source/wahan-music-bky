# Reliable group management commands + new-member welcome.
from collections import defaultdict

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatPermissions, Message

import config
from WahabX import app

_WARNINGS = defaultdict(lambda: defaultdict(int))


def _is_owner(user_id: int) -> bool:
    return user_id in config.OWNER_ID


async def _is_admin(message: Message) -> bool:
    if not message.from_user:
        return False
    if _is_owner(message.from_user.id):
        return True
    try:
        member = await app.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        return False


async def _bot_is_admin(message: Message) -> bool:
    try:
        member = await app.get_chat_member(message.chat.id, "me")
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        return False


async def _target(message: Message):
    # Reply target has priority.
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user

    if len(message.command) > 1:
        value = message.command[1].strip()
        # Support /ban @username and /ban user_id.
        try:
            return await app.get_users(value)
        except Exception:
            try:
                return await app.get_users(int(value))
            except Exception:
                return None
    return None


def _full_permissions():
    return ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
    )


@app.on_message(filters.new_chat_members & filters.group)
async def welcome_new_members(client, message: Message):
    for user in message.new_chat_members:
        if user.is_bot:
            continue
        try:
            await message.reply_text(
                f"Welcome {user.mention} 💗✨\n"
                "COM E GIRLE 💋 yahan hai, enjoy karo aur music bajao 🎶"
            )
        except Exception as e:
            print(f"[GROUP] Welcome failed: {type(e).__name__}: {e}")


@app.on_message(
    filters.command(
        [
            "ban", "unban", "kick", "mute", "unmute",
            "promote", "demote", "warn", "unwarn",
            "del", "delete", "purge",
        ]
    )
    & filters.group
)
async def group_management(client, message: Message):
    if not await _is_admin(message):
        return

    command = message.command[0].lower()

    # Delete/purge are handled before target lookup.
    if command in ("del", "delete"):
        if not message.reply_to_message:
            return await message.reply_text("Reply karo jis message ko delete karna hai 💗")
        if not await _bot_is_admin(message):
            return await message.reply_text("❌ Pehle mujhe group mein admin banao.")
        try:
            await message.reply_to_message.delete()
            await message.delete()
        except Exception as e:
            await message.reply_text(f"❌ Delete nahi ho saka: {str(e)[:120]}")
        return

    if command == "purge":
        if not await _bot_is_admin(message):
            return await message.reply_text("❌ Pehle mujhe group mein admin banao.")
        if not message.reply_to_message:
            return await message.reply_text("Purge ke liye pehle message par reply karo 💗")
        try:
            chat_id = message.chat.id
            start_id = message.reply_to_message.id
            end_id = message.id
            ids = list(range(start_id, end_id + 1))
            await app.delete_messages(chat_id, ids, revoke=True)
        except Exception as e:
            return await message.reply_text(f"❌ Purge nahi ho saka: {str(e)[:120]}")
        return

    target = await _target(message)
    if not target:
        return await message.reply_text(
            "Reply karo member ke message par, ya username/ID do 💗"
        )

    if target.id in config.OWNER_ID:
        return await message.reply_text(
            "Ye mere owner hain 😌 inko touch nahi kar sakti 💋"
        )

    # Never let the bot try to moderate itself.
    try:
        me = await app.get_me()
        if target.id == me.id:
            return await message.reply_text("Mujhe khud par ye action nahi karna 😭")
    except Exception:
        pass

    if not await _bot_is_admin(message):
        return await message.reply_text("❌ Pehle mujhe group mein admin banao.")

    try:
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
                message.chat.id,
                target.id,
                permissions=ChatPermissions(can_send_messages=False),
            )
            return await message.reply_text(f"🔇 {target.mention} mute ho gaya.")

        if command == "unmute":
            await app.restrict_chat_member(
                message.chat.id,
                target.id,
                permissions=_full_permissions(),
            )
            return await message.reply_text(f"🔊 {target.mention} unmute ho gaya.")

        if command == "promote":
            await app.promote_chat_member(
                message.chat.id,
                target.id,
                can_manage_chat=True,
                can_delete_messages=True,
                can_restrict_members=True,
                can_invite_users=True,
                can_pin_messages=True,
                can_manage_video_chats=True,
            )
            return await message.reply_text(f"⬆️ {target.mention} promote ho gaya.")

        if command == "demote":
            await app.promote_chat_member(
                message.chat.id,
                target.id,
                is_anonymous=False,
                can_manage_chat=False,
                can_delete_messages=False,
                can_restrict_members=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_manage_video_chats=False,
            )
            return await message.reply_text(f"⬇️ {target.mention} demote ho gaya.")

        if command == "warn":
            _WARNINGS[message.chat.id][target.id] += 1
            count = _WARNINGS[message.chat.id][target.id]
            if count >= 3:
                await app.ban_chat_member(message.chat.id, target.id)
                _WARNINGS[message.chat.id][target.id] = 0
                return await message.reply_text(
                    f"⚠️ 3 warnings complete — {target.mention} banned."
                )
            return await message.reply_text(
                f"⚠️ {target.mention} warning {count}/3."
            )

        if command == "unwarn":
            _WARNINGS[message.chat.id][target.id] = 0
            return await message.reply_text(
                f"✅ {target.mention} ki warnings reset kar di."
            )

    except Exception as e:
        return await message.reply_text(
            f"❌ Action nahi ho saka: {type(e).__name__}: {str(e)[:160]}"
        )


__MODULE__ = "Gʀᴏᴜᴘ Mᴀɴᴀɢᴇᴍᴇɴᴛ"
__HELP__ = """
**Gʀᴏᴜᴘ Mᴀɴᴀɢᴇᴍᴇɴᴛ:**
• /ban /unban /kick
• /mute /unmute
• /promote /demote
• /warn /unwarn — 3 warnings par ban
• /del /delete — replied message delete
• /purge — replied message se current message tak delete
• Reply karke ya /command @username / user_id se target select karo.
• Bot ko group mein required admin permissions dena zaroori hai.
• New members ko automatic welcome.
"""
