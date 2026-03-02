#!/usr/bin/env python3
import re
import time
import urllib.request
from pathlib import Path


README_PATH = Path("README.md")


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "WhoIsMrSentry-profile-views-badge/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_count_from_komarev_svg(svg: str) -> int:
    m = re.search(r"data-count=\"([0-9][0-9,]*)\"", svg)
    if m:
        return int(m.group(1).replace(",", ""))

    candidates = re.findall(r"<text[^>]*>\s*([0-9][0-9,]*)\s*</text>", svg)
    values: list[int] = []
    for candidate in candidates:
        try:
            values.append(int(candidate.replace(",", "")))
        except ValueError:
            pass

    if not values:
        raise ValueError("Could not parse profile views count from Komarev SVG")

    return max(values)


def build_badge_url(count: int) -> str:
    return (
        "https://img.shields.io/badge/"
        f"Profile%20Views-{count}-88001b"
        "?style=for-the-badge&labelColor=000000"
    )


def update_readme_badge(count: int) -> bool:
    text = README_PATH.read_text(encoding="utf-8")
    new_url = build_badge_url(count)

    pattern = r'(<img\s+src=")[^"]+(" alt="Profile Views \(All Time\)"[^>]*>)'
    new_text, replaced = re.subn(pattern, rf"\1{new_url}\2", text, count=1)
    if replaced == 0:
        raise RuntimeError("Profile Views badge not found in README.md")

    if new_text != text:
        README_PATH.write_text(new_text, encoding="utf-8")
        return True
    return False


def main() -> int:
    username = "WhoIsMrSentry"
    cache_bust = int(time.time())
    komarev_url = (
        f"https://komarev.com/ghpvc/?username={username}"
        f"&style=flat-square&color=88001b&cb={cache_bust}"
    )

    svg = fetch_text(komarev_url)
    count = extract_count_from_komarev_svg(svg)
    changed = update_readme_badge(count)
    print(f"Profile Views count={count}; README changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
