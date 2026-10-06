
# All rights reserved.
#

from os import path

from yt_dlp import YoutubeDL

from WahabX.utils.decorators import asyncify
from WahabX.utils.formatters import seconds_to_min


class SoundCloud:
    def __init__(self):
        self.opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "format": "best",
            "retries": 3,
            "nooverwrites": False,
            "continuedl": True,
        }

    async def valid(self, link: str) -> bool:
        return "soundcloud" in link

    @asyncify
    def search(self, query: str) -> dict | bool:
        """Find the first SoundCloud track for a text query."""
        with YoutubeDL(self.opts) as ydl:
            try:
                info = ydl.extract_info(f"scsearch1:{query}", download=False)
                entries = (info or {}).get("entries") or []
                if not entries:
                    return False
                item = entries[0]
                duration = int(item.get("duration") or 0)
                return {
                    "url": item.get("webpage_url") or item.get("original_url") or item.get("url"),
                    "title": item.get("title") or query,
                    "duration_sec": duration,
                    "duration_min": seconds_to_min(duration),
                    "uploader": item.get("uploader") or "",
                }
            except Exception:
                return False

    @asyncify
    def download(self, url: str) -> dict | bool:
        with YoutubeDL(self.opts) as ydl:
            try:
                info = ydl.extract_info(url)
            except Exception:
                return False
            xyz = path.join("downloads", f"{info['id']}.{info['ext']}")
            duration_min = seconds_to_min(info["duration"])
            track_details = {
                "title": info["title"],
                "duration_sec": info["duration"],
                "duration_min": duration_min,
                "uploader": info["uploader"],
                "filepath": xyz,
            }
            return track_details, xyz
