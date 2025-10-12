import os
import json
import base64
import time
from typing import List, Dict, Optional
import math

import requests

# This script updates README.md placeholders with Spotify data
# Features:
# - Playlists grid (half selectable)
# - Artist ignore list (still supported but used in tops previously)
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
THUMB_SIZE = int(os.environ.get("SPOTIFY_THUMB_SIZE", "250"))
SPACER_IMG = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if raw.isdigit():
        value = int(raw)
        return value if value > 0 else default
    return default


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
    r = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=20,
    )
    # 204 No Content: Spotify returns this when nothing is playing
    if r.status_code == 204 or not r.content:
        return {}
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        # Unexpected empty/non-JSON body
        return {}


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
    # Kept for potential future use; not used in the simplified README flow
    try:
        data = _get(f"{API_BASE}/me/player/currently-playing", token)
    except requests.HTTPError:
        return ''
    if not data or not data.get("is_playing"):
        return ''
    item = data.get("item") or {}
    href = (item.get("external_urls") or {}).get("spotify", "")
    cover = (item.get("album", {}).get("images") or [{}])[0].get("url", "")
    title = item.get("name", "")
    artist = ", ".join(a.get("name", "") for a in item.get("artists", []))
    return (
        f'<div style="display:inline-flex;align-items:center;gap:12px">'
        f'<a href="{href}" target="_blank"><img src="{cover}" alt="cover" height="64" style="border:1px solid #88001b;border-radius:6px"/></a>'
        f'<div style="text-align:left">'
        f'<div><strong>{title}</strong></div>'
        f'<div><sub>{artist}</sub></div>'
        f'</div>'
        f'</div>'
    )


def recents_carousel_html(token: str, ignore: List[str], limit: int = 20) -> str:
    return ''


def top_tracks_html(token: str, ignore: List[str], term: str, limit: int = 10) -> str:
    return ''


def playlists_html(token: str, user_id: Optional[str] = None) -> str:
    # Fetch playlists with fallback:
    # 1) /me/playlists (requires OAuth; returns public + private if scoped)
    # 2) /users/{user_id}/playlists (returns public playlists for that user)

    def _fetch_all(url: str) -> List[Dict]:
        items: List[Dict] = []
        limit = 50
        offset = 0
        while True:
            data = _get(url, token, params={"limit": limit, "offset": offset})
            batch = data.get("items", [])
            if not batch:
                break
            items.extend(batch)
            if not data.get("next"):
                break
            offset += limit
        return items

    items: List[Dict] = []
    try:
        items = _fetch_all(f"{API_BASE}/me/playlists")
    except requests.HTTPError:
        items = []

    if not items and user_id:
        try:
            items = _fetch_all(f"{API_BASE}/users/{user_id}/playlists")
        except requests.HTTPError:
            items = []

    if not items:
        return '<div><sub>No playlists found.</sub></div>'

    n = len(items)
    half = os.environ.get("SPOTIFY_PLAYLIST_HALF", "all").lower().strip()
    mid = math.ceil(n / 2)
    if half == "first":
        chosen = items[:mid]
    elif half == "second":
        chosen = items[mid:]
    else:
        chosen = items

    # Optional cap
    cols_hint = _int_env("SPOTIFY_PLAYLIST_COLS", 5)
    rows_hint = _int_env("SPOTIFY_PLAYLIST_ROWS", 4)
    raw_max = os.environ.get("SPOTIFY_PLAYLIST_MAX", "").strip()
    if raw_max.isdigit():
        max_items = int(raw_max)
    else:
        max_items = cols_hint * rows_hint if rows_hint > 0 else cols_hint * 4
    max_items = max_items if max_items > 0 else 20
    chosen = chosen[:max_items]

    n = len(chosen)
    if n == 0:
        return '<div><sub>No playlists found.</sub></div>'

    cols = max(1, min(cols_hint, n))

    # Build an HTML table without relying on CSS that GitHub may strip.
    # Use <img width="140" height="140"> so thumbnails always render.
    rows_html: List[str] = []
    for r_start in range(0, n, cols):
        row_items = chosen[r_start:r_start + cols]
        tds: List[str] = []
        for p in row_items:
            name = p.get("name", "")
            url = (p.get("external_urls") or {}).get("spotify", "")
            img = ((p.get("images") or [{}])[0]).get("url", "")
            cell_html = (
                f'<a href="{url}" target="_blank">'
                f'<img src="{img}" alt="{name}" width="{THUMB_SIZE}" height="{THUMB_SIZE}" '
                f'style="width:{THUMB_SIZE}px;height:{THUMB_SIZE}px;object-fit:cover;border:1px solid #52000f;background-color:#1a0006;" />'
                f'</a>'
                f'<div style="max-width:{THUMB_SIZE}px;word-wrap:break-word"><sub>{name}</sub></div>'
            )
            tds.append(f'<td align="center" valign="top">{cell_html}</td>')
        while len(tds) < cols:
            tds.append(
                f'<td align="center" valign="top">'
                f'<img src="{SPACER_IMG}" width="{THUMB_SIZE}" height="{THUMB_SIZE}" '
                f'style="width:{THUMB_SIZE}px;height:{THUMB_SIZE}px;opacity:0;" />'
                f'</td>'
            )
        rows_html.append('<tr>' + ''.join(tds) + '</tr>')

    table = '<div align="center"><table>' + ''.join(rows_html) + '</table></div>'
    return table


def update_readme(readme_path: str, token: str, user_id: str):
    # Only update playlists block as requested
    playlists = playlists_html(token, user_id=user_id or None)

    def _replace(section: str, new_html: str, text: str) -> str:
        start = f"<!-- {section}:START -->"
        end = f"<!-- {section}:END -->"
        if start in text and end in text:
            # Replace content between markers
            before = text.split(start)[0]
            after = text.split(end)[1]
            return before + start + "\n" + new_html + "\n" + end + after
        # If markers missing, try to inject after '## Playlists' header
        insertion = start + "\n" + new_html + "\n" + end
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.strip().lower().startswith("## playlists"):
                # insert after this header and a blank line if present
                insert_at = i + 1
                # skip any empty line directly after header
                while insert_at < len(lines) and lines[insert_at].strip() == "":
                    insert_at += 1
                return "\n".join(lines[:insert_at] + ["", insertion, ""] + lines[insert_at:])
        # Otherwise append at the end
        return text.rstrip() + "\n\n" + insertion + "\n"

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = _replace("SPOTIFY_PLAYLISTS", playlists, content)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    token = _token()
    update_readme(readme_path=os.environ.get("README_PATH", "README.md"), token=token, user_id=os.environ.get("SPOTIFY_USER_ID", ""))
