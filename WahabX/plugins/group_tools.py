import asyncio
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message
from WahabX import app
from WahabX.utils.premium import premium_entities

ADMIN_STATUSES = {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}

def _label(user):
    return (getattr(user, "first_name", None) or getattr(user, "username", None) or str(user.id)).strip()

async def _bot_member(client, chat_id):
    """Fetch the bot's membership using its numeric ID (not the ambiguous 'me' string)."""
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

async def _target_from_message(client, message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if len(message.command or []) > 1:
        raw = message.command[1]
        try:
            return await client.get_users(raw)
        except Exception:
            return None
    return None

@app.on_message(filters.group & filters.command(["admins", "adminlist"]))
async def admins_command(client, message: Message):
    if not await _bot_is_admin(client, message.chat.id):
        await message.reply_text("🥰 Mujhe group mein admin rights do, phir /admins kaam karega.", entities=premium_entities("🥰 Mujhe group mein admin rights do, phir /admins kaam karega."))
        return
    admins = []
    async for member in client.get_chat_members(message.chat.id, filter="administrators"):
        user = member.user
        if getattr(user, "is_bot", False):
            continue
        icon = "🥰" if member.status == ChatMemberStatus.OWNER else "💪"
        admins.append(f"{icon} {_label(user)}")
    if not admins:
        text = "😢 Is group mein admins nahi mile."
    else:
        text = "🥰 **Group Admins**\n\n" + "\n".join(admins)
    await message.reply_text(text, entities=premium_entities(text))

@app.on_message(filters.group & filters.command(["promote", "prom"]))
async def promote_command(client, message: Message):
    if not await _caller_is_admin(client, message):
        return

    bot_member = await _bot_member(client, message.chat.id)
    if not bot_member or bot_member.status not in ADMIN_STATUSES:
        text = "🥵 Main is group mein admin nahi hoon. Mujhe pehle admin banao."
        await message.reply_text(text, entities=premium_entities(text))
        return

    # Telegram only allows a bot to grant admin rights it already has.
    if not bool(getattr(bot_member, "can_promote_members", False)):
        text = "🥵 Mere admin rights mein **Add New Admins** permission ON karo, phir /promote chalega."
        await message.reply_text(text, entities=premium_entities(text))
        return

    target = await _target_from_message(client, message)
    if not target:
        text = "🙂 Kisi user ko reply karke /promote bhejo, ya /promote @username."
        await message.reply_text(text, entities=premium_entities(text))
        return
    if target.id == bot_member.user.id:
        text = "🙂 Main khud ko promote nahi kar sakta."
        await message.reply_text(text, entities=premium_entities(text))
        return

    # Match assigned permissions to the bot's own rights. Previously the bot
    # always requested several rights it might not possess, causing Telegram's
    # RIGHT_FORBIDDEN error even when it had Add New Admins enabled.
    rights = {
        "can_change_info": bool(getattr(bot_member, "can_change_info", False)),
        "can_post_messages": bool(getattr(bot_member, "can_post_messages", False)),
        "can_edit_messages": bool(getattr(bot_member, "can_edit_messages", False)),
        "can_delete_messages": bool(getattr(bot_member, "can_delete_messages", False)),
        "can_invite_users": bool(getattr(bot_member, "can_invite_users", False)),
        "can_restrict_members": bool(getattr(bot_member, "can_restrict_members", False)),
        "can_pin_messages": bool(getattr(bot_member, "can_pin_messages", False)),
        "can_manage_video_chats": bool(getattr(bot_member, "can_manage_video_chats", False)),
        "can_manage_topics": bool(getattr(bot_member, "can_manage_topics", False)),
        # Do not pass on the ability to promote more admins by default.
        "can_promote_members": False,
        "is_anonymous": False,
    }
    try:
        await client.promote_chat_member(message.chat.id, target.id, **rights)
        text = f"🥰 **Promoted:** {_label(target)}"
        await message.reply_text(text, entities=premium_entities(text))
    except Exception as e:
        reason = str(e)
        print(f"[GROUP] promote failed: {type(e).__name__}: {reason}")
        if "RIGHT_FORBIDDEN" in reason.upper() or "CHAT_ADMIN_REQUIRED" in reason.upper():
            text = "😢 Telegram ne promotion reject ki. Bot ke admin rights mein **Add New Admins** ON check karo aur ensure karo target owner nahi hai."
        else:
            text = f"😢 Promote nahi hua: {type(e).__name__}. Bot ke **Add New Admins** rights aur target ki admin hierarchy check karo."
        await message.reply_text(text, entities=premium_entities(text))


@app.on_message(filters.group & filters.command(["demote", "dem"]))
async def demote_command(client, message: Message):
    if not await _caller_is_admin(client, message):
        return
    if not await _bot_is_admin(client, message.chat.id):
        return
    target = await _target_from_message(client, message)
    if not target:
        text = "🙂 Kisi admin ko reply karke /demote bhejo, ya /demote @username."
        await message.reply_text(text, entities=premium_entities(text))
        return
    try:
        await client.promote_chat_member(message.chat.id, target.id, can_change_info=False, can_post_messages=False, can_edit_messages=False, can_delete_messages=False, can_invite_users=False, can_restrict_members=False, can_pin_messages=False, can_manage_video_chats=False, can_promote_members=False, is_anonymous=False)
        text = f"😜 **Demoted:** {_label(target)}"
        await message.reply_text(text, entities=premium_entities(text))
    except Exception as e:
        print(f"[GROUP] demote failed: {type(e).__name__}: {e}")
        text = "😢 Demote nahi hua. Owner/admin hierarchy check karo."
        await message.reply_text(text, entities=premium_entities(text))

@app.on_message(filters.group & filters.command(["tagall", "all"]))
async def tagall_command(client, message: Message):
    if not await _caller_is_admin(client, message):
        return
    if not await _bot_is_admin(client, message.chat.id):
        text = "🥵 Pehle mujhe group mein admin banao, phir /tagall sabko tag karega."
        await message.reply_text(text, entities=premium_entities(text))
        return

    members = []
    async for member in client.get_chat_members(message.chat.id):
        user = member.user
        if not user or getattr(user, "is_bot", False) or getattr(user, "is_deleted", False):
            continue
        if user.id not in {x.id for x in members}:
            members.append(user)

    if not members:
        text = "😢 Koi member nahi mila."
        await message.reply_text(text, entities=premium_entities(text))
        return

    prefix = (message.text or "").split(maxsplit=1)
    custom = prefix[1].strip() if len(prefix) > 1 else "Everyone idhar dekho 💋"
    chunks = []
    current = custom + "\n\n"
    for user in members:
        mention = user.mention(style="md")
        piece = mention + " "
        if len(current) + len(piece) > 3500:
            chunks.append(current.rstrip())
            current = piece
        else:
            current += piece
    if current.strip():
        chunks.append(current.rstrip())

    for i, chunk in enumerate(chunks):
        text = f"💋 **Tag All**\n{chunk}"
        try:
            await message.reply_text(text, parse_mode="markdown", disable_web_page_preview=True)
        except Exception as e:
            print(f"[GROUP] tagall failed: {type(e).__name__}: {e}")
        if i + 1 < len(chunks):
            await asyncio.sleep(0.4)
