
# All rights reserved.
#

from pyrogram.enums import ChatMemberStatus, ChatType, ChatMembersFilter
from pyrogram.types import InlineKeyboardMarkup

from config import adminlist
from strings import get_string
from WahabX import app
from WahabX.misc import SUDOERS
from WahabX.utils.database import (
    get_authuser_names,
    get_cmode,
    get_lang,
    is_active_chat,
    is_commanddelete_on,
    is_maintenance,
    is_nonadmin_chat,
)

from ..formatters import int_to_alpha, alpha_to_int
from WahabX.utils.premium import warn_btn


async def refresh_admin_cache(client, chat_id: int):
    """Rebuild the per-chat player admin cache from Telegram and authorized users."""
    fresh = []
    async for member in client.get_chat_members(
        chat_id, filter=ChatMembersFilter.ADMINISTRATORS
    ):
        user = getattr(member, "user", None)
        status = getattr(member, "status", None)
        if user and status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        ):
            fresh.append(user.id)

    try:
        authusers = await get_authuser_names(chat_id) or []
    except Exception as e:
        authusers = []
        print(f"[ADMIN_CACHE] authorized-user lookup failed for {chat_id}: {type(e).__name__}: {e}")

    for value in authusers:
        try:
            if isinstance(value, int):
                user_id = value
            else:
                raw = str(value).strip()
                user_id = int(raw) if raw.isdigit() else await alpha_to_int(raw)
            if user_id:
                fresh.append(int(user_id))
        except Exception as e:
            print(f"[ADMIN_CACHE] skipped malformed authorized user for {chat_id}: {type(e).__name__}")

    fresh = list(dict.fromkeys(fresh))
    # Apply the new cache only after the Telegram admin scan succeeds.
    adminlist[chat_id] = fresh
    return fresh


def AdminRightsCheck(mystic):
    async def wrapper(client, message):
        if not await is_maintenance():
            if message.from_user.id not in SUDOERS:
                return
        if await is_commanddelete_on(message.chat.id):
            try:
                await message.delete()
            except Exception:
                pass
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)
        except Exception:
            _ = get_string("en")
        if message.sender_chat:
            upl = InlineKeyboardMarkup(
                [
                    [
                        warn_btn(
                            text="How to Fix this? ",
                            callback_data="AnonymousAdmin",
                        ),
                    ]
                ]
            )
            return await message.reply_text(_["general_4"], reply_markup=upl)
        if message.command[0][0] == "c":
            chat_id = await get_cmode(message.chat.id)
            if chat_id is None:
                return await message.reply_text(_["setting_12"])
            try:
                await app.get_chat(chat_id)
            except Exception:
                return await message.reply_text(_["cplay_4"])
        else:
            chat_id = message.chat.id
        if not await is_active_chat(chat_id):
            return await message.reply_text(_["general_6"])
        is_non_admin = await is_nonadmin_chat(message.chat.id)
        if not is_non_admin:
            if message.from_user.id not in SUDOERS:
                admins = adminlist.get(message.chat.id) or []
                if message.from_user.id not in admins:
                    # First ask Telegram directly: cache may be stale after a
                    # promotion/demotion or bot restart.
                    try:
                        member = await client.get_chat_member(
                            message.chat.id, message.from_user.id
                        )
                        if member.status in (
                            ChatMemberStatus.OWNER,
                            ChatMemberStatus.ADMINISTRATOR,
                        ):
                            admins = await refresh_admin_cache(client, message.chat.id)
                            if message.from_user.id not in admins:
                                admins.append(message.from_user.id)
                                adminlist[message.chat.id] = admins
                        else:
                            admins = await refresh_admin_cache(client, message.chat.id)
                    except Exception as e:
                        print(f"[ADMIN_CACHE] refresh failed for {message.chat.id}: {type(e).__name__}: {e}")
                        return await message.reply_text(
                            "❌ 💎 Admin list Telegram se refresh nahi hui. Bot ka admin access check karo aur /admincache try karo."
                        )
                    if message.from_user.id not in admins:
                        return await message.reply_text(_["admin_19"])
        return await mystic(client, message, _, chat_id)

    return wrapper


def AdminActual(mystic):
    async def wrapper(client, message):
        if not await is_maintenance():
            if message.from_user.id not in SUDOERS:
                return

        if await is_commanddelete_on(message.chat.id):
            try:
                await message.delete()
            except Exception:
                pass

        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)
        except Exception:
            _ = get_string("en")

        if message.sender_chat:
            upl = InlineKeyboardMarkup(
                [
                    [
                        warn_btn(
                            text="How to Fix this?",
                            callback_data="AnonymousAdmin",
                        ),
                    ]
                ]
            )
            return await message.reply_text(_["general_4"], reply_markup=upl)

        if message.from_user.id not in SUDOERS:
            try:
                member = await client.get_chat_member(
                    message.chat.id, message.from_user.id
                )

                if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER] or (
                    member.privileges is None
                    or not member.privileges.can_manage_video_chats
                ):

                    return await message.reply(_["general_5"])

            except Exception as e:
                return await message.reply(f"Error: {str(e)}")

        return await mystic(client, message, _)

    return wrapper


def ActualAdminCB(mystic):
    async def wrapper(client, CallbackQuery):
        try:
            language = await get_lang(CallbackQuery.message.chat.id)
            _ = get_string(language)
        except Exception:
            _ = get_string("en")

        if not await is_maintenance():
            if CallbackQuery.from_user.id not in SUDOERS:
                return await CallbackQuery.answer(
                    _["maint_4"],
                    show_alert=True,
                )

        if CallbackQuery.message.chat.type == ChatType.PRIVATE:
            return await mystic(client, CallbackQuery, _)

        is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
        if not is_non_admin:
            try:
                a = await app.get_chat_member(
                    CallbackQuery.message.chat.id,
                    CallbackQuery.from_user.id,
                )

                if a is None or (
                    a.privileges is None or not a.privileges.can_manage_video_chats
                ):
                    if CallbackQuery.from_user.id not in SUDOERS:
                        token = await int_to_alpha(CallbackQuery.from_user.id)
                        _check = await get_authuser_names(CallbackQuery.from_user.id)
                        if token not in _check:
                            return await CallbackQuery.answer(
                                _["general_5"],
                                show_alert=True,
                            )

            except Exception as e:
                return await CallbackQuery.answer(f"Error: {str(e)}")

        return await mystic(client, CallbackQuery, _)

    return wrapper
