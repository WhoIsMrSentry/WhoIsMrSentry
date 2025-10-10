import os
import json
import base64
import time
from typing import List, Dict, Optional

import requests

# This script updates README.md placeholders with Spotify data
# Features:
# - Current playlist (if playing from a playlist and public)
# - Recently played (carousel-like horizontal tiles)
# - Top of the week (short term top track)
# - Top tracks (short/mid/long)
# - Artist ignore list (repo secret SPOTIFY_IGNORE_ARTISTS as JSON array)
#
# Requirements (secrets):
# - SPOTIFY_CLIENT_ID
# - SPOTIFY_CLIENT_SECRET
# - SPOTIFY_REFRESH_TOKEN
# - SPOTIFY_USER_ID
# - SPOTIFY_IGNORE_ARTISTS (optional JSON array of names)
#
# Note: Carousel is simulated with a horizontally scrollable HTML div of album arts.

API_BASE = "https://api.spotify.com/v1"


def _token() -> str:
    cid = os.environ["SPOTIFY_CLIENT_ID"]
    csec = os.environ["SPOTIFY_CLIENT_SECRET"]
    refresh = os.environ["SPOTIFY_REFRESH_TOKEN"]
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh},
        headers={
            "Authorization": "Basic "
            + base64.b64encode(f"{cid}:{csec}".encode()).decode()
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _get(url: str, token: str, params: Optional[Dict] = None) -> Dict:
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def _get_ignore_list() -> List[str]:
    try:
        raw = os.environ.get("SPOTIFY_IGNORE_ARTISTS", "[]")
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x).strip().lower() for x in data]
    except Exception:
        pass
    return []


def _artist_blocked(track: Dict, ignore: List[str]) -> bool:
    artists = [a.get("name", "").lower() for a in track.get("artists", [])]
    return any(a in ignore for a in artists)


def current_playlist_html(token: str, user_id: str, ignore: List[str]) -> str:
    # Get current playing
    try:
        data = _get(f"{API_BASE}/me/player/currently-playing", token)
    except requests.HTTPError:
        return '<div><sub>No current playback.</sub></div>'

    if not data or not data.get("is_playing"):
        return '<div><sub>Not playing right now.</sub></div>'

    item = data.get("item") or {}
    # Do NOT filter in current playlist section (user requested it visible even if ignored in tops)

    context = data.get("context") or {}
    context_type = context.get("type")
    href = (context.get("external_urls") or {}).get("spotify") or data.get("item", {}).get("external_urls", {}).get("spotify", "")

    cover = ""
    if item.get("album", {}).get("images"):
        cover = item["album"]["images"][0]["url"]

    title = item.get("name", "Unknown")
    artist = ", ".join(a.get("name", "") for a in item.get("artists", []))
    subtitle = f"{artist}"
    label = "playlist" if context_type == "playlist" else "track"

    return (
        f'<div style="display:inline-flex;align-items:center;gap:12px">'
        f'<a href="{href}" target="_blank"><img src="{cover}" alt="cover" height="64" style="border:1px solid #88001b;border-radius:6px"/></a>'
        f'<div style="text-align:left">'
        f'<div><strong>{title}</strong></div>'
        f'<div><sub>{subtitle} • {label}</sub></div>'
        f'</div>'
        f'</div>'
    )


def recents_carousel_html(token: str, ignore: List[str], limit: int = 20) -> str:
    data = _get(f"{API_BASE}/me/player/recently-played", token, params={"limit": limit})
    items = data.get("items", [])
    # sort by most recent (already ordered), keep public contexts if any
    tiles = []
    for it in items:
        track = it.get("track", {})
        if not track:
            continue
        album = track.get("album", {})
        img = (album.get("images") or [{}])[0].get("url", "")
        url = (track.get("external_urls") or {}).get("spotify", "")
        title = track.get("name", "")
        tiles.append(
            f'<a href="{url}" target="_blank">'
            f'<img src="{img}" alt="{title}" height="84" width="84" '
            f'style="border:2px solid #88001b;border-radius:50%;object-fit:cover"/>'
            f'</a>'
        )

    if not tiles:
        return '<div><sub>No recent plays.</sub></div>'

    return (
        '<div style="display:flex;gap:8px;overflow-x:auto;padding:6px;scrollbar-width:thin">'
        + "".join(tiles)
        + "</div>"
    )


