
#
# All rights reserved.
import importlib

from pyrogram import idle
from pyrogram.errors import FloodWait

import config
from config import BANNED_USERS
from WahabX import HELPABLE, LOGGER, app, userbot
from WahabX.core.call import Ayush
from WahabX.plugins import ALL_MODULES
from WahabX.utils.database import get_banned_users, get_gbanned
from WahabX.utils.premium import install_text_entities_patch, validate_db

install_text_entities_patch()


async def init():
    if len(config.STRING_SESSIONS) == 0:
        LOGGER("WahabX").error(
            "No Assistant Clients Vars Defined!.. Exiting Process."
        )
        return
    if not config.SPOTIFY_CLIENT_ID and not config.SPOTIFY_CLIENT_SECRET:
        LOGGER("WahabX").warning(
            "No Spotify Vars defined. Your bot won't be able to play spotify queries."
        )
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except Exception:
        pass

    # Start each Telegram client exactly once. The normal bot uses a persistent
    # session in tempdb, while the assistant uses the supplied string session.
    # Do not wrap successful starts in another reconnect/start loop.
    await userbot.start()
    LOGGER("WahabX").info("Assistant Started Successfully")

    try:
        await app.start()
    except FloodWait as e:
        LOGGER("WahabX").error(
            f"Bot login is flood-limited for {e.value} seconds; startup stopped to avoid reconnect looping."
        )
        await userbot.stop()
        return

    LOGGER("WahabX").info("Bot Started Successfully")
    LOGGER("WahabX").info("Validating premium emoji database...")
    try:
        await validate_db(app)
    except Exception:
        LOGGER("WahabX").warning("Could not validate premium emoji database.")

    for all_module in ALL_MODULES:
        imported_module = importlib.import_module(all_module)
        if hasattr(imported_module, "__MODULE__") and imported_module.__MODULE__:
            if hasattr(imported_module, "__HELP__") and imported_module.__HELP__:
                HELPABLE[imported_module.__MODULE__.lower()] = imported_module

    LOGGER("WahabX.plugins").info("Successfully Imported All Modules")

    # Start PyTgCalls once. Do not perform a fake stream/join/leave test at
    # startup; that test was creating an unnecessary Telegram voice request.
    await Ayush.start()
    LOGGER("WahabX").info("PyTgCalls Started Successfully")
    LOGGER("WahabX").info("WahabX Started Successfully")

    await idle()

    await app.stop()
    await userbot.stop()


if __name__ == "__main__":
    app.run(init())
    LOGGER("WahabX").info("Stopping WahabX! GoodBye")
