# Full group-management suite for WAHABX.
from collections import defaultdict
import re

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatPermissions, Message

import config
from WahabX import app

_WARNINGS = defaultdict(lambda: defaultdict(int))

COMMANDS = {
    "ban", "unban", "kick",
    "mute", "unmute",
    "lock", "unlock", "lockchat", "unlockchat",
    "warn", "unwarn",
    "del", "delete",
    "purge",
}

_COMMAND_RE = re.compile(r"^/([A-Za-z_]+)(?:@[\w_]+)?(?:\s+(.+))?$")


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


async def _bot_member(message: Message):
    try:
        me = await app.get_me()
        return await app.get_chat_member(message.chat.id, me.id)
    except Exception:
        return None


async def _bot_is_admin(message: Message) -> bool:
    member = await _bot_member(message)
    return bool(member and member.status in (
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    ))


async def _require_bot_restrict_rights(message: Message) -> bool:
    member = await _bot_member(message)
    if member and member.status == ChatMemberStatus.OWNER:
        return True
    privileges = getattr(member, "privileges", None) if member else None
    can_restrict = bool(
        getattr(member, "can_restrict_members", False)
        or getattr(privileges, "can_restrict_members", False)
    )
    if member and member.status == ChatMemberStatus.ADMINISTRATOR and can_restrict:
        return True
    await message.reply_text(
        "❌ Is command ke liye bot ko **Restrict Members** permission chahiye."
    )
    return False


async def _bot_is_owner(message: Message) -> bool:
    try:
        member = await app.get_chat_member(message.chat.id, "me")
        return member.status == ChatMemberStatus.OWNER
    except Exception:
        return False


async def _target(message: Message, argument: str | None = None):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user

    value = (argument or "").strip().split()[0] if argument else ""
    if not value:
        return None

    value = value.lstrip("@")
    try:
        return await app.get_users(value)
    except Exception:
        try:
            return await app.get_users(int(value))
        except Exception:
            return None


def _full_permissions():
    return ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
    )


async def _require_bot_admin(message: Message) -> bool:
    if await _bot_is_admin(message):
        return True
    await message.reply_text("❌ Mujhe group mein admin banao, phir ye command chalegi.")
    return False


@app.on_message(filters.new_chat_members & filters.group)
async def welcome_new_members(client, message: Message):
    for user in message.new_chat_members:
        if user.is_bot:
            continue
        try:
            await message.reply_text(
                f"Welcome {user.mention} 💗✨\n"
                "COM E GIRLE 💋 yahan hai — enjoy karo aur music bajao 🎶"
            )
        except Exception as e:
            print(f"[GROUP] Welcome failed: {type(e).__name__}: {e}")