def top_tracks_html(token: str, ignore: List[str], term: str, limit: int = 10) -> str:
    data = _get(f"{API_BASE}/me/top/tracks", token, params={"time_range": term, "limit": limit})
    items = data.get("items", [])
    tiles = []
    for t in items:
        # Apply ignore only for top sections
        if _artist_blocked(t, ignore):
            continue
        album = t.get("album", {})
        img = (album.get("images") or [{}])[0].get("url", "")
        url = (t.get("external_urls") or {}).get("spotify", "")
        title = t.get("name", "")
        tiles.append(f'<a href="{url}" target="_blank"><img src="{img}" alt="{title}" height="96" style="border:2px solid #88001b;border-radius:6px"/></a>')

    if not tiles:
        return '<div><sub>No top tracks.</sub></div>'

    return (
        '<div style="display:flex;gap:10px;overflow-x:auto;padding:6px;scroll-snap-type:x mandatory">'
        + "".join(tiles)
        + "</div>"
    )


def update_readme(readme_path: str, token: str, user_id: str):
    ignore = _get_ignore_list()

    current_html = current_playlist_html(token, user_id, ignore)
    recents_html = recents_carousel_html(token, ignore, limit=50)
    top_short = top_tracks_html(token, ignore, term="short_term", limit=20)
    top_mid = top_tracks_html(token, ignore, term="medium_term", limit=20)
    top_long = top_tracks_html(token, ignore, term="long_term", limit=20)

    # Top of the week = first of short-term list (if any)
    top_week = '<div><sub>No data.</sub></div>'
    try:
        data = _get(f"{API_BASE}/me/top/tracks", token, params={"time_range": "short_term", "limit": 1})
        items = data.get("items", [])
        if items and not _artist_blocked(items[0], ignore):
            t = items[0]
            img = (t.get("album", {}).get("images") or [{}])[0].get("url", "")
            url = (t.get("external_urls") or {}).get("spotify", "")
            title = t.get("name", "")
            artist = ", ".join(a.get("name", "") for a in t.get("artists", []))
            top_week = (
                f'<div style="display:inline-flex;align-items:center;gap:12px">'
                f'<a href="{url}" target="_blank"><img src="{img}" alt="{title}" height="72" style="border:2px solid #88001b;border-radius:6px"/></a>'
                f'<div style="text-align:left">'
                f'<div><strong>{title}</strong></div>'
                f'<div><sub>{artist}</sub></div>'
                f'</div>'
                f'</div>'
            )
    except Exception:
        pass

    def _replace(section: str, new_html: str, text: str) -> str:
        start = f"<!-- {section}:START -->"
        end = f"<!-- {section}:END -->"
        if start in text and end in text:
            return text.split(start)[0] + start + "\n" + new_html + "\n" + end + text.split(end)[1]
        return text

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = _replace("SPOTIFY_CURRENT_PLAYLIST", current_html, content)
    content = _replace("SPOTIFY_RECENTS", recents_html, content)
    content = _replace("SPOTIFY_TOP_OF_WEEK", top_week, content)
    content = _replace("SPOTIFY_TOP_SHORT", top_short, content)
    content = _replace("SPOTIFY_TOP_MID", top_mid, content)
    content = _replace("SPOTIFY_TOP_LONG", top_long, content)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    token = _token()
    update_readme(readme_path=os.environ.get("README_PATH", "README.md"), token=token, user_id=os.environ.get("SPOTIFY_USER_ID", ""))
