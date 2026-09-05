#!/usr/bin/env python3
"""Refresh assets/profile_terminal_panel.svg with live GitHub statistics,
typewriter animations, streak metrics, and animated commit snake game.
"""

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
STREAK_SVG_PATH = REPO_ROOT / "assets" / "streak_stats.svg"

USERNAME = os.environ.get("GITHUB_USERNAME", "WhoIsMrSentry")
TOTAL_REPOS = os.environ.get("TOTAL_REPOS", "76")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GHT") or os.environ.get("GH_TOKEN")


def http_json(url: str) -> dict:
    headers = {
        "User-Agent": "whoismrsentry-profile-terminal-panel",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
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
    with urllib.request.urlopen(req, timeout=30) as resp:
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


def format_uptime(created_at_str: str) -> str:
    parsed = dt.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
    created_date = parsed.date()
    today = dt.date.today()
    delta_days = (today - created_date).days
    years = delta_days // 365
    days = delta_days % 365
    y_unit = "year" if years == 1 else "years"
    d_unit = "day" if days == 1 else "days"
    return f"{years} {y_unit}, {days} {d_unit}"


def get_total_stars_count() -> int:
    total = 0
    page = 1
    while True:
        url = f"https://api.github.com/users/{USERNAME}/repos?type=owner&per_page=100&page={page}"
        data = http_json(url)
        if not isinstance(data, list) or not data:
            break
        for repo in data:
            total += int((repo or {}).get("stargazers_count", 0))
        if len(data) < 100:
            break
        page += 1
    return total


def read_streak_stats() -> dict[str, str]:
    fallback = {
        "current_streak": "257",
        "longest_streak": "257",
        "total_contributions": "4,792",
        "streak_range": "Dec 23, 2025 - Present",
    }
    if not STREAK_SVG_PATH.exists():
        return fallback

    try:
        content = STREAK_SVG_PATH.read_text(encoding="utf-8")
        # Extract total contributions: first big text block in streak_stats.svg
        nums = re.findall(r'<text[^>]*font-size=[\'"]28px[\'"][^>]*>\s*([0-9,]+)\s*</text>', content)
        ranges = re.findall(r'<text[^>]*font-size=[\'"]12px[\'"][^>]*>\s*([^<]+)\s*</text>', content)

        total = nums[0] if len(nums) > 0 else fallback["total_contributions"]
        curr = nums[1] if len(nums) > 1 else fallback["current_streak"]
        longest = nums[2] if len(nums) > 2 else fallback["longest_streak"]
        s_range = ranges[1].strip() if len(ranges) > 1 else fallback["streak_range"]

        return {
            "current_streak": curr,
            "longest_streak": longest,
            "total_contributions": total,
            "streak_range": s_range,
        }
    except Exception as exc:
        print(f"WARN: could not parse streak_stats.svg ({exc}); using fallback")
        return fallback


def collect_metrics() -> dict[str, str]:
    streak = read_streak_stats()

    profile = None
    try:
        profile = get_user_profile()
    except Exception as exc:
        print(f"WARN: failed to fetch user profile: {exc}")

    if isinstance(profile, dict) and profile:
        public_repos = str(int(profile.get("public_repos", 62)))
        followers = str(int(profile.get("followers", 23)))
        gists = str(int(profile.get("public_gists", 0)))
        created_at = profile.get("created_at")
        uptime = format_uptime(created_at) if created_at else "3 years, 105 days"
    else:
        public_repos = "62"
        followers = "23"
        gists = "0"
        uptime = "3 years, 105 days"

    # Quick search counts
    try:
        pull_requests = str(search_total_count(f"type:pr author:{USERNAME}"))
    except Exception:
        pull_requests = "250"

    try:
        issues = str(search_total_count(f"type:issue author:{USERNAME}"))
    except Exception:
        issues = "9"

    try:
        stars = str(get_total_stars_count())
    except Exception:
        stars = "16"

    return {
        "repos": TOTAL_REPOS,
        "public_repos": public_repos,
        "contributions": streak["total_contributions"].replace(",", ""),
        "commits": "4114",
        "pull_requests": pull_requests,
        "issues": issues,
        "followers": followers,
        "stars": stars,
        "gists": gists,
        "uptime": uptime,
        "current_streak": streak["current_streak"],
        "longest_streak": streak["longest_streak"],
        "total_streak_contribs": streak["total_contributions"],
        "streak_range": streak["streak_range"],
    }


def generate_terminal_panel_svg(m: dict[str, str]) -> str:
    width = 920
    height = 1060

    # Build ASCII snake arena cells
    snake_cells = []
    # 4 rows of 38 cells
    cols = 38
    rows = 4
    start_x = 56
    start_y = 738
    cell_w = 19
    cell_h = 14
    gap = 3

    # Pattern of active contributions:
    # 0 = empty/dark, 1 = low, 2 = medium, 3 = high, 4 = snake body, 5 = snake head
    active_indices = {
        (0, 2): 1, (0, 7): 2, (0, 14): 1, (0, 20): 3, (0, 28): 2, (0, 35): 1,
        (1, 4): 2, (1, 10): 3, (1, 18): 1, (1, 24): 2, (1, 31): 3,
        (2, 1): 1, (2, 8): 2, (2, 15): 3, (2, 22): 1, (2, 29): 2, (2, 36): 3,
        (3, 5): 3, (3, 12): 1, (3, 19): 2, (3, 26): 3, (3, 33): 1,
    }

    # Snake path: in row 1 & 2
    snake_body = [(1, 12), (1, 13), (1, 14), (1, 15), (1, 16), (2, 16), (2, 17), (2, 18)]
    snake_head = (2, 19)

    for r in range(rows):
        for c in range(cols):
            cx = start_x + c * (cell_w + gap)
            cy = start_y + r * (cell_h + gap)

            if (r, c) == snake_head:
                snake_cells.append(
                    f'<rect class="snake-head" x="{cx}" y="{cy}" width="{cell_w}" height="{cell_h}" rx="2" fill="#39ff14" />'
                )
            elif (r, c) in snake_body:
                snake_cells.append(
                    f'<rect class="snake-body" x="{cx}" y="{cy}" width="{cell_w}" height="{cell_h}" rx="2" fill="#ff1744" />'
                )
            elif (r, c) in active_indices:
                lvl = active_indices[(r, c)]
                color = "#004d1a" if lvl == 1 else ("#009933" if lvl == 2 else "#39ff14")
                snake_cells.append(
                    f'<rect class="food-dot" x="{cx}" y="{cy}" width="{cell_w}" height="{cell_h}" rx="2" fill="{color}" />'
                )
            else:
                snake_cells.append(
                    f'<rect x="{cx}" y="{cy}" width="{cell_w}" height="{cell_h}" rx="2" fill="#2d000d" />'
                )

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">WhoIsMrSentry Interactive Profile Terminal</title>
  <desc id="desc">Typewriter shell session showcasing whoami, profile summary, neofetch stats, streak metrics, commit snake, uptime, and about.</desc>

  <defs>
    <style>
      .outer {{ fill: #200009; }}
      .terminal {{ fill: #200009; }}
      .head {{ fill: #15000a; }}
      .frame {{ fill: none; stroke: #88001b; stroke-width: 2; }}
      .prompt {{ fill: #39ff14; font: 700 17px Monaco, Consolas, Menlo, monospace; }}
      .cmd {{ fill: #ff5f58; font: 600 17px Monaco, Consolas, Menlo, monospace; }}
      .txt {{ fill: #e6e6e6; font: 500 16px Monaco, Consolas, Menlo, monospace; }}
      .info {{ fill: #ff5f58; font: 600 16px Monaco, Consolas, Menlo, monospace; }}
      .ascii {{ fill: #39ff14; font: 500 4.2px Monaco, Consolas, Menlo, monospace; }}
      .box-frame {{ fill: #15000a; stroke: #88001b; stroke-width: 1.5; }}
      .box-header {{ fill: #39ff14; font: 700 14px Monaco, Consolas, monospace; }}
      .box-metric {{ fill: #e6ffe6; font: 500 15px Monaco, Consolas, monospace; }}
      .highlight {{ fill: #39ff14; font-weight: bold; }}
      .accent {{ fill: #ff5f58; font-weight: bold; }}

      /* Typewriter Keyframe Animations */
      @keyframes typeCmd {{
        from {{ width: 0; }}
        to {{ width: 320px; }}
      }}
      @keyframes lineReveal {{
        from {{ opacity: 0; transform: translateY(-2px); }}
        to {{ opacity: 1; transform: translateY(0); }}
      }}
      @keyframes cursorBlink {{
        0%, 49% {{ opacity: 1; }}
        50%, 100% {{ opacity: 0; }}
      }}
      @keyframes snakeCrawl {{
        0% {{ transform: translateX(0px); }}
        50% {{ transform: translateX(30px); }}
        100% {{ transform: translateX(0px); }}
      }}
      @keyframes foodGlow {{
        0%, 100% {{ filter: drop-shadow(0 0 1px #39ff14); }}
        50% {{ filter: drop-shadow(0 0 4px #39ff14); }}
      }}

      /* Sequential Timing */
      .p-1 {{ opacity: 0; animation: lineReveal 0.05s 0.2s forwards; }}
      .c-1 {{ animation: typeCmd 0.35s steps(6, end) 0.35s forwards; }}
      .o-1 {{ opacity: 0; animation: lineReveal 0.05s 0.8s forwards; }}

      .p-2 {{ opacity: 0; animation: lineReveal 0.05s 1.1s forwards; }}
      .c-2 {{ animation: typeCmd 0.5s steps(19, end) 1.25s forwards; }}
      .o-2 {{ opacity: 0; animation: lineReveal 0.05s 1.85s forwards; }}

      .p-3 {{ opacity: 0; animation: lineReveal 0.05s 2.2s forwards; }}
      .c-3 {{ animation: typeCmd 0.4s steps(8, end) 2.35s forwards; }}
      .o-3 {{ opacity: 0; animation: lineReveal 0.05s 2.85s forwards; }}

      .p-4 {{ opacity: 0; animation: lineReveal 0.05s 3.8s forwards; }}
      .c-4 {{ animation: typeCmd 0.45s steps(16, end) 3.95s forwards; }}
      .o-4 {{ opacity: 0; animation: lineReveal 0.05s 4.5s forwards; }}

      .p-5 {{ opacity: 0; animation: lineReveal 0.05s 5.2s forwards; }}
      .c-5 {{ animation: typeCmd 0.45s steps(15, end) 5.35s forwards; }}
      .o-5 {{ opacity: 0; animation: lineReveal 0.05s 5.9s forwards; }}

      .p-6 {{ opacity: 0; animation: lineReveal 0.05s 6.8s forwards; }}
      .c-6 {{ animation: typeCmd 0.35s steps(6, end) 6.95s forwards; }}
      .o-6 {{ opacity: 0; animation: lineReveal 0.05s 7.4s forwards; }}

      .p-7 {{ opacity: 0; animation: lineReveal 0.05s 7.7s forwards; }}
      .c-7 {{ animation: typeCmd 0.4s steps(13, end) 7.85s forwards; }}
      .o-7 {{ opacity: 0; animation: lineReveal 0.05s 8.35s forwards; }}

      .p-8 {{ opacity: 0; animation: lineReveal 0.05s 8.7s forwards; }}
      .c-8 {{ animation: typeCmd 0.3s steps(4, end) 8.85s forwards; }}
      
      .cursor-blink {{
        opacity: 0;
        animation: lineReveal 0.05s 9.2s forwards, cursorBlink 1s 9.2s infinite;
      }}

      .snake-head {{
        animation: foodGlow 1.5s infinite alternate;
      }}
      .snake-body {{
        animation: snakeCrawl 4s ease-in-out infinite alternate;
      }}
      .food-dot {{
        animation: foodGlow 2s infinite alternate;
      }}
    </style>

    <!-- Clip Paths for Typewriter Effect -->
    <clipPath id="cp-cmd1"><rect class="c-1" x="325" y="80" width="0" height="30"/></clipPath>
    <clipPath id="cp-cmd2"><rect class="c-2" x="325" y="145" width="0" height="30"/></clipPath>
    <clipPath id="cp-cmd3"><rect class="c-3" x="325" y="245" width="0" height="30"/></clipPath>
    <clipPath id="cp-cmd4"><rect class="c-4" x="325" y="525" width="0" height="30"/></clipPath>
    <clipPath id="cp-cmd5"><rect class="c-5" x="325" y="665" width="0" height="30"/></clipPath>
    <clipPath id="cp-cmd6"><rect class="c-6" x="325" y="835" width="0" height="30"/></clipPath>
    <clipPath id="cp-cmd7"><rect class="c-7" x="325" y="900" width="0" height="30"/></clipPath>
    <clipPath id="cp-cmd8"><rect class="c-8" x="325" y="985" width="0" height="30"/></clipPath>
  </defs>

  <!-- Terminal Window Background -->
  <rect class="outer" x="0" y="0" width="{width}" height="{height}" rx="16"/>
  <rect class="terminal" x="20" y="20" width="880" height="{height - 40}" rx="10"/>
  <rect class="frame" x="20" y="20" width="880" height="{height - 40}" rx="10"/>
  
  <!-- Header Bar -->
  <rect class="head" x="20" y="20" width="880" height="42" rx="10"/>
  <circle cx="44" cy="41" r="7" fill="#ff5f58"/>
  <circle cx="66" cy="41" r="7" fill="#ffbd2e"/>
  <circle cx="88" cy="41" r="7" fill="#18c132"/>
  <text x="{width // 2}" y="46" fill="#e6ffe6" font-family="Monaco, Consolas, monospace" font-size="13" font-weight="bold" text-anchor="middle">WhoIsMrSentry@github.com: ~ (bash)</text>

  <!-- ================= 1. whoami ================= -->
  <g class="p-1">
    <text class="prompt" x="44" y="98">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd" x="325" y="98" clip-path="url(#cp-cmd1)">whoami</text>
  </g>
  <g class="o-1">
    <text class="txt" x="44" y="124">Emir Hamurcu</text>
  </g>

  <!-- ================= 2. ./profile --summary ================= -->
  <g class="p-2">
    <text class="prompt" x="44" y="164">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd" x="325" y="164" clip-path="url(#cp-cmd2)">./profile --summary</text>
  </g>
  <g class="o-2">
    <text class="info" x="44" y="190">Focus:</text><text class="txt" x="126" y="190">Robotics &amp; Embedded AI</text>
    <text class="info" x="44" y="214">Role:</text><text class="txt" x="126" y="214">Embedded System Developer</text>
    <text class="info" x="44" y="238">Status:</text><text class="txt" x="126" y="238">Open to Collaboration</text>
  </g>

  <!-- ================= 3. neofetch ================= -->
  <g class="p-3">
    <text class="prompt" x="44" y="266">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd" x="325" y="266" clip-path="url(#cp-cmd3)">neofetch</text>
  </g>
  <g class="o-3">
    <!-- ASCII Octocat / Sentry Robot -->
    <text class="ascii" x="44" y="296" xml:space="preserve">
      <tspan x="44" dy="0">                               @@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">                         @@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">                    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">                 @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">              @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">            @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">          @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">         @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">       @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">      @@@@@@@@@@@      @@@@@@@@@@@@@@@@@@@@@@@@@@@@      @@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">     @@@@@@@@@@@          @@@@@@          @@@@@@          @@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">    @@@@@@@@@@@@                                          @@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">   @@@@@@@@@@@@@                                          @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">  @@@@@@@@@@@@@@                                          @@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2"> @@@@@@@@@@@@@@@@                                        @@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2"> @@@@@@@@@@@@@@                                            @@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2"> @@@@@@@@@@@@@                                              @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">@@@@@@@@@@@@@@                                               @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">@@@@@@@@@@@@@                                                @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">@@@@@@@@@@@@@                                                @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">@@@@@@@@@@@@@                                                @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">@@@@@@@@@@@@@                                                @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">@@@@@@@@@@@@@@                                              @@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2"> @@@@@@@@@@@@@@                                            @@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2"> @@@@@@@@@@@@@@@                                          @@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">  @@@@@@@@@@@@@@@@@@                                  @@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">   @@@@@@@   @@@@@@@@@@                            @@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">     @@@@@@@@    @@@@@@@@@@@                  @@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">      @@@@@@@@     @@@@@@@@@                  @@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">       @@@@@@@@                               @@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">          @@@@@@@@                            @@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">            @@@@@@@@@@@@@@@@                  @@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.2">                %@@@@@@@@@@@                  @@@@@@@@@@@%</tspan>
      <tspan x="44" dy="4.2">                    @@@@@@@@                  @@@@@@@@</tspan>
    </text>

    <!-- Neofetch Details -->
    <text class="info" x="340" y="300">WhoIsMrSentry @github.com</text>
    <text class="info" x="340" y="322">--------------------------</text>
    <text class="info" x="340" y="344">OS:</text><text class="txt" x="380" y="344">GitHub</text>
    <text class="info" x="340" y="366">Host:</text><text class="txt" x="394" y="366">github.com</text>
    <text class="info" x="340" y="388">Repos:</text><text class="txt" x="400" y="388">{m['repos']}</text>
    <text class="info" x="340" y="410">Public Repos:</text><text class="txt" x="470" y="410">{m['public_repos']}</text>
    <text class="info" x="340" y="432">Contributions:</text><text class="txt" x="480" y="432">{m['contributions']}</text>
    <text class="info" x="340" y="454">Commits:</text><text class="txt" x="420" y="454">{m['commits']}</text>
    <text class="info" x="340" y="476">Pull Requests:</text><text class="txt" x="480" y="476">{m['pull_requests']}</text>
    <text class="info" x="340" y="498">Followers / Stars:</text><text class="txt" x="515" y="498">{m['followers']} / {m['stars']}</text>
  </g>

  <!-- ================= 4. ./profile --streak ================= -->
  <g class="p-4">
    <text class="prompt" x="44" y="546">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd" x="325" y="546" clip-path="url(#cp-cmd4)">./profile --streak</text>
  </g>
  <g class="o-4">
    <rect class="box-frame" x="44" y="562" width="832" height="74" rx="8"/>
    <text class="box-header" x="64" y="586">⚡ GITHUB CONTRIBUTION STREAK METRICS</text>
    
    <text class="box-metric" x="64" y="616">
      <tspan class="accent">🔥 Current Streak:</tspan> <tspan class="highlight">{m['current_streak']} days</tspan> (Active)
      <tspan dx="25" class="accent">⚡ Longest Streak:</tspan> <tspan class="highlight">{m['longest_streak']} days</tspan>
      <tspan dx="25" class="accent">✨ Total Contribs:</tspan> <tspan class="highlight">{m['total_streak_contribs']}</tspan>
    </text>
  </g>

  <!-- ================= 5. ./snake --commits ================= -->
  <g class="p-5">
    <text class="prompt" x="44" y="684">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd" x="325" y="684" clip-path="url(#cp-cmd5)">./snake --commits</text>
  </g>
  <g class="o-5">
    <!-- Snake Game Arena Box -->
    <rect class="box-frame" x="44" y="700" width="832" height="116" rx="8"/>
    <rect x="44" y="700" width="832" height="28" rx="8" fill="#1b000d"/>
    <line x1="44" y1="728" x2="876" y2="728" stroke="#88001b" stroke-width="1"/>
    
    <text class="box-header" x="64" y="720">🐍 SENTRY RETRO SNAKE ARENA</text>
    <text x="856" y="720" fill="#39ff14" font-family="Monaco, monospace" font-size="12" text-anchor="end">
      SCORE: {m['total_streak_contribs']}  •  LENGTH: {m['current_streak']}  •  STATUS: WINNING
    </text>

    <!-- Grid of Contribution Cells & Crawling Snake -->
    {''.join(snake_cells)}
  </g>

  <!-- ================= 6. uptime ================= -->
  <g class="p-6">
    <text class="prompt" x="44" y="852">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd" x="325" y="852" clip-path="url(#cp-cmd6)">uptime</text>
  </g>
  <g class="o-6">
    <text class="txt" x="44" y="878">{m['uptime']}</text>
  </g>

  <!-- ================= 7. cat about.txt ================= -->
  <g class="p-7">
    <text class="prompt" x="44" y="916">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd" x="325" y="916" clip-path="url(#cp-cmd7)">cat about.txt</text>
  </g>
  <g class="o-7">
    <text class="txt" x="44" y="942">Building robotics and edge AI systems with production-first engineering.</text>
    <text class="txt" x="44" y="966">Focused on reliable automation, maintainable code, and measurable results.</text>
  </g>

  <!-- ================= 8. exit & Blinking Cursor ================= -->
  <g class="p-8">
    <text class="prompt" x="44" y="1004">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd" x="325" y="1004" clip-path="url(#cp-cmd8)">exit</text>
  </g>
  <rect class="cursor-blink" x="382" y="987" width="10" height="20" fill="#39ff14"/>
</svg>
"""
    return svg


def main() -> int:
    metrics = collect_metrics()
    svg = generate_terminal_panel_svg(metrics)
    SVG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text(svg, encoding="utf-8")

    print(f"Generated typewriter profile terminal: {SVG_PATH}")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
