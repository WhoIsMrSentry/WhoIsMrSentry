#!/usr/bin/env python3
"""Download a fresh contribution streak SVG into assets/streak_stats.svg."""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = REPO_ROOT / "assets" / "streak_stats.svg"

USERNAME = os.environ.get("GITHUB_USERNAME", "WhoIsMrSentry")
STREAK_SOURCES = (
    "https://github-readme-streak-stats-eight.vercel.app/",
    "https://streak-stats.demolab.com/",
)

STREAK_OPTIONS = {
    "user": USERNAME,
    "theme": "dark",
    "background": "200009",
    "border": "88001b",
    "stroke": "88001b",
    "ring": "39FF14",
    "fire": "88001b",
    "currStreakLabel": "39FF14",
    "sideLabels": "E6FFE6",
    "currStreakNum": "E6FFE6",
    "sideNums": "E6FFE6",
    "dates": "E6FFE6",
    "disable_animations": "true",
}


def build_url(base: str) -> str:
    query = urllib.parse.urlencode(STREAK_OPTIONS)
    return f"{base}?{query}"


def download_streak_svg() -> bytes:
    last_error: Exception | None = None

    for base in STREAK_SOURCES:
        url = build_url(base)
        for attempt in range(1, 4):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "whoismrsentry-streak-updater/1.0"},
                )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    data = resp.read()
                if b"<svg" not in data:
                    raise RuntimeError(f"Unexpected response from {base}")
                return data
            except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
                last_error = exc
                print(f"WARN: streak fetch failed ({base}, attempt {attempt}): {exc}")
                time.sleep(2 * attempt)

    raise RuntimeError(f"Unable to download streak SVG: {last_error}")


def main() -> int:
    SVG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_bytes(download_streak_svg())
    print(f"Updated {SVG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
