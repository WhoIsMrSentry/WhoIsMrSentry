#!/usr/bin/env python3
"""Refresh assets/profile_terminal_panel.svg with live GitHub statistics."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.error
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


def graphql(query: str, variables: dict | None = None) -> dict:
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required for GraphQL")

    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "whoismrsentry-profile-terminal-panel",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]


def search_total_count(query: str) -> int:
    encoded_q = urllib.parse.quote(query, safe=":/+")
    data = http_json(f"https://api.github.com/search/issues?q={encoded_q}&per_page=1")
    return int(data.get("total_count", 0))


def get_user_profile() -> dict:
    return http_json(f"https://api.github.com/users/{USERNAME}")


def get_user_created_date() -> dt.date:
    q_created = "query($login: String!) { user(login: $login) { createdAt } }"
    created_at = graphql(q_created, {"login": USERNAME})["user"]["createdAt"]
    return dt.datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()


def get_total_contributions_all_time() -> int:
    created_date = get_user_created_date()
    today = dt.date.today()
    total = 0

    q_year = """
      query($login: String!, $from: DateTime!, $to: DateTime!) {
        user(login: $login) {
          contributionsCollection(from: $from, to: $to) {
            contributionCalendar { totalContributions }
          }
        }
      }
    """

    for year in range(created_date.year, today.year + 1):
        start = dt.date(year, 1, 1)
        end = dt.date(year, 12, 31)
        if year == created_date.year:
            start = created_date
        if year == today.year:
            end = today

        from_dt = dt.datetime.combine(start, dt.time.min, tzinfo=dt.UTC).isoformat()
        to_dt = dt.datetime.combine(end, dt.time.max, tzinfo=dt.UTC).isoformat()
        data = graphql(q_year, {"login": USERNAME, "from": from_dt, "to": to_dt})
        total += int(
            data["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
        )
    return total


def get_total_commit_contributions_all_time() -> int:
    created_date = get_user_created_date()
    today = dt.date.today()
    total = 0

    q_year = """
      query($login: String!, $from: DateTime!, $to: DateTime!) {
        user(login: $login) {
          contributionsCollection(from: $from, to: $to) {
            totalCommitContributions
          }
        }
      }
    """

    for year in range(created_date.year, today.year + 1):
        start = dt.date(year, 1, 1)
        end = dt.date(year, 12, 31)
        if year == created_date.year:
            start = created_date
        if year == today.year:
            end = today

        from_dt = dt.datetime.combine(start, dt.time.min, tzinfo=dt.UTC).isoformat()
        to_dt = dt.datetime.combine(end, dt.time.max, tzinfo=dt.UTC).isoformat()
        data = graphql(q_year, {"login": USERNAME, "from": from_dt, "to": to_dt})
        total += int(data["user"]["contributionsCollection"]["totalCommitContributions"])
    return total


def format_uptime(created_at: str) -> str:
    created = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    now = dt.datetime.now(dt.UTC)
    total_days = (now - created).days
    years = total_days // 365
    days = total_days % 365
    year_label = "year" if years == 1 else "years"
    day_label = "day" if days == 1 else "days"
    return f"{years} {year_label}, {days} {day_label}"


def extract_current_value(svg: str, label: str, y: int) -> str:
    pattern = (
        rf'<text class="info" x="{LABEL_X}" y="{y}">{re.escape(label)}</text>'
        rf'<text class="txt" x="\d+" y="{y}">([^<]*)</text>'
    )
    match = re.search(pattern, svg)
    return match.group(1) if match else "N/A"


def extract_uptime(svg: str) -> str:
    match = re.search(r'<text class="txt" x="44" y="614">([^<]*)</text>', svg)
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


def replace_uptime_line(svg: str, uptime_text: str) -> str:
    pattern = r'(<text class="txt" x="44" y="614">)[^<]*(</text>)'
    new_svg, count = re.subn(pattern, rf"\g<1>{uptime_text}\g<2>", svg, count=1)
    if count != 1:
        raise RuntimeError("Failed to update uptime line")
    return new_svg


def safe_value(name: str, getter, fallback: str) -> str:
    try:
        value = getter()
        return str(value)
    except Exception as exc:
        print(f"WARN: failed to fetch {name}: {exc}; using fallback={fallback}")
        return fallback


def collect_metrics(svg: str) -> dict[str, str]:
    fallbacks = {
        "repos": extract_current_value(svg, "Repos:", 394),
        "public_repos": extract_current_value(svg, "Public Repos:", 420),
        "contributions": extract_current_value(svg, "Contributions:", 446),
        "followers": extract_current_value(svg, "Followers:", 472),
        "pull_requests": extract_current_value(svg, "Pull Requests:", 498),
        "commits": extract_current_value(svg, "Commits:", 524),
        "uptime": extract_uptime(svg),
    }

    try:
        profile = get_user_profile()
    except Exception as exc:
        print(f"WARN: failed to fetch user profile: {exc}")
        profile = None

    if isinstance(profile, dict) and profile:
        public_repos = str(int(profile.get("public_repos", fallbacks["public_repos"])))
        followers = str(int(profile.get("followers", fallbacks["followers"])))
        created_at = profile.get("created_at")
        uptime = format_uptime(created_at) if created_at else fallbacks["uptime"]
    else:
        public_repos = fallbacks["public_repos"]
        followers = fallbacks["followers"]
        uptime = fallbacks["uptime"]

    contributions = safe_value(
        "contributions",
        get_total_contributions_all_time,
        fallbacks["contributions"],
    )
    commits = safe_value(
        "commits",
        get_total_commit_contributions_all_time,
        fallbacks["commits"],
    )
    pull_requests = safe_value(
        "pull requests",
        lambda: search_total_count(f"type:pr author:{USERNAME}"),
        fallbacks["pull_requests"],
    )

    return {
        "repos": TOTAL_REPOS,
        "public_repos": public_repos,
        "contributions": contributions,
        "followers": followers,
        "pull_requests": pull_requests,
        "commits": commits,
        "uptime": uptime,
    }


def main() -> int:
    svg = SVG_PATH.read_text(encoding="utf-8")
    metrics = collect_metrics(svg)

    for label, key, y in STAT_ROWS:
        svg = replace_stat_line(svg, label, metrics[key], y)

    svg = replace_uptime_line(svg, metrics["uptime"])
    SVG_PATH.write_text(svg, encoding="utf-8")

    print(f"Updated {SVG_PATH}")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
