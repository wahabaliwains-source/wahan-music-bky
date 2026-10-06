# All rights reserved.
#
# Centralized cleanup for downloaded playback files.

import glob
import os
import re

from config import autoclean
from WahabX.utils.decorators import asyncify


_YOUTUBE_QUEUE_RE = re.compile(r"^vid_([A-Za-z0-9_-]+)$")


def _remove_file(path: str) -> None:
    try:
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass


def _cleanup_one(rem: str) -> None:
    try:
        if rem in autoclean:
            autoclean.remove(rem)
    except Exception:
        pass

    # YouTube queue entries use vid_<video_id> as a logical queue key,
    # while the real downloaded files are downloads/<video_id>.*.
    match = _YOUTUBE_QUEUE_RE.match(str(rem))
    if match:
        video_id = match.group(1)
        for path in glob.glob(os.path.join("downloads", f"{video_id}.*")):
            _remove_file(path)
        for path in glob.glob(os.path.join("downloads", f"{video_id}_*")):
            _remove_file(path)
        return

    # Never remove live/direct stream placeholders.
    if any(token in str(rem) for token in ("vid_", "live_", "index_")):
        return

    _remove_file(str(rem))


@asyncify
def auto_clean(popped):
    if isinstance(popped, dict):
        _cleanup_one(popped.get("file", ""))
    elif isinstance(popped, list):
        for item in popped:
            if isinstance(item, dict):
                _cleanup_one(item.get("file", ""))
    else:
        raise ValueError("Expected popped to be a dict or list.")
