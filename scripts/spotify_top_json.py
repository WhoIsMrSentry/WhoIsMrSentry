import os
import json
import base64
from typing import List, Dict

import requests

API_TOKEN = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"


def _access_token() -> str:
	cid = os.environ["SPOTIFY_CLIENT_ID"]
	csec = os.environ["SPOTIFY_CLIENT_SECRET"]
	refresh = os.environ["SPOTIFY_REFRESH_TOKEN"]
	resp = requests.post(
		API_TOKEN,
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


def _ignore_list() -> List[str]:
	raw = os.environ.get("SPOTIFY_IGNORE_ARTISTS", "[]")
	try:
		data = json.loads(raw)
		if isinstance(data, list):
			return [str(x).strip().lower() for x in data]
	except Exception:
		pass
	return []


def _blocked(track: Dict, ignore: List[str]) -> bool:
	arts = [a.get("name", "").lower() for a in track.get("artists", [])]
	return any(a in ignore for a in arts)


def build_json(token: str) -> Dict:
	ignore = _ignore_list()
	out = {"short_term": [], "medium_term": [], "long_term": []}
	for rng in ("short_term", "medium_term", "long_term"):
		data = _get(f"{API_BASE}/me/top/tracks", token, params={"time_range": rng, "limit": 30})
		items = data.get("items", [])
		for t in items:
			if _blocked(t, ignore):
				continue
			img = (t.get("album", {}).get("images") or [{}])[0].get("url", "")
			url = (t.get("external_urls") or {}).get("spotify", "")
			name = t.get("name", "")
			artists = [a.get("name", "") for a in t.get("artists", [])]
			# Spotify API top-tracks endpoint play count vermez; popularity var (0-100).
			popularity = t.get("popularity")
			out[rng].append({
				"name": name,
				"artists": artists,
				"image": img,
				"url": url,
				"play_count": None,  # bilinmiyor; ileride Last.fm ile zenginleştirilebilir
				"popularity": popularity,
			})
	return out


def main():
	token = _access_token()
	data = build_json(token)
	os.makedirs("docs", exist_ok=True)
	with open("docs/spotify_top.json", "w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
	main()

