import os
import json
import base64
import math
from typing import List, Dict

import requests

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


def _get(url: str, token: str, params: Dict = None) -> Dict:
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=20)
    if r.status_code == 204 or not r.content:
        return {}
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
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


def _image_data_uri(url: str) -> str:
    try:
        rr = requests.get(url, timeout=20)
        rr.raise_for_status()
        # Best effort detect type
        ctype = rr.headers.get("Content-Type", "image/jpeg")
        b64 = base64.b64encode(rr.content).decode()
        return f"data:{ctype};base64,{b64}"
    except Exception:
        return ""


def fetch_top_tracks(token: str, term: str, limit: int, ignore: List[str]) -> List[Dict]:
    data = _get(f"{API_BASE}/me/top/tracks", token, params={"time_range": term, "limit": limit})
    items = data.get("items", [])
    out = []
    for t in items:
        if _artist_blocked(t, ignore):
            continue
        album = t.get("album", {})
        imgs = album.get("images") or []
        img_url = imgs[1]["url"] if len(imgs) > 1 else (imgs[0]["url"] if imgs else "")
        out.append({
            "title": t.get("name", ""),
            "artist": ", ".join(a.get("name", "") for a in t.get("artists", [])),
            "img": _image_data_uri(img_url),
            "url": (t.get("external_urls") or {}).get("spotify", ""),
        })
    return out


def build_svg(tracks: List[Dict], width: int = 800, height: int = 320) -> str:
    cx, cy = width // 2, height // 2
    radius = 110
    item_size = 80
    stroke = "#88001b"
    bg = "#000000"

    # Wheel group with rotation animation
    wheel_items = []
    n = max(1, len(tracks))
    for i, t in enumerate(tracks):
        angle = (2 * math.pi * i) / n
        x = cx + radius * math.cos(angle) - item_size / 2
        y = cy + radius * math.sin(angle) - item_size / 2
        href = t.get("img", "")
        title = (t.get("title") or "").replace("&", "&amp;")
        url = t.get("url", "")
        if not href:
            continue
        wheel_items.append(
            f'<a xlink:href="{url}" target="_blank">'
            f'<image href="{href}" x="{x:.1f}" y="{y:.1f}" width="{item_size}" height="{item_size}" '
            f'style="clip-path: circle(50% at 50% 50%);" />'
            f'<circle cx="{x+item_size/2:.1f}" cy="{y+item_size/2:.1f}" r="{item_size/2:.1f}" fill="none" stroke="{stroke}" stroke-width="2" />'
            f'</a>'
        )

    # Titles line
    titles = " • ".join((t.get("title") or "").replace("&", "&amp;") for t in tracks[:10])

    svg = f"""
<svg xmlns=\"http://www.w3.org/2000/svg\" xmlns:xlink=\"http://www.w3.org/1999/xlink\" width=\"{width}\" height=\"{height}\" viewBox=\"0 0 {width} {height}\">
  <rect x=\"0\" y=\"0\" width=\"{width}\" height=\"{height}\" rx=\"12\" ry=\"12\" fill=\"{bg}\" stroke=\"{stroke}\" stroke-width=\"2\"/>
  <g transform=\"rotate(0 {cx} {cy})\">
    {''.join(wheel_items)}
    <animateTransform attributeName=\"transform\" attributeType=\"XML\" type=\"rotate\" from=\"0 {cx} {cy}\" to=\"360 {cx} {cy}\" dur=\"40s\" repeatCount=\"indefinite\"/>
  </g>
  <text x=\"{width-12}\" y=\"24\" fill=\"#fff\" font-size=\"14\" text-anchor=\"end\" font-family=\"Segoe UI, Roboto, Arial, sans-serif\">Top Tracks</text>
  <text x=\"{width/2}\" y=\"{height-16}\" fill=\"#ddd\" font-size=\"12\" text-anchor=\"middle\" font-family=\"Segoe UI, Roboto, Arial, sans-serif\">{titles}</text>
</svg>
"""
    return svg


def write_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def generate_all():
    token = _token()
    ignore = _get_ignore_list()
    cfg = [
        ("short", "short_term"),
        ("mid", "medium_term"),
        ("long", "long_term"),
    ]
    for label, term in cfg:
        items = fetch_top_tracks(token, term=term, limit=12, ignore=ignore)
        svg = build_svg(items)
        out = os.path.join("assets", f"top_{label}.svg")
        write_file(out, svg)


if __name__ == "__main__":
    generate_all()
