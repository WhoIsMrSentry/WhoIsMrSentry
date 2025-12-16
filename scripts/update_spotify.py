#!/usr/bin/env python3
"""Update the Spotify snippet inside README.md with the latest track and playlist info."""

from __future__ import annotations

import base64
import html
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional

ROOT = pathlib.Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
MARKER_START = "<!-- SPOTIFY_SECTION:START -->"
MARKER_END = "<!-- SPOTIFY_SECTION:END -->"
PLACEHOLDER = "<p style=\"margin:0;\"><em>Unable to pull Spotify data right now.</em></p>"


class SpotifyConfigError(RuntimeError):
    """Raised when required Spotify configuration is missing."""


def _require_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise SpotifyConfigError(f"Missing required environment variable: {key}")
    return value.strip()


def _fetch_json(url: str, headers: Dict[str, str], data: Optional[bytes] = None) -> Dict[str, Any]:
    request = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    for header, header_value in headers.items():
        request.add_header(header, header_value)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = response.read()
            if not payload:
                return {}
            return json.loads(payload.decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - network layer
        if exc.code in (202, 204, 304):
            return {}
        if exc.code == 404:
            return {}
        raise


def _build_token() -> str:
    client_id = _require_env("SPOTIFY_CLIENT_ID")
    client_secret = _require_env("SPOTIFY_CLIENT_SECRET")
    refresh_token = _require_env("SPOTIFY_REFRESH_TOKEN")

    auth = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")
    payload = _fetch_json("https://accounts.spotify.com/api/token", headers, body)
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Spotify token response did not include access_token")
    return token


def _fetch_current_payload(headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    url = "https://api.spotify.com/v1/me/player/currently-playing"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read()
            if not data:
                return None
            payload = json.loads(data.decode("utf-8"))
            if payload.get("item"):
                payload["_source"] = "now"
                return payload
            return None
    except urllib.error.HTTPError as exc:  # pragma: no cover - network layer
        if exc.code in (202, 204, 404):
            return None
        raise


def _fetch_recent_payload(headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    url = "https://api.spotify.com/v1/me/player/recently-played?limit=1"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read()
            if not data:
                return None
            payload = json.loads(data.decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - network layer
        if exc.code == 404:
            return None
        raise

    items = payload.get("items") or []
    if not items:
        return None
    normalized = {
        "item": items[0].get("track"),
        "context": items[0].get("context"),
        "played_at": items[0].get("played_at"),
        "_source": "recent",
    }
    return normalized


def _retrieve_payload(access_token: str) -> Optional[Dict[str, Any]]:
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = _fetch_current_payload(headers)
    if payload:
        return payload
    return _fetch_recent_payload(headers)


def _extract_track(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    item = payload.get("item")
    if not item:
        return None
    artists = [artist.get("name") for artist in item.get("artists", []) if artist.get("name")]
    album = item.get("album") or {}
    album_images = album.get("images") or []
    album_url = (album.get("external_urls") or {}).get("spotify")
    track_url = (item.get("external_urls") or {}).get("spotify")

    return {
        "name": item.get("name") or "Unknown Track",
        "artists": ", ".join(artists) or "Unknown Artist",
        "url": track_url or album_url or "https://open.spotify.com",
        "album": album.get("name") or "Unknown Collection",
        "album_url": album_url or track_url or "https://open.spotify.com",
        "cover": album_images[0]["url"] if album_images else None,
    }


def _fetch_playlist(headers: Dict[str, str], context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not context or context.get("type") != "playlist":
        return None

    href = context.get("href")
    if not href:
        uri = context.get("uri", "")
        if uri.startswith("spotify:playlist:"):
            playlist_id = uri.split(":")[-1]
            href = f"https://api.spotify.com/v1/playlists/{playlist_id}"
    if not href:
        return None

    request = urllib.request.Request(href, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - network layer
        if exc.code in (401, 403, 404):
            return None
        raise

    images = payload.get("images") or []
    external = (payload.get("external_urls") or {}).get("spotify")
    return {
        "name": payload.get("name") or "Unnamed Playlist",
        "url": external or "https://open.spotify.com",
        "image": images[0]["url"] if images else None,
    }


def _build_playlist(headers: Dict[str, str], payload: Dict[str, Any], track: Dict[str, Any]) -> Dict[str, Any]:
    playlist = _fetch_playlist(headers, payload.get("context"))
    if playlist:
        return playlist
    # Fallback to album/collection visuals when no playlist context is available.
    return {
        "name": track["album"],
        "url": track["album_url"],
        "image": track.get("cover"),
    }


def _format_html(track: Dict[str, Any], playlist: Dict[str, Any], payload: Dict[str, Any]) -> str:
    track_name = html.escape(track["name"])
    artists = html.escape(track["artists"])
    track_url = html.escape(track["url"])
    playlist_name = html.escape(playlist["name"])
    playlist_url = html.escape(playlist["url"])
    track_cover = html.escape(track.get("cover") or "https://placehold.co/300x300/1a0006/ffffff?text=Track")
    playlist_cover = html.escape(playlist.get("image") or track.get("cover") or "https://placehold.co/300x300/1a0006/ffffff?text=Playlist")
    status_label = "Now Playing" if payload.get("_source") == "now" else "Last Played"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return (
        '<div style="color:#f5f5f5;text-align:center;">\n'
        f'  <p style="margin:0 0 2px 0;font-size:14px;letter-spacing:0.2em;text-transform:uppercase;color:#a8ff60;">{status_label}</p>\n'
        f'  <p style="margin:0 0 8px 0;font-size:21px;font-weight:700;">'
        f'<a href="{track_url}" style="color:#f5f5f5;text-decoration:none;">{track_name}</a></p>\n'
        f'  <p style="margin:0 0 14px 0;font-size:16px;color:#d8d8d8;">{artists}</p>\n'
        f'  <p style="margin:0 0 4px 0;font-size:13px;letter-spacing:0.3em;text-transform:uppercase;color:#ffb3c1;">Playlist</p>\n'
        f'  <p style="margin:0 0 20px 0;font-size:18px;font-weight:600;">'
        f'<a href="{playlist_url}" style="color:#f5f5f5;text-decoration:none;">{playlist_name}</a></p>\n'
        '  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:28px;align-items:start;max-width:700px;margin:0 auto;">\n'
        f'    <a href="{track_url}" title="Listen to {track_name}" '
        'style="display:block;border-radius:24px;overflow:hidden;background:#0b0005;border:2px solid #39ff14;box-shadow:0 12px 30px rgba(57,255,20,0.25);text-decoration:none;">\n'
        f'      <img src="{track_cover}" alt="{track_name} cover art" '
        'style="display:block;width:100%;aspect-ratio:4/5;object-fit:cover;" />\n'
        '      <div style="padding:12px 18px 18px;text-align:left;">\n'
        '        <p style="margin:0;font-size:12px;letter-spacing:0.35em;text-transform:uppercase;color:#a8ff60;">Track Art</p>\n'
        '      </div>\n'
        '    </a>\n'
        f'    <a href="{playlist_url}" title="Open {playlist_name}" '
        'style="display:block;border-radius:24px;overflow:hidden;background:#0b0005;border:2px solid #ff0047;box-shadow:0 12px 30px rgba(255,0,71,0.25);text-decoration:none;">\n'
        f'      <img src="{playlist_cover}" alt="{playlist_name} artwork" '
        'style="display:block;width:100%;aspect-ratio:4/5;object-fit:cover;" />\n'
        '      <div style="padding:12px 18px 18px;text-align:left;">\n'
        '        <p style="margin:0;font-size:12px;letter-spacing:0.35em;text-transform:uppercase;color:#ff86a7;">Playlist Art</p>\n'
        '      </div>\n'
        '    </a>\n'
        '  </div>\n'
        f'  <p style="margin-top:16px;font-size:12px;color:#bbbbbb;"><em>Updated {timestamp}</em></p>\n'
        '</div>'
    )


def _update_readme(html_block: str) -> None:
    content = README_PATH.read_text(encoding="utf-8")
    start_index = content.find(MARKER_START)
    end_index = content.find(MARKER_END)
    if start_index == -1 or end_index == -1:
        raise RuntimeError("Spotify markers not found in README.md")

    new_content = (
        content[: start_index + len(MARKER_START)]
        + "\n"
        + html_block
        + "\n"
        + content[end_index:]
    )

    if new_content != content:
        README_PATH.write_text(new_content, encoding="utf-8")


def main() -> None:
    try:
        token = _build_token()
        payload = _retrieve_payload(token)
    except SpotifyConfigError as exc:
        print(exc)
        _update_readme(PLACEHOLDER)
        sys.exit(0)

    headers = {"Authorization": f"Bearer {token}"}
    if not payload:
        _update_readme(PLACEHOLDER)
        return

    track = _extract_track(payload)
    if not track:
        _update_readme(PLACEHOLDER)
        return

    playlist = _build_playlist(headers, payload, track)
    html_block = _format_html(track, playlist, payload)
    _update_readme(html_block)


if __name__ == "__main__":
    main()
