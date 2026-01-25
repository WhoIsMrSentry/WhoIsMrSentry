#!/usr/bin/env python3
import json
import re
import sys
import urllib.request
from pathlib import Path


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "WhoIsMrSentry-profile-views-total/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_count_from_komarev_svg(svg: str) -> int:
    # Komarev returns an SVG badge; the count is rendered as text.
    # Make extraction resilient: grab any digit groups (allowing commas),
    # then fall back to previous heuristics if needed.
    candidates = re.findall(r"[\d,]+", svg)
    values: list[int] = []
    for c in candidates:
        try:
            values.append(int(c.replace(",", "")))
        except ValueError:
            pass

    if not values:
        # Older fallback: try to capture numbers inside <text> nodes explicitly
        candidates = re.findall(r">\s*([0-9][0-9,]*)\s*<\/text>", svg)
        for c in candidates:
            try:
                values.append(int(c.replace(",", "")))
            except ValueError:
                pass

    if not values:
        raise ValueError("Could not parse any numeric count from SVG")

    return max(values)


def write_shields_endpoint_json(path: Path, total: int) -> None:
    payload = {
        "schemaVersion": 1,
        "label": "Total Visitors",
        "message": str(total),
        "color": "88001b",
        "labelColor": "000000",
        "style": "for-the-badge",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    # Current + legacy handles
    usernames = ["WhoIsMrSentry", "SentryCoderDev"]

    totals = []
    for u in usernames:
        url = f"https://komarev.com/ghpvc/?username={u}&style=flat-square&color=88001b"
        svg = fetch_text(url)
        count = extract_count_from_komarev_svg(svg)
        totals.append(count)

    total = sum(totals)
    out_path = Path("assets") / "profile_views_total.json"
    write_shields_endpoint_json(out_path, total)
    print(f"Wrote {out_path} with total={total} (components={totals})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
