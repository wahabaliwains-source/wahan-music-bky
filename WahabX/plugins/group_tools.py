import asyncio
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message
from WahabX import app
from WahabX.utils.premium import premium_entities

ADMIN_STATUSES = {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}

def _label(user):
    return (getattr(user, "first_name", None) or getattr(user, "username", None) or str(user.id)).strip()

async def _bot_is_admin(client, chat_id):
    try:
        me = await client.get_chat_member(chat_id, "me")
        return me.status in ADMIN_STATUSES
    except Exception:
        return False

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
    if not await _bot_is_admin(client, message.chat.id):
        text = "🥵 Mujhe admin rights ke saath **Add New Admins** permission bhi do."
        await message.reply_text(text, entities=premium_entities(text))
        return
    target = await _target_from_message(client, message)
    if not target:
        text = "🙂 Kisi user ko reply karke /promote bhejo, ya /promote @username."
        await message.reply_text(text, entities=premium_entities(text))
        return
    try:
        await client.promote_chat_member(
            message.chat.id,
            target.id,
            can_change_info=False,
            can_post_messages=True,
            can_edit_messages=True,
            can_delete_messages=True,
            can_invite_users=True,
            can_restrict_members=True,
            can_pin_messages=True,
            can_manage_video_chats=True,
            can_promote_members=False,
        )
        text = f"🥰 **Promoted:** {_label(target)}"
        await message.reply_text(text, entities=premium_entities(text))
    except Exception as e:
        print(f"[GROUP] promote failed: {type(e).__name__}: {e}")
        text = "😢 Promote nahi hua. Check karo bot ke paas **Add New Admins** permission aur target par Telegram restrictions na hon."
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
