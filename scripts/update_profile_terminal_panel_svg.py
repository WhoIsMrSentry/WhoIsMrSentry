#!/usr/bin/env python3
"""Refresh assets/profile_terminal_panel.svg with live GitHub statistics."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = REPO_ROOT / "assets" / "profile_terminal_panel.svg"

USERNAME = os.environ.get("GITHUB_USERNAME", "WhoIsMrSentry")
TOTAL_REPOS = os.environ.get("TOTAL_REPOS", "76")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

LABEL_X = 350
CHAR_W = 10.8

STAT_ROWS: tuple[tuple[str, str, int], ...] = (
    ("Repos:", "repos", 394),
    ("Public Repos:", "public_repos", 420),
    ("Contributions:", "contributions", 446),
    ("Followers:", "followers", 472),
    ("Pull Requests:", "pull_requests", 498),
    ("Commits:", "commits", 524),
)


def value_x(label: str) -> int:
    return round(LABEL_X + len(label) * CHAR_W)


def http_json(url: str) -> dict:
    headers = {
        "User-Agent": "whoismrsentry-profile-terminal-panel",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_user_profile() -> dict:
    return http_json(f"https://api.github.com/users/{USERNAME}")


def extract_current_value(svg: str, label: str, y: int) -> str:
    pattern = (
        rf'<text class="info" x="{LABEL_X}" y="{y}">{re.escape(label)}</text>'
        rf'<text class="txt" x="\d+" y="{y}">([^<]*)</text>'
    )
    match = re.search(pattern, svg)
    return match.group(1) if match else "N/A"


def replace_stat_line(svg: str, label: str, value: str, y: int) -> str:
    vx = value_x(label)
    pattern = (
        rf'(<text class="info" x="{LABEL_X}" y="{y}">{re.escape(label)}</text>)'
        rf'<text class="txt" x="\d+" y="{y}">[^<]*</text>'
    )
    replacement = rf'\g<1><text class="txt" x="{vx}" y="{y}">{value}</text>'
    new_svg, count = re.subn(pattern, replacement, svg, count=1)
    if count != 1:
        raise RuntimeError(f"Failed to update stat line for {label}")
    return new_svg
