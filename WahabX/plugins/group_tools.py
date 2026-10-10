import asyncio

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatMembersFilter
from pyrogram.types import Message

from WahabX import app

ADMIN_STATUSES = {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}


def _label(user):
    return (
        getattr(user, "first_name", None)
        or getattr(user, "username", None)
        or str(user.id)
    ).strip()


async def _bot_member(client, chat_id):
    """Fetch bot membership by numeric ID, never by the ambiguous 'me' alias."""
    try:
        me = await client.get_me()
        return await client.get_chat_member(chat_id, me.id)
    except Exception as e:
        print(f"[GROUP] could not fetch bot membership: {type(e).__name__}: {e}")
        return None


async def _bot_is_admin(client, chat_id):
    member = await _bot_member(client, chat_id)
    return bool(member and member.status in ADMIN_STATUSES)


async def _caller_is_admin(client, message):
    if not message.from_user:
        return False
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in ADMIN_STATUSES
    except Exception:
        return False


async def _caller_can_manage_admins(client, message):
    """Only the owner or an admin with Add New Admins may promote."""
    if not message.from_user:
        return False
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if member.status == ChatMemberStatus.OWNER:
            return True
        return (
            member.status == ChatMemberStatus.ADMINISTRATOR
            and _right(member, "can_promote_members")
        )
    except Exception as e:
        print(f"[GROUP] could not verify caller promotion rights: {type(e).__name__}: {e}")
        return False


