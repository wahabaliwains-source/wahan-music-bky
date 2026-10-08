from pyrogram import filters
from pyrogram.types import Message

from WahabX import app
from WahabX.utils.premium import premium_entities


WELCOME_TEXT = (
    "😘 **Welcome {name}!**\n\n"
    "Himwari ki group family mein welcome 💗\n"
    "Rules follow karo aur enjoy karo 🎀"
)


@app.on_message(filters.group & filters.new_chat_members)
async def group_welcome(client, message: Message):
    members = getattr(message, "new_chat_members", None) or []
    if not members:
        return

    names = []
    for user in members:
        if getattr(user, "is_bot", False):
            continue
        name = (getattr(user, "first_name", None) or getattr(user, "username", None) or "friend").strip()
        names.append(name)

    if not names:
        return

    if len(names) == 1:
        text = WELCOME_TEXT.format(name=names[0])
    else:
        joined = ", ".join(names[:10])
        if len(names) > 10:
            joined += f" +{len(names) - 10} more"
        text = (
            "😘 **Welcome everyone!**\n\n"
            f"New members: **{joined}**\n"
            "Himwari ki group family mein welcome 💗\n"
            "Rules follow karo aur enjoy karo 🎀"
        )

    try:
        await message.reply_text(text, entities=premium_entities(text))
    except Exception as e:
        print(f"[WELCOME] premium welcome failed: {type(e).__name__}: {e}")
        try:
            await message.reply_text(text)
        except Exception as fallback_error:
            print(f"[WELCOME] fallback failed: {type(fallback_error).__name__}: {fallback_error}")


__MODULE__ = "Gʀᴏᴜᴘ Wᴇʟᴄᴏᴍᴇ"
__HELP__ = """
**Group Welcome:**
• New members automatically get a welcome message.
• Welcome message uses the approved premium custom-emoji set.
• Multiple new members are grouped into one welcome.
• Bot accounts are ignored.
"""
