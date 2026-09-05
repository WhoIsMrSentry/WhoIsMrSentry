#!/usr/bin/env python3
import json
import re
import sys
import urllib.request
from pathlib import Path


PROFILE_VIEWS_URL = (
    "https://visitor-badge.laobi.icu/badge?"
    "page_id=WhoIsMrSentry.WhoIsMrSentry&left_text=Profile%20Views"
)


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "WhoIsMrSentry-profile-views-json/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_count(svg: str) -> int:
    numbers = re.findall(r">([0-9][0-9,]*)<", svg)
    values: list[int] = []
    for num in numbers:
        try:
            values.append(int(num.replace(",", "")))
        except ValueError:
            pass

    if not values:
        raise RuntimeError("Could not parse profile views count from visitor badge SVG")

    return max(values)


def write_shields_endpoint_json(path: Path, count: int) -> None:
    payload = {
        "schemaVersion": 1,
        "label": "Profile Views",
        "message": str(count),
        "color": "88001b",
        "labelColor": "000000",
        "style": "for-the-badge",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    out_path = Path("assets") / "profile_views.json"
    try:
        svg = fetch_text(PROFILE_VIEWS_URL)
        count = extract_count(svg)
        write_shields_endpoint_json(out_path, count)
        print(f"Wrote {out_path} with profile_views={count}")
        return 0
    except Exception as exc:
        print(
            f"WARN: Could not fetch profile views from visitor badge ({exc}). "
            "Preserving previous value if available.",
            file=sys.stderr,
        )
        if not out_path.exists():
            write_shields_endpoint_json(out_path, 0)
            print(f"Wrote fallback {out_path} with profile_views=0")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