async def _target_from_message(client, message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if len(message.command or []) > 1:
        raw = message.command[1].strip()
        try:
            return await client.get_users(raw)
        except Exception:
            try:
                return await client.get_users(int(raw))
            except Exception:
                return None
    return None


def _right(member, name):
    direct = getattr(member, name, None)
    privileges = getattr(member, "privileges", None)
    return bool(direct or getattr(privileges, name, False))


@app.on_message(filters.group & filters.command(["admins", "adminlist"]))
async def admins_command(client, message: Message):
    if not await _bot_is_admin(client, message.chat.id):
        return await message.reply_text(
            "🥰 Mujhe group mein admin banao, phir /admins kaam karega."
        )
    try:
        admins = []
        async for member in client.get_chat_members(
            message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS
        ):
            user = member.user
            if not user or getattr(user, "is_bot", False):
                continue
            icon = "👑" if member.status == ChatMemberStatus.OWNER else "💎"
            admins.append(f"{icon} {_label(user)}")
        if not admins:
            return await message.reply_text("😢 Is group mein admins nahi mile.")
        return await message.reply_text("👑 **Group Admins**\n\n" + "\n".join(admins))
    except Exception as e:
        print(f"[GROUP] admin list failed: {type(e).__name__}: {e}")
        return await message.reply_text(
            "❌ Admin list fetch nahi hui. Bot ke admin rights check karo aur /admincache try karo."
        )


@app.on_message(filters.group & filters.command(["promote", "prom", "fullpromote", "fullprom"]))
async def promote_command(client, message: Message):
    command_name = (message.command[0].split("@", 1)[0].lower() if message.command else "")
    full = command_name in {"fullpromote", "fullprom"}
    if not await _caller_can_manage_admins(client, message):
        return await message.reply_text(
            "🥵 Sirf group owner ya **Add New Admins** permission wala admin promote kar sakta hai."
        )

    bot_member = await _bot_member(client, message.chat.id)
    if not bot_member or bot_member.status not in ADMIN_STATUSES:
        return await message.reply_text(
            "🥵 Main is group mein admin nahi hoon. Mujhe pehle admin banao."
        )
    if not _right(bot_member, "can_promote_members"):
        return await message.reply_text(
            "🥵 Mere admin rights mein **Add New Admins** permission ON karo."
        )

    target = await _target_from_message(client, message)
    if not target:
        cmd = "/fullpromote" if full else "/promote"
        return await message.reply_text(
            f"🙂 User ke message par reply karke {cmd} bhejo, ya {cmd} @username."
        )
    if target.id == bot_member.user.id:
        return await message.reply_text("🙂 Main khud ko promote nahi kar sakta.")

    try:
        target_member = await client.get_chat_member(message.chat.id, target.id)
        if target_member.status == ChatMemberStatus.OWNER:
            return await message.reply_text("❌ Group owner ko promote nahi kar sakte.")
    except Exception:
        target_member = None

    # Telegram only permits a bot to grant rights it itself has. fullpromote
    # mirrors supported rights from this bot; normal promote keeps promote-rights disabled.
    rights = {
        "can_change_info": _right(bot_member, "can_change_info"),
        "can_post_messages": _right(bot_member, "can_post_messages"),
        "can_edit_messages": _right(bot_member, "can_edit_messages"),
        "can_delete_messages": _right(bot_member, "can_delete_messages"),
        "can_invite_users": _right(bot_member, "can_invite_users"),
        "can_restrict_members": _right(bot_member, "can_restrict_members"),
        "can_pin_messages": _right(bot_member, "can_pin_messages"),
        "can_manage_video_chats": _right(bot_member, "can_manage_video_chats"),
        "can_promote_members": _right(bot_member, "can_promote_members") if full else False,
        "is_anonymous": False,
    }
    try:
        await client.promote_chat_member(message.chat.id, target.id, **rights)
        rights_names = [
            key.removeprefix("can_").replace("_", " ")
            for key, value in rights.items()
            if value and key != "is_anonymous"
        ]
        summary = ", ".join(rights_names) if rights_names else "basic admin"
        prefix = "💎 **FULL PROMOTE complete!**" if full else "💎 **Promoted!**"
        return await message.reply_text(
            f"{prefix}\n👤 {_label(target)}\n🛡 Rights: {summary}"
        )
    except Exception as e:
        reason = str(e)
        print(f"[GROUP] {'fullpromote' if full else 'promote'} failed: {type(e).__name__}: {reason}")
        if "RIGHT_FORBIDDEN" in reason.upper() or "CHAT_ADMIN_REQUIRED" in reason.upper():
            text = (
                "😢 Telegram ne promotion reject ki. Bot ko **Add New Admins** aur "
                "required admin rights enable karo; target owner/equal-higher admin na ho."
            )
        else:
            text = f"😢 Promote fail: {type(e).__name__}: {reason[:120]}"
        return await message.reply_text(text)


@app.on_message(filters.group & filters.command(["demote", "dem"]))
async def demote_command(client, message: Message):
    if not await _caller_can_manage_admins(client, message):
        return
    bot_member = await _bot_member(client, message.chat.id)
    if not bot_member or bot_member.status not in ADMIN_STATUSES or not _right(bot_member, "can_promote_members"):
        return await message.reply_text(
            "❌ Demote ke liye bot ko admin aur **Add New Admins** permission chahiye."
        )
    target = await _target_from_message(client, message)
    if not target:
        return await message.reply_text(
            "🙂 Kisi admin ko reply karke /demote bhejo, ya /demote @username."
        )
    try:
        member = await client.get_chat_member(message.chat.id, target.id)
        if member.status == ChatMemberStatus.OWNER:
            return await message.reply_text("❌ Group owner ko demote nahi kar sakte.")
        await client.promote_chat_member(
            message.chat.id,
            target.id,
            can_change_info=False,
            can_post_messages=False,
            can_edit_messages=False,
            can_delete_messages=False,
            can_invite_users=False,
            can_restrict_members=False,
            can_pin_messages=False,
            can_manage_video_chats=False,
            can_promote_members=False,
            is_anonymous=False,
        )
        return await message.reply_text(f"⬇️ **Demoted:** {_label(target)}")
    except Exception as e:
        print(f"[GROUP] demote failed: {type(e).__name__}: {e}")
        return await message.reply_text(
            f"😢 Demote fail: {type(e).__name__}: {str(e)[:120]}"
        )


@app.on_message(filters.group & filters.command(["tagall", "all"]))
async def tagall_command(client, message: Message):
    if not await _caller_is_admin(client, message):
        return
    if not await _bot_is_admin(client, message.chat.id):
        return await message.reply_text(
            "🥵 Pehle mujhe group mein admin banao, phir /tagall sabko tag karega."
        )

    members = []
    async for member in client.get_chat_members(message.chat.id):
        user = member.user
        if not user or getattr(user, "is_bot", False) or getattr(user, "is_deleted", False):
            continue
        if user.id not in {x.id for x in members}:
            members.append(user)

    if not members:
        return await message.reply_text("😢 Koi member nahi mila.")

    prefix = (message.text or "").split(maxsplit=1)
    custom = prefix[1].strip() if len(prefix) > 1 else "Everyone idhar dekho 💋"
    chunks = []
    current = custom + "\n\n"
    for user in members:
        piece = user.mention(style="md") + " "
        if len(current) + len(piece) > 3500:
            chunks.append(current.rstrip())
            current = piece
        else:
            current += piece
    if current.strip():
        chunks.append(current.rstrip())

    for i, chunk in enumerate(chunks):
        try:
            await message.reply_text(
                f"💋 **Tag All**\n{chunk}",
                parse_mode="markdown",
                disable_web_page_preview=True,
            )
        except Exception as e:
            print(f"[GROUP] tagall failed: {type(e).__name__}: {e}")
        if i + 1 < len(chunks):
            await asyncio.sleep(0.4)
