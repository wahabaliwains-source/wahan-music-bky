# All rights reserved.

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message

from config import BANNED_USERS
from strings import command
from WahabX import app
from WahabX.utils.decorators import language
from WahabX.utils.decorators.admins import refresh_admin_cache


@app.on_message(command("RELOAD_COMMAND") & filters.group & ~BANNED_USERS)
@language
async def reload_admin_cache_command(client, message: Message, _):
    try:
        chat_id = message.chat.id
        me = await client.get_me()
        bot_member = await client.get_chat_member(chat_id, me.id)
        if bot_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return await message.reply_text(
                "❌ 💎 Admin list refresh karne ke liye pehle bot ko group admin banao."
            )

        # The cache is replaced only after Telegram's full admin scan succeeds.
        admins = await refresh_admin_cache(client, chat_id)
        if not admins:
            return await message.reply_text(
                "⚠️ Telegram se admin list empty mili. Bot ka admin access check karo; purana cache preserve kiya gaya hai."
            )
        await message.reply_text(
            f"💎 **Admin cache refresh ho gaya!**\n"
            f"👑 Admin/authorized users cached: {len(admins)}"
        )
    except Exception as e:
        print(f"[ADMIN_CACHE] reload failed for {message.chat.id}: {type(e).__name__}: {e}")
        await message.reply_text(
            f"❌ 💎 Admin list refresh nahi ho saka ({type(e).__name__}). "
            "Bot ko admin banao aur /admincache dobara chalao."
        )