@app.on_message(filters.text & filters.group, group=20)
async def group_management(client, message: Message):
    if not message.from_user or not message.text:
        return

    match = _COMMAND_RE.match(message.text.strip())
    if not match:
        return

    command = match.group(1).lower()
    argument = match.group(2)
    if command not in COMMANDS:
        return

    if not await _is_admin(message):
        return await message.reply_text("❌ Sirf group admins ye command use kar sakte hain.")

    if command in ("lock", "lockchat", "unlock", "unlockchat"):
        if not await _require_bot_restrict_rights(message):
            return
        locked = command in ("lock", "lockchat")
        try:
            if locked:
                permissions = ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_polls=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                )
                await app.set_chat_permissions(message.chat.id, permissions=permissions)
                return await message.reply_text(
                    "🔒 **Group locked!** Members ke messages/media temporarily band kar diye."
                )
            await app.set_chat_permissions(
                message.chat.id, permissions=_full_permissions()
            )
            return await message.reply_text(
                "🔓 **Group unlocked!** Members dobara messages bhej sakte hain."
            )
        except Exception as e:
            return await message.reply_text(
                f"❌ Group lock/unlock failed: {type(e).__name__}: {str(e)[:120]}"
            )

    if command in ("del", "delete"):
        if not await _require_bot_admin(message):
            return
        if not message.reply_to_message:
            return await message.reply_text("❌ `/del` ko kisi message par reply karke use karo.")
        try:
            await message.reply_to_message.delete()
            try:
                await message.delete()
            except Exception:
                pass
        except Exception as e:
            await message.reply_text(f"❌ Delete failed: {type(e).__name__}: {str(e)[:120]}")
        return

    if command == "purge":
        if not await _require_bot_admin(message):
            return
        try:
            count = 0
            if argument:
                count = max(1, min(int(argument.split()[0]), 100))
            if count:
                start = max(1, message.id - count + 1)
                ids = list(range(start, message.id + 1))
            elif message.reply_to_message:
                ids = list(range(message.reply_to_message.id, message.id + 1))
                ids = ids[-100:]
            else:
                return await message.reply_text(
                    "❌ `/purge 22` ya kisi message par reply karke `/purge` use karo."
                )

            for i in range(0, len(ids), 100):
                await app.delete_messages(message.chat.id, ids[i:i + 100], revoke=True)
        except (TypeError, ValueError):
            await message.reply_text("❌ Purge count number hona chahiye, example: `/purge 22`.")
        except Exception as e:
            await message.reply_text(f"❌ Purge failed: {type(e).__name__}: {str(e)[:120]}")
        return

    if command == "admins":
        try:
            admins = []
            async for member in app.get_chat_members(
                message.chat.id, filter="administrators"
            ):
                if member.user:
                    admins.append(f"• {member.user.mention}")
            if not admins:
                return await message.reply_text("❌ Admin list nahi mili.")
            return await message.reply_text(
                "👑 **Group Admins**\n\n" + "\n".join(admins)
            )
        except Exception as e:
            return await message.reply_text(
                f"❌ Admin list nahi mil saki: {type(e).__name__}: {str(e)[:120]}"
            )

    target = await _target(message, argument)
    if not target:
        return await message.reply_text(
            "❌ Member ko reply karo ya username/user ID do.\n"
            "Example: `/ban @username`"
        )

    if target.id in config.OWNER_ID:
        return await message.reply_text("😌 Ye owner hain — inko touch nahi kar sakti 💗")

    try:
        me = await app.get_me()
        if target.id == me.id:
            return await message.reply_text("😭 Main khud ko ye action nahi de sakti.")
    except Exception:
        pass

    if not await _require_bot_admin(message):
        return

    try:
        try:
            target_member = await app.get_chat_member(message.chat.id, target.id)
            if target_member.status == ChatMemberStatus.OWNER:
                return await message.reply_text("❌ Group owner par ye action nahi ho sakta.")
        except Exception:
            target_member = None

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
            if not await _require_bot_restrict_rights(message):
                return
            await app.restrict_chat_member(
                message.chat.id,
                target.id,
                permissions=ChatPermissions(can_send_messages=False),
            )
            return await message.reply_text(f"🔇 {target.mention} mute ho gaya.")

        if command == "unmute":
            if not await _require_bot_restrict_rights(message):
                return
            await app.restrict_chat_member(
                message.chat.id,
                target.id,
                permissions=_full_permissions(),
            )
            return await message.reply_text(f"🔊 {target.mention} unmute ho gaya.")

        if command == "promote":
            if not await _bot_is_owner(message):
                return await message.reply_text(
                    "❌ Promote ke liye bot ko required admin hierarchy/rights chahiye."
                )
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
            return await message.reply_text(f"⬆️ {target.mention} admin promote ho gaya.")

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
            return await message.reply_text(f"⬇️ {target.mention} admin demote ho gaya.")

        if command == "warn":
            _WARNINGS[message.chat.id][target.id] += 1
            count = _WARNINGS[message.chat.id][target.id]
            if count >= 3:
                await app.ban_chat_member(message.chat.id, target.id)
                _WARNINGS[message.chat.id][target.id] = 0
                return await message.reply_text(
                    f"⚠️ 3 warnings complete — {target.mention} banned."
                )
            return await message.reply_text(f"⚠️ {target.mention} warning {count}/3.")

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
• `/ban`, `/unban`, `/kick` — reply/username/ID
• `/mute`, `/unmute` — reply/username/ID
• `/promote`, `/fullpromote`, `/demote` — reply/username/ID
• `/warn`, `/unwarn` — 3 warnings par ban
• `/del` / `/delete` — replied message delete
• `/purge 22` — last 22 messages delete
• `/purge` — reply se purge
• `/lock`, `/unlock` — group default permissions
• `/admincache` / `/reload` — refresh music admin cache
• New members ko automatic welcome
• Bot ko required admin permissions dena zaroori hai.
"""
