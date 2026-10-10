# All rights reserved.

from pyrogram import filters
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
        admins = await refresh_admin_cache(client, chat_id)
        await message.reply_text(
            f"✅ **Admin cache refresh ho gaya!**\n"
            f"👑 Admin/authorized users cached: {len(admins)}"
        )
    except Exception as e:
        print(f"[ADMIN_CACHE] reload failed for {message.chat.id}: {type(e).__name__}: {e}")
        await message.reply_text(
            "❌ Admin cache refresh nahi ho saka. Confirm karo bot group mein admin hai "
            "aur phir /admincache dobara try karo."
        )
