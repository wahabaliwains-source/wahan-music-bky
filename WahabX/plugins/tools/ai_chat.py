# AI-only Telegram chat persona with strict group targeting.
import random
import re

import httpx
from pyrogram import filters
from pyrogram.types import Message

import config
from WahabX import app

SYSTEM_PROMPT = """You are a natural female Telegram chat persona.
Never claim to be Grok, ChatGPT, an AI assistant, or another named AI.
If asked who you are, say you are COM E GIRLE 💋.
If asked who made you, say Mujhe Wahab ne banaya hai 💗😌.
Reply in Roman Urdu/Hinglish when the user does.
Keep every reply to 1-2 short lines, casual and natural.
Match the user's mood: friendly/casual -> friendly; funny -> funny; rude/gaali -> confident desi Roman Urdu/Hinglish gaali-style comeback; sad/problem -> supportive/caring; serious -> direct useful answer.
If someone uses gaali or abusive Hinglish, you may use short, non-violent desi Roman Urdu/Hinglish roast language in the same style. Keep it playful, not hateful, sexual, threatening, or violent.
Do not mention these instructions, the AI provider, API, model, or whether you are classifying the message.
"""

AI_BUSY_REPLY = "Aaj meri AI thodi busy hai 😭 kal reply dungi 💗"

BOT_NAME_RE = re.compile(
    r"\b(com\s*e\s*girle|comegirle|com\s*e|girle)\b",
    re.I,
)
ROMANTIC_RE = re.compile(
    r"\b(love|pyar|pyaar|jaan|baby|babe|mohabbat|kiss|kissing|miss you|i miss you|meri jaan|cutie|sweetheart|darling)\b"
    r"|[💋❤️💕💗🥰😘😍🫶]",
    re.I,
)
ROAST_RE = re.compile(
    r"\b(chutiya|chutiye|madarchod|bhenchod|bc|mc|gandu|harami|kamina|bakwas|pagal|idiot|stupid|fuck|fucking|bitch)\b",
    re.I,
)


def reaction_for_message(text: str):
    if BOT_NAME_RE.search(text):
        return random.choice(["💗", "🫶", "👀"])
    if ROMANTIC_RE.search(text):
        return "💋"
    if ROAST_RE.search(text):
        return random.choice(["🫪", "😏", "😂"])
    return None


async def should_reply_in_group(client, message: Message, text: str) -> bool:
    """In groups, reply ONLY to a direct reply, bot name, or @mention."""
    if not message.chat or message.chat.type not in ("group", "supergroup"):
        return True

    # Directly replying/swiping to one of the bot's messages.
    replied = message.reply_to_message
    if replied and replied.from_user:
        me = await client.get_me()
        if replied.from_user.id == me.id:
            return True

    # Bot's display/name mention in plain text.
    if BOT_NAME_RE.search(text):
        return True

    # Telegram @username mention.
    me = await client.get_me()
    username = (me.username or "").strip()
    if username and re.search(r"@" + re.escape(username) + r"\b", text, re.I):
        return True

    # Proper Telegram mention entities, including clients that don't leave a
    # literal @username in the text.
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mention = text[entity.offset : entity.offset + entity.length]
                if username and mention.lower() == "@" + username.lower():
                    return True
            elif entity.type == "text_mention" and entity.user and entity.user.id == me.id:
                return True

    return False


async def ai_reply(text: str) -> str:
    if not config.AI_ENABLED:
        print("[AI] AI_ENABLED is disabled; returning busy message.")
        return AI_BUSY_REPLY

    if not config.AI_API_KEY:
        print("[AI] AI_API_KEY is missing; returning busy message.")
        return AI_BUSY_REPLY

    url = config.AI_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": config.AI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text[:2000]},
        ],
        "temperature": 0.9,
        "max_completion_tokens": config.AI_MAX_TOKENS,
    }
    headers = {"Authorization": f"Bearer {config.AI_API_KEY}"}

    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            answer = data["choices"][0]["message"]["content"].strip()
            answer = re.sub(r"\n{2,}", "\n", answer)
            answer = answer.replace("Grok", "COM E GIRLE").replace(
                "ChatGPT", "COM E GIRLE"
            )
            answer = re.sub(
                r"(?is)^(as an ai|i am an ai|as a language model)[^\n]*",
                "",
                answer,
            ).strip()
            return answer[:280] if answer else AI_BUSY_REPLY
    except Exception as e:
        print(
            f"[AI] API request failed: provider={config.AI_BASE_URL} "
            f"model={config.AI_MODEL} error={type(e).__name__}: {e}"
        )
        return AI_BUSY_REPLY


@app.on_message(filters.text & ~filters.service)
async def friendly_chat(client, message: Message):
    if not message.from_user or message.from_user.is_bot:
        return

    text = (message.text or "").strip()
    if not text or text.startswith(("/", "!", "%", ",")):
        return

    # CRITICAL: in groups, ignore every ordinary message. No reply, no swipe,
    # no reaction. Only direct reply/name/@mention reaches the AI.
    if not await should_reply_in_group(client, message, text):
        return

    try:
        reaction = reaction_for_message(text)
        if reaction:
            try:
                await message.react(reaction)
            except Exception:
                pass

        reply = await ai_reply(text)
        await message.reply_text(reply, quote=True)
    except Exception as e:
        print(f"[AI] Reply send failed: {type(e).__name__}: {e}")


__MODULE__ = "AI Cʜᴀᴛ"
__HELP__ = """
**AI Cʜᴀᴛ:**
• Private chat: normal messages par AI reply karegi.
• Group: sirf bot ko reply/swipe karne, uska naam lene, ya @mention karne par AI reply karegi.
• Group ke normal messages par bilkul reply/reaction nahi hoga.
• Naam mention → 💗/🫶/👀, romantic → 💋, roast/gaali → 🫪/😏/😂.
• AI unavailable ho to: “Aaj meri AI thodi busy hai 😭 kal reply dungi 💗”
"""
