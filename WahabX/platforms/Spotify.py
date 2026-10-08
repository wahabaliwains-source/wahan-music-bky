
# All rights reserved.
#

import re

import spotipy
from py_yt import VideosSearch
from spotipy.oauth2 import SpotifyClientCredentials

import config
from WahabX.utils.decorators import asyncify


class Spotify:
    def __init__(self):
        self.regex = r"^(https:\/\/open.spotify.com\/)(.*)$"
        self.client_id = config.SPOTIFY_CLIENT_ID
        self.client_secret = config.SPOTIFY_CLIENT_SECRET
        self.market = getattr(config, "SPOTIFY_MARKET", "US")
        self.spotify = None
        if self.client_id and self.client_secret:
            self.client_credentials_manager = SpotifyClientCredentials(
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            self.spotify = spotipy.Spotify(
                client_credentials_manager=self.client_credentials_manager
            )

    async def valid(self, link: str):
        if re.search(self.regex, link):
            return True
        else:
            return False


    async def search(self, query: str):
        """Search Spotify catalog metadata only; never download Spotify audio."""
        if not self.spotify or not query:
            return False

        def _search():
            result = self.spotify.search(
                q=query,
                type="track",
                market=self.market,
                limit=5,
            )
            tracks = result.get("tracks", {}).get("items", [])
            if not tracks:
                return False
            for track in tracks:
                artists = [a.get("name", "") for a in track.get("artists", [])]
                title = track.get("name") or ""
                if not title:
                    continue
                return {
                    "title": title,
                    "artists": artists,
                    "query": " ".join([title, *artists]).strip(),
                    "url": (track.get("external_urls") or {}).get("spotify"),
                    "duration_ms": track.get("duration_ms") or 0,
                    "thumb": ((track.get("album", {}).get("images") or [{}])[0]).get("url"),
                }
            return False

        return await asyncify(_search)()

    async def track(self, link: str):
        track = self.spotify.track(link)
        info = track["name"]
        for artist in track["artists"]:
            fetched = f' {artist["name"]}'
            if "Various Artists" not in fetched:
                info += fetched
        results = VideosSearch(info, limit=1)
        for result in (await results.next())["result"]:
            ytlink = result["link"]
            title = result["title"]
            vidid = result["id"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": ytlink,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    @asyncify
    def playlist(self, url: str) -> tuple:
        playlist = self.spotify.playlist(url)
        playlist_id = playlist["id"]
        results = []
        for item in playlist["tracks"]["items"]:
            music_track = item["track"]
            info = music_track["name"]
            for artist in music_track["artists"]:
                fetched = f' {artist["name"]}'
                if "Various Artists" not in fetched:
                    info += fetched
            results.append(info)
        return results, playlist_id

    @asyncify
    def album(self, url: str) -> tuple:
        album = self.spotify.album(url)
        album_id = album["id"]
        results = []
        for item in album["tracks"]["items"]:
            info = item["name"]
            for artist in item["artists"]:
                fetched = f' {artist["name"]}'
                if "Various Artists" not in fetched:
                    info += fetched
            results.append(info)
        return results, album_id

    @asyncify
    def artist(self, url: str) -> tuple:
        artist_info = self.spotify.artist(url)
        artist_id = artist_info["id"]
        results = []
        artist_top_tracks = self.spotify.artist_top_tracks(url)
        for item in artist_top_tracks["tracks"]:
            info = item["name"]
            for artist in item["artists"]:
                fetched = f' {artist["name"]}'
                if "Various Artists" not in fetched:
                    info += fetched
            results.append(info)
        return results, artist_id
