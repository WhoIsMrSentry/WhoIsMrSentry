import os
import json
import base64
from typing import Dict, List

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


def _get(url: str, token: str, params: Dict | None = None) -> Dict:
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=20)
    if r.status_code == 204 or not r.content:
        return {}
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        return {}


def _recent_counts(token: str) -> Dict[str, int]:
    # Count last 50 recently played occurrences per track id
    data = _get(f"{API_BASE}/me/player/recently-played", token, params={"limit": 50})
    counts: Dict[str, int] = {}
    for item in data.get("items", []):
        tid = (item.get("track") or {}).get("id")
        if not tid:
            continue
        counts[tid] = counts.get(tid, 0) + 1
    return counts


def _top_tracks(token: str, term: str, limit: int = 12) -> List[Dict]:
    data = _get(f"{API_BASE}/me/top/tracks", token, params={"time_range": term, "limit": limit})
    items = []
    for idx, t in enumerate(data.get("items", []), start=1):
        items.append(
            {
                "id": t.get("id"),
                "rank": idx,
                "name": t.get("name", ""),
                "artists": ", ".join(a.get("name", "") for a in t.get("artists", [])),
                "url": (t.get("external_urls") or {}).get("spotify", ""),
                "image": ((t.get("album") or {}).get("images") or [{}])[0].get("url", ""),
            }
        )
    return items


def main():
    token = _token()
    counts = _recent_counts(token)
    payload = {}
    for term in ["short_term", "medium_term", "long_term"]:
        items = _top_tracks(token, term, limit=12)
        for it in items:
            it["recentCount"] = counts.get(it.get("id") or "", 0)
        payload[term] = items

    os.makedirs("docs", exist_ok=True)
    with open("docs/spotify_top.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
