
# All rights reserved.
#

import random
import os
import string
import time as _time

from pyrogram import filters
from pyrogram.errors import ChatWriteForbidden
from pyrogram.types import InlineKeyboardMarkup, Message

import config
from config import BANNED_USERS, lyrical
from strings import command
from WahabX import app, LOGGER, Platform
from WahabX.core.call import Ayush
from WahabX.misc import db
from WahabX.utils import seconds_to_min, time_to_seconds
from WahabX.utils.database import is_video_allowed
from WahabX.utils.decorators.play import PlayWrapper
from WahabX.utils.formatters import formats
from WahabX.utils.inline.play import (
    livestream_markup,
    playlist_markup,
    slider_markup,
    stream_markup,
    track_markup,
)
from WahabX.utils.inline.playlist import botplaylist_markup
from WahabX.utils.logger import play_logs
from WahabX.utils.stream.stream import stream
from WahabX.utils.stream.queue import put_queue
from WahabX.utils.notify import notify_owner
from WahabX.utils.premium import premium_entities

_PLAY_LOG = "Play"


@app.on_message(
    command(
        "PLAY_COMMAND",
        prefixes=["/", "!", "%", ",", "@", "#"],
    )
    & filters.group
    & ~BANNED_USERS
)
@PlayWrapper
async def play_commnd(
    client,
    message: Message,
    _,
    chat_id,
    video,
    channel,
    playmode,
    url,
    fplay,
):
    t0 = _time.monotonic()
    query_text = message.text or ""
    LOGGER(_PLAY_LOG).info(
        "[PLAY] command received from user=%s chat=%s text=%s",
        message.from_user.id if message.from_user else "?",
        message.chat.id,
        query_text[:120],
    )
    try:
        mystic = await message.reply_text(
            _["play_2"].format(channel) if channel else _["play_1"]
        )
    except ChatWriteForbidden:
        LOGGER(_PLAY_LOG).warning("[PLAY] ChatWriteForbidden for chat=%s", message.chat.id)
        return
    plist_id = None
    slider = None
    plist_type = None
    spotify = None
    user_id = message.from_user.id
    user_name = message.from_user.mention
    audio_telegram = (
        (message.reply_to_message.audio or message.reply_to_message.voice)
        if message.reply_to_message
        else None
    )
    video_telegram = (
        (message.reply_to_message.video or message.reply_to_message.document)
        if message.reply_to_message
        else None
    )
    if audio_telegram:
        if audio_telegram.file_size > config.TG_AUDIO_FILESIZE_LIMIT:
            return await mystic.edit_text(_["play_5"])
        duration_min = seconds_to_min(audio_telegram.duration)
        if (audio_telegram.duration) > config.DURATION_LIMIT:
            return await mystic.edit_text(
                _["play_6"].format(config.DURATION_LIMIT_MIN, duration_min)
            )
        file_path = await Platform.telegram.get_filepath(audio=audio_telegram)
        if await Platform.telegram.download(_, message, mystic, file_path):
            message_link = await Platform.telegram.get_link(message)
            file_name = await Platform.telegram.get_filename(audio_telegram, audio=True)
            dur = await Platform.telegram.get_duration(audio_telegram)
            details = {
                "title": file_name,
                "link": message_link,
                "path": file_path,
                "dur": dur,
            }

            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    streamtype="telegram",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                if ex_type == "AssistantErr":
                    err = e
                else:
                    err = _["general_3"].format(ex_type)
                    LOGGER(__name__).error("An error occurred", exc_info=True)
                return await mystic.edit_text(err)
            return await mystic.delete()
        return
    elif video_telegram:
        if not await is_video_allowed(message.chat.id):
            return await mystic.edit_text(_["play_3"])
        if message.reply_to_message.document:
            try:
                ext = video_telegram.file_name.split(".")[-1]
                if ext.lower() not in formats:
                    return await mystic.edit_text(
                        _["play_8"].format(f"{' | '.join(formats)}")
                    )
            except Exception:
                return await mystic.edit_text(
                    _["play_8"].format(f"{' | '.join(formats)}")
                )
        if video_telegram.file_size > config.TG_VIDEO_FILESIZE_LIMIT:
            return await mystic.edit_text(_["play_9"])
        file_path = await Platform.telegram.get_filepath(video=video_telegram)
        if await Platform.telegram.download(_, message, mystic, file_path):
            message_link = await Platform.telegram.get_link(message)
            file_name = await Platform.telegram.get_filename(video_telegram)
            dur = await Platform.telegram.get_duration(video_telegram)
            details = {
                "title": file_name,
                "link": message_link,
                "path": file_path,
                "dur": dur,
            }
            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    video=True,
                    streamtype="telegram",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                if ex_type == "AssistantErr":
                    err = e
                else:
                    LOGGER(__name__).error("An error occurred", exc_info=True)
                    err = _["general_3"].format(ex_type)
                return await mystic.edit_text(err)
            return await mystic.delete()
        return
    elif url:
        # Video commands must not silently fall back to audio-only sources.
        if video:
            video_source = (
                await Platform.youtube.exists(url)
                or await Platform.spotify.valid(url)
                or await Platform.apple.valid(url)
                or await Platform.resso.valid(url)
            )
            if not video_source:
                return await mystic.edit_text("❌ Video stream ke liye YouTube link/title (ya supported Spotify/Apple/Resso link) use karo.")
        if await Platform.youtube.exists(url):
            if "playlist" in url:
                try:
                    details = await Platform.youtube.playlist(
                        url,
                        config.PLAYLIST_FETCH_LIMIT,
                    )
                except Exception as e:
                    print(e)
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "yt"
                if "&" in url:
                    plist_id = (url.split("=")[1]).split("&")[0]
                else:
                    plist_id = url.split("=")[1]
                img = config.PLAYLIST_IMG_URL
                cap = _["play_10"]
            elif "https://youtu.be" in url:
                videoid = url.split("/")[-1].split("?")[0]
                try:
                    details, track_id = await Platform.youtube.track(
                        f"https://www.youtube.com/watch?v={videoid}"
                    )
                    streamtype = "youtube"
                    img = details["thumb"]
                    cap = _["play_11"].format(
                        details["title"],
                        details["duration_min"],
                    )
                except Exception as yt_error:
                    LOGGER(_PLAY_LOG).warning("[PLAY] YouTube URL details failed: %s", yt_error)
                    if video:
                        return await mystic.edit_text("❌ Video ke liye YouTube details nahi milin. Doosra YouTube link ya video title try karo.")
                    sc = await Platform.soundcloud.search(f"https://www.youtube.com/watch?v={videoid}")
                    if not sc or not sc.get("url"):
                        return await mystic.edit_text("❌ Song nahi mila 💗")
                    duration_sec = int(sc.get("duration_sec") or 0)
                    if duration_sec > config.SONG_DOWNLOAD_DURATION_LIMIT:
                        return await mystic.edit_text("❌ Ye song 10 minutes se zyada hai, download nahi kar sakti 💗")
                    downloaded = await Platform.soundcloud.download(sc["url"])
                    if not downloaded:
                        return await mystic.edit_text("❌ Song nahi mila 💗")
                    details, track_path = downloaded
                    details["filepath"] = track_path
                    track_id = "soundcloud"
                    streamtype = "soundcloud"
                    img = config.SOUNCLOUD_IMG_URL
                    cap = _["play_11"].format(details["title"], details["duration_min"])
            else:
                try:
                    details, track_id = await Platform.youtube.track(url)
                    streamtype = "youtube"
                    img = details["thumb"]
                    cap = _["play_11"].format(
                        details["title"],
                        details["duration_min"],
                    )
                except Exception as yt_error:
                    LOGGER(_PLAY_LOG).warning("[PLAY] YouTube URL track failed: %s", yt_error)
                    if video:
                        return await mystic.edit_text("❌ Video ke liye YouTube details nahi milin. Doosra YouTube link ya video title try karo.")
                    sc = await Platform.soundcloud.search(url)
                    if not sc or not sc.get("url"):
                        return await mystic.edit_text("❌ Song nahi mila 💗")
                    duration_sec = int(sc.get("duration_sec") or 0)
                    if duration_sec > config.SONG_DOWNLOAD_DURATION_LIMIT:
                        return await mystic.edit_text("❌ Ye song 10 minutes se zyada hai, download nahi kar sakti 💗")
                    downloaded = await Platform.soundcloud.download(sc["url"])
                    if not downloaded:
                        return await mystic.edit_text("❌ Song nahi mila 💗")
                    details, track_path = downloaded
                    details["filepath"] = track_path
                    track_id = "soundcloud"
                    streamtype = "soundcloud"
                    img = config.SOUNCLOUD_IMG_URL
                    cap = _["play_11"].format(details["title"], details["duration_min"])
        elif await Platform.spotify.valid(url):
            spotify = True
            if not config.SPOTIFY_CLIENT_ID and not config.SPOTIFY_CLIENT_SECRET:
                return await mystic.edit_text(
                    "This Bot can't play spotify tracks and playlist, please contact my owner and ask him to add Spotify player."
                )
            if "track" in url:
                try:
                    details, track_id = await Platform.spotify.track(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "youtube"
                img = details["thumb"]
                cap = _["play_11"].format(details["title"], details["duration_min"])
            elif "playlist" in url:
                try:
                    details, plist_id = await Platform.spotify.playlist(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spplay"
                img = config.SPOTIFY_PLAYLIST_IMG_URL
                cap = _["play_12"].format(message.from_user.first_name)
            elif "album" in url:
                try:
                    details, plist_id = await Platform.spotify.album(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spalbum"
                img = config.SPOTIFY_ALBUM_IMG_URL
                cap = _["play_12"].format(message.from_user.first_name)
            elif "artist" in url:
                try:
                    details, plist_id = await Platform.spotify.artist(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spartist"
                img = config.SPOTIFY_ARTIST_IMG_URL
                cap = _["play_12"].format(message.from_user.first_name)
            else:
                return await mystic.edit_text(_["play_17"])
        elif await Platform.apple.valid(url):
            if "album" in url:
                try:
                    details, track_id = await Platform.apple.track(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "youtube"
                img = details["thumb"]
                cap = _["play_11"].format(details["title"], details["duration_min"])
            elif "playlist" in url:
                spotify = True
                try:
                    details, plist_id = await Platform.apple.playlist(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "apple"
                cap = _["play_13"].format(message.from_user.first_name)
                img = url
            else:
                return await mystic.edit_text(_["play_16"])
        elif await Platform.resso.valid(url):
            try:
                details, track_id = await Platform.resso.track(url)
            except Exception:
                return await mystic.edit_text(_["play_3"])
            streamtype = "youtube"
            img = details["thumb"]
            cap = _["play_11"].format(details["title"], details["duration_min"])
        elif await Platform.saavn.valid(url):
            if "shows" in url:
                return await mystic.edit_text(_["saavn_1"])

            elif await Platform.saavn.is_song(url):
                try:
                    file_path, details = await Platform.saavn.download(url)
                except Exception as e:
                    ex_type = type(e).__name__
                    LOGGER(__name__).error("An error occurred", exc_info=True)
                    return await mystic.edit_text(_["play_3"])
                duration_sec = details["duration_sec"]
                streamtype = "saavn_track"

                if duration_sec > config.DURATION_LIMIT:
                    return await mystic.edit_text(
                        _["play_6"].format(
                            config.DURATION_LIMIT_MIN,
                            details["duration_min"],
                        )
                    )
            elif await Platform.saavn.is_playlist(url):
                try:
                    details = await Platform.saavn.playlist(
                        url, limit=config.PLAYLIST_FETCH_LIMIT
                    )
                    streamtype = "saavn_playlist"
                except Exception as e:
                    ex_type = type(e).__name__
                    LOGGER(__name__).error("An error occurred", exc_info=True)
                    return await mystic.edit_text(_["play_3"])

                if len(details) == 0:
                    return await mystic.edit_text(_["play_3"])
            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    streamtype=streamtype,
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                if ex_type == "AssistantErr":
                    err = e
                else:
                    err = _["general_3"].format(ex_type)
                    LOGGER(__name__).error("An error occurred", exc_info=True)
                return await mystic.edit_text(err)
            return await mystic.delete()

        elif await Platform.soundcloud.valid(url):
            try:
                details, track_path = await Platform.soundcloud.download(url)
            except Exception:
                return await mystic.edit_text(_["play_3"])
            duration_sec = details["duration_sec"]
            if duration_sec > config.DURATION_LIMIT:
                return await mystic.edit_text(
                    _["play_6"].format(
                        config.DURATION_LIMIT_MIN,
                        details["duration_min"],
                    )
                )
            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    streamtype="soundcloud",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                if ex_type == "AssistantErr":
                    err = e
                else:
                    LOGGER(__name__).error("An error occurred", exc_info=True)
                    err = _["general_3"].format(ex_type)
                return await mystic.edit_text(err)
            return await mystic.delete()
        else:
            if not await Platform.telegram.is_streamable_url(url):
                return await mystic.edit_text(_["play_19"])

            await mystic.edit_text(_["str_2"])
            try:
                await stream(
                    _,
                    mystic,
                    message.from_user.id,
                    url,
                    chat_id,
                    message.from_user.first_name,
                    message.chat.id,
                    video=video,
                    streamtype="index",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                if ex_type == "AssistantErr":
                    err = e
                else:
                    LOGGER(__name__).error("An error occurred", exc_info=True)
                    err = _["general_3"].format(ex_type)
                return await mystic.edit_text(err)
            return await play_logs(message, streamtype="M3u8 or Index Link")
    else:
        if len(message.command) < 2:
            buttons = botplaylist_markup(_)
            return await mystic.edit_text(
                _["playlist_1"],
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        slider = True
        query = " ".join(message.command[1:])
        if "-v" in query:
            query = query.replace("-v", "")
        LOGGER(_PLAY_LOG).info(
            "[PLAY] YouTube search query='%s' (track call starting)", query[:80]
        )
        track_t0 = _time.monotonic()
        try:
            details, track_id = await Platform.youtube.track(query)
            LOGGER(_PLAY_LOG).info(
                "[PLAY] track() returned in %.1fs title=%s vidid=%s",
                _time.monotonic() - track_t0,
                details.get("title", "?")[:40],
                track_id,
            )
            streamtype = "youtube"
        except Exception as e:
            LOGGER(_PLAY_LOG).warning(
                "[PLAY] YouTube search failed after %.1fs: %s",
                _time.monotonic() - track_t0,
                e,
            )
            if video:
                try:
                    await notify_owner(
                        "VPlay YouTube search",
                        e,
                        f"query={query[:80]} user={user_id} chat={message.chat.id}",
                    )
                except Exception:
                    pass
                return await mystic.edit_text("❌ Is title ka YouTube video nahi mila. YouTube ka exact title ya link try karo.")

            spotify_result = False
            try:
                spotify_result = await Platform.spotify.search(query)
            except Exception as spotify_error:
                LOGGER(_PLAY_LOG).warning(
                    "[PLAY] Spotify metadata search failed: %s", spotify_error
                )

            fallback_query = query
            if spotify_result:
                fallback_query = spotify_result.get("query") or query
                LOGGER(
                    _PLAY_LOG,
                    "[PLAY] Spotify resolved query='%s'",
                    fallback_query[:100],
                )

            sc = await Platform.soundcloud.search(fallback_query)
            if not sc or not sc.get("url"):
                if fallback_query != query:
                    sc = await Platform.soundcloud.search(query)

            if not sc or not sc.get("url"):
                try:
                    await notify_owner(
                        "Play.track + Spotify/SoundCloud fallback",
                        e,
                        f"query={query[:80]} user={user_id} chat={message.chat.id}",
                    )
                except Exception:
                    pass
                return await mystic.edit_text("❌ Song nahi mila 💗")

            try:
                duration_sec = int(sc.get("duration_sec") or 0)
                if duration_sec > config.DURATION_LIMIT:
                    return await mystic.edit_text(
                        _["play_6"].format(config.DURATION_LIMIT_MIN, sc["duration_min"])
                    )
                downloaded = await Platform.soundcloud.download(sc["url"])
                if not downloaded:
                    return await mystic.edit_text("❌ Song nahi mila 💗")
                details, track_path = downloaded
                details["filepath"] = track_path
                streamtype = "soundcloud"
                track_id = "soundcloud"
                img = config.SOUNCLOUD_IMG_URL
                LOGGER(_PLAY_LOG).info(
                    "[PLAY] SoundCloud fallback selected: %s",
                    details.get("title", fallback_query)[:60],
                )
            except Exception as sc_error:
                LOGGER(_PLAY_LOG).error(
                    "[PLAY] SoundCloud fallback failed: %s", sc_error, exc_info=True
                )
                return await mystic.edit_text("❌ Song nahi mila 💗")
    if str(playmode) == "Direct" and not plist_type:
        if details["duration_min"]:
            duration_sec = time_to_seconds(details["duration_min"])
            if duration_sec > config.DURATION_LIMIT:
                return await mystic.edit_text(
                    _["play_6"].format(
                        config.DURATION_LIMIT_MIN,
                        details["duration_min"],
                    )
                )
        else:
            buttons = livestream_markup(
                _,
                track_id,
                user_id,
                "v" if video else "a",
                "c" if channel else "g",
                "f" if fplay else "d",
            )
            return await mystic.edit_text(
                _["play_15"],
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        try:
            LOGGER(_PLAY_LOG).info(
                "[PLAY] stream() call starting (Direct mode) vidid=%s",
                details.get("vidid", "?"),
            )
            stream_t0 = _time.monotonic()
            await stream(
                _,
                mystic,
                user_id,
                details,
                chat_id,
                user_name,
                message.chat.id,
                video=video,
                streamtype=streamtype,
                spotify=spotify,
                forceplay=fplay,
            )
            LOGGER(_PLAY_LOG).info(
                "[PLAY] stream() completed in %.1fs",
                _time.monotonic() - stream_t0,
            )
        except Exception as e:
            ex_type = type(e).__name__
            LOGGER(_PLAY_LOG).error(
                "[PLAY] stream() FAILED in %.1fs err=%s (%s)",
                _time.monotonic() - stream_t0,
                e,
                ex_type,
            )
            try:
                await notify_owner(
                    "Play.stream",
                    e,
                    f"vidid={details.get('vidid', '?')} user={user_id} chat={message.chat.id} type={ex_type}",
                )
            except Exception:
                pass
            if ex_type == "AssistantErr":
                err = e
            else:
                LOGGER(__name__).error("An error occurred", exc_info=True)

                err = _["general_3"].format(ex_type)
            return await mystic.edit_text(err)
        await mystic.delete()
        return await play_logs(
            message, streamtype=streamtype, thumbnail=details.get("thumb")
        )
    else:
        if plist_type:
            ran_hash = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            )
            lyrical[ran_hash] = plist_id
            buttons = playlist_markup(
                _,
                ran_hash,
                message.from_user.id,
                plist_type,
                "c" if channel else "g",
                "f" if fplay else "d",
            )
            await mystic.delete()
            await message.reply_photo(
                photo=img,
                caption=cap,
                reply_markup=InlineKeyboardMarkup(buttons),
                has_spoiler=True,
            )
            return await play_logs(
                message,
                streamtype=f"Playlist : {plist_type}",
                thumbnail=img,
            )
        else:
            if slider:
                buttons = slider_markup(
                    _,
                    track_id,
                    message.from_user.id,
                    query,
                    0,
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                await mystic.delete()
                await message.reply_photo(
                    photo=details["thumb"],
                    caption=_["play_11"].format(
                        details["title"].title(),
                        details["duration_min"],
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                    has_spoiler=True,
                )
                return await play_logs(
                    message,
                    streamtype=f"Searched on Youtube",
                    thumbnail=details.get("thumb"),
                )
            else:
                buttons = track_markup(
                    _,
                    track_id,
                    message.from_user.id,
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                await mystic.delete()
                await message.reply_photo(
                    photo=img,
                    caption=cap,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    has_spoiler=True,
                )
                return await play_logs(
                    message,
                    streamtype=f"URL Searched Inline",
                    thumbnail=img,
                )


# Dedicated video stream command. It intentionally does not reuse the audio
# fallback branch: it always downloads an actual video file and starts VC video.
@app.on_message(
    filters.group
    & filters.command(
        ["vstream", "vplay", "vplayforce", "videoplay"],
        prefixes=["/", "!", "%", ",", "@", "#"],
    )
    & ~BANNED_USERS
)
@PlayWrapper
async def dedicated_video_play_command(
    client,
    message: Message,
    _,
    chat_id,
    video,
    channel,
    playmode,
    url,
    fplay,
):
    user = message.from_user
    if not user:
        return

    if not await is_video_allowed(chat_id):
        text = "❌ Is group mein video streaming allowed nahi hai."
        return await message.reply_text(text, entities=premium_entities(text))

    args = getattr(message, "command", None) or []
    query = (url or " ".join(args[1:])).strip()
    if not query:
        text = "🎵 Use: /vstream song name"
        return await message.reply_text(text, entities=premium_entities(text))

    status = await message.reply_text(
        "🎵 YouTube par video search ho rahi hai...",
        entities=premium_entities("🎵 YouTube par video search ho rahi hai..."),
    )
    try:
        details, video_id = await Platform.youtube.track(query)
        title = (details.get("title") or query).strip()
        duration = details.get("duration_min")
        if not duration or str(duration).strip().lower() == "none":
            text = "❌ Video ki duration verify nahi hui, is liye download nahi ki."
            return await status.edit_text(text, entities=premium_entities(text))

        try:
            duration_seconds = int(time_to_seconds(str(duration)))
        except Exception:
            duration_seconds = 0
        limit_minutes = int(getattr(config, "SONG_DOWNLOAD_DURATION_LIMIT", 10) or 10)
        if duration_seconds <= 0:
            text = "❌ Video ki duration read nahi hui. Doosra YouTube title/link try karo."
            return await status.edit_text(text, entities=premium_entities(text))
        if duration_seconds > limit_minutes * 60:
            text = f"❌ {limit_minutes} minutes se lambi video download nahi hogi. Duration: {duration}"
            return await status.edit_text(text, entities=premium_entities(text))

        # Always clear any previous audio/video queue and leave its stream before
        # starting a replacement. video_dl() also removes stale media/temp files.
        try:
            await Ayush.stop_stream(chat_id)
        except Exception as stop_error:
            LOGGER(_PLAY_LOG).warning(
                "[VSTREAM] previous stream cleanup had an issue: %s", stop_error
            )

        downloading_text = (
            f"🥹 Video + audio download ho rahi hai...\n"
            f"🎵 {title}\n"
            f"⭐ Duration: {duration} (limit {limit_minutes} min)"
        )
        await status.edit_text(
            downloading_text,
            entities=premium_entities(downloading_text),
        )
        file_path, _direct = await Platform.youtube.download(
            video_id,
            status,
            video=True,
            videoid=True,
            title=title,
        )

        # yt-dlp can merge to a different extension than the selected stream's
        # metadata. Resolve the real completed video file before launching FFmpeg.
        os.makedirs("downloads", exist_ok=True)
        video_exts = (".mp4", ".mkv", ".webm", ".m4v", ".mov")
        if (
            not file_path
            or not os.path.isfile(file_path)
            or not str(file_path).lower().endswith(video_exts)
            or os.path.getsize(file_path) < 10240
        ):
            candidates = []
            for filename in os.listdir("downloads"):
                candidate = os.path.join("downloads", filename)
                if (
                    filename.startswith(f"{video_id}.")
                    and filename.lower().endswith(video_exts)
                    and os.path.isfile(candidate)
                    and os.path.getsize(candidate) >= 10240
                ):
                    candidates.append(candidate)
            if candidates:
                file_path = max(candidates, key=os.path.getmtime)
            else:
                raise RuntimeError("YouTube download finished but no valid video file was found")

        # Add the local file to the queue so the normal stream-end/stop cleanup
        # deletes it later. The queue type is explicitly 'video' (not audio).
        await put_queue(
            chat_id,
            message.chat.id,
            file_path,
            title,
            str(duration),
            user.mention,
            video_id,
            user.id,
            "video",
        )
        try:
            await Ayush.join_call(
                chat_id,
                message.chat.id,
                file_path,
                video=True,
                image=details.get("thumb"),
            )
        except Exception:
            # Remove queue entry and downloaded file if the VC could not start.
            try:
                await Ayush.stop_stream(chat_id)
            except Exception:
                try:
                    os.remove(file_path)
                except OSError:
                    pass
            raise

        caption = (
            f"🥰 Video download complete — VC par video play ho rahi hai!\n"
            f"🎵 {title}\n"
            f"⭐ Duration: {duration}\n"
            f"👤 Requested by: {user.first_name}"
        )
        thumb = details.get("thumb") or config.STREAM_IMG_URL
        card = await app.send_photo(
            message.chat.id,
            photo=thumb,
            caption=caption,
            caption_entities=premium_entities(caption),
            reply_markup=InlineKeyboardMarkup(stream_markup(_, video_id, chat_id)),
        )
        if db.get(chat_id):
            db[chat_id][0]["mystic"] = card
            db[chat_id][0]["markup"] = "stream"
        await status.edit_text(
            "🥰 Video download complete! VC mein video + audio start ho gaya.",
            entities=premium_entities("🥰 Video download complete! VC mein video + audio start ho gaya."),
        )
    except Exception as e:
        LOGGER(_PLAY_LOG).error("[VSTREAM] failed: %s", e, exc_info=True)
        try:
            await notify_owner(
                "VStream video download/playback",
                e,
                f"query={query[:100]} chat={message.chat.id} user={user.id}",
            )
        except Exception:
            pass
        error_text = f"❌ Video stream start nahi hui ({type(e).__name__}). YouTube title/link dobara try karo."
        try:
            await status.edit_text(error_text, entities=premium_entities(error_text))
        except Exception:
            pass
