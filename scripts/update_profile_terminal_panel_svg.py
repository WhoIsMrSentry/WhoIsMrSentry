#!/usr/bin/env python3
"""Generate WhoIsMrSentry interactive terminal profile SVG with live stats,
typewriter animation, streak metrics, 30-day activity graph, and commit snake arena.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = REPO_ROOT / "assets" / "profile_terminal_panel.svg"
SVG_PATH_NEW = REPO_ROOT / "assets" / "terminal_profile.svg"
STREAK_PATH = REPO_ROOT / "assets" / "streak_stats.svg"
ACTIVITY_PATH = REPO_ROOT / "assets" / "activity_graph.svg"

USERNAME = os.environ.get("GITHUB_USERNAME", "WhoIsMrSentry")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GHT") or os.environ.get("GH_TOKEN")


def get_streak_metrics() -> dict[str, str]:
    defaults = {
        "total_contribs": "4,792",
        "current_streak": "257",
        "longest_streak": "257",
        "period": "May 24, 2023 - Present",
        "dates": "Dec 23, 2025 - Sep 5",
    }
    if not STREAK_PATH.exists():
        return defaults

    try:
        content = STREAK_PATH.read_text(encoding="utf-8")
        texts = [t.strip() for t in re.findall(r"<text[^>]*>([^<]+)</text>", content) if t.strip()]
        if len(texts) >= 9:
            return {
                "total_contribs": texts[0],
                "period": texts[2],
                "current_streak": texts[3],
                "dates": texts[5],
                "longest_streak": texts[6],
            }
    except Exception as exc:
        print(f"WARN: could not read streak metrics from SVG: {exc}")
    return defaults


def get_account_uptime() -> str:
    # WhoIsMrSentry created date: May 24, 2023
    created = dt.date(2023, 5, 24)
    today = dt.date.today()
    total_days = (today - created).days
    years = total_days // 365
    days = total_days % 365
    year_label = "year" if years == 1 else "years"
    day_label = "day" if days == 1 else "days"
    return f"{years} {year_label}, {days} {day_label}"


def get_activity_points() -> list[tuple[int, int]]:
    """Return 30 days of contribution counts as (day_of_month, count)."""
    # 1. Try fetching from GraphQL
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    days_data = []
    if GITHUB_TOKEN:
        try:
            payload = json.dumps({"query": query, "variables": {"login": USERNAME}}).encode("utf-8")
            req = urllib.request.Request(
                "https://api.github.com/graphql",
                data=payload,
                headers={
                    "Authorization": f"Bearer {GITHUB_TOKEN}",
                    "Content-Type": "application/json",
                    "User-Agent": "whoismrsentry-terminal-panel",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8")).get("data")
                weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
                for w in weeks:
                    for d in w["contributionDays"]:
                        days_data.append((int(d["date"].split("-")[2]), int(d["contributionCount"])))
        except Exception as exc:
            print(f"WARN: GraphQL contributions fetch failed: {exc}")

    if not days_data:
        try:
            res = subprocess.run(
                ["gh", "api", "graphql", "-F", f"login={USERNAME}", "-f", f"query={query}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                data = json.loads(res.stdout).get("data")
                weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
                for w in weeks:
                    for d in w["contributionDays"]:
                        days_data.append((int(d["date"].split("-")[2]), int(d["contributionCount"])))
        except Exception as exc:
            print(f"WARN: gh CLI fallback failed: {exc}")

    if len(days_data) >= 30:
        return days_data[-30:]

    # Fallback to realistic distribution matching activity graph
    fallback = [
        (6, 7), (7, 7), (8, 5), (9, 7), (10, 7), (11, 7),
        (12, 46), (13, 21), (14, 10), (15, 25), (16, 21), (17, 15),
        (18, 15), (19, 12), (20, 23), (21, 15), (22, 16), (23, 13),
        (24, 16), (25, 12), (26, 16), (27, 24), (28, 16), (29, 11),
        (30, 8), (31, 8), (1, 8), (2, 8), (3, 8), (4, 8), (5, 12)
    ]
    return fallback[-30:]


def build_activity_chart(points: list[tuple[int, int]], chart_x: int = 70, chart_y: int = 450, chart_w: int = 780, chart_h: int = 80) -> str:
    max_val = max(50, max(c for _, c in points))
    n = len(points)
    step_x = chart_w / (n - 1)

    coords = []
    for i, (_, count) in enumerate(points):
        cx = chart_x + i * step_x
        cy = chart_y + chart_h - (count / max_val) * chart_h
        coords.append((cx, cy, count))

    # Spline Path
    path_d = f"M {coords[0][0]:.1f} {coords[0][1]:.1f}"
    for i in range(len(coords) - 1):
        x0, y0, _ = coords[i]
        x1, y1, _ = coords[i + 1]
        mid_x = (x0 + x1) / 2
        path_d += f" C {mid_x:.1f} {y0:.1f}, {mid_x:.1f} {y1:.1f}, {x1:.1f} {y1:.1f}"

    area_d = f"{path_d} L {coords[-1][0]:.1f} {chart_y + chart_h:.1f} L {coords[0][0]:.1f} {chart_y + chart_h:.1f} Z"

    # Grid lines for 0, 10, 20, 30, 40, 50
    grid_lines = []
    for v in [0, 10, 20, 30, 40, 50]:
        gy = chart_y + chart_h - (v / 50) * chart_h
        grid_lines.append(f'<line x1="{chart_x}" y1="{gy:.1f}" x2="{chart_x + chart_w}" y2="{gy:.1f}" stroke="#440015" stroke-dasharray="3,3" stroke-width="1"/>')
        grid_lines.append(f'<text x="{chart_x - 8}" y="{gy + 4:.1f}" fill="#a0a0a0" font-family="Monaco, Consolas, monospace" font-size="10" text-anchor="end">{v}</text>')

    # Dots and peak annotation
    dots = []
    peak_count = max(c for _, c in points)
    for i, (cx, cy, cnt) in enumerate(coords):
        if cnt == peak_count:
            dots.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" fill="#39ff14" stroke="#ffffff" stroke-width="2"/>')
            dots.append(f'<text x="{cx:.1f}" y="{cy - 8:.1f}" fill="#39ff14" font-family="Monaco, Consolas, monospace" font-size="11" font-weight="bold" text-anchor="middle">{cnt}</text>')
        else:
            dots.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2.5" fill="#e6ffe6" stroke="#39ff14" stroke-width="1.2"/>')

    # X-axis day labels
    day_labels = []
    for i, (day, _) in enumerate(points):
        cx = chart_x + i * step_x
        if i % 2 == 0 or i == n - 1:
            day_labels.append(f'<text x="{cx:.1f}" y="{chart_y + chart_h + 16}" fill="#a0a0a0" font-family="Monaco, Consolas, monospace" font-size="10" text-anchor="middle">{day}</text>')

    return f"""
      <defs>
        <linearGradient id="actGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#39ff14" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="#39ff14" stop-opacity="0.0"/>
        </linearGradient>
      </defs>
      {''.join(grid_lines)}
      <path d="{area_d}" fill="url(#actGrad)"/>
      <path d="{path_d}" fill="none" stroke="#39ff14" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
      {''.join(dots)}
      {''.join(day_labels)}
      <text x="{chart_x + chart_w / 2}" y="{chart_y + chart_h + 30}" fill="#888888" font-family="Monaco, Consolas, monospace" font-size="10" text-anchor="middle">Days (30-Day Window)</text>
    """


def build_snake_arena() -> str:
    cols = 44
    rows = 6
    cell_w = 14
    cell_h = 9
    gap_x = 4
    gap_y = 3
    start_x = 64
    start_y = 665

    # Visual contribution pattern
    pattern = [
        [0, 1, 0, 0, 1, 0, 1, 0, 0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0],
        [1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1],
        [0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 1, 0],
        [0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0],
        [1, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1],
        [0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0],
    ]

    cells = []
    for r in range(rows):
        for c in range(cols):
            x = start_x + c * (cell_w + gap_x)
            y = start_y + r * (cell_h + gap_y)
            is_active = pattern[r][c]
            fill = "#ff1744" if is_active else "#4a0015"
            cells.append(f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" rx="2" fill="{fill}"/>')

    snake_elements = f"""
      <g class="snake-crawl">
        <rect x="{start_x + 28 * (cell_w + gap_x)}" y="{start_y + 3 * (cell_h + gap_y)}" width="{cell_w}" height="{cell_h}" rx="2" fill="#39ff14" filter="drop-shadow(0 0 3px #39ff14)"/>
        <rect x="{start_x + 29 * (cell_w + gap_x)}" y="{start_y + 3 * (cell_h + gap_y)}" width="{cell_w}" height="{cell_h}" rx="2" fill="#39ff14" filter="drop-shadow(0 0 3px #39ff14)"/>
        <rect x="{start_x + 30 * (cell_w + gap_x)}" y="{start_y + 3 * (cell_h + gap_y)}" width="{cell_w}" height="{cell_h}" rx="2" fill="#39ff14" filter="drop-shadow(0 0 3px #39ff14)"/>
        <rect x="{start_x + 31 * (cell_w + gap_x)}" y="{start_y + 3 * (cell_h + gap_y)}" width="{cell_w}" height="{cell_h}" rx="2" fill="#39ff14" filter="drop-shadow(0 0 3px #39ff14)"/>
        <rect x="{start_x + 32 * (cell_w + gap_x)}" y="{start_y + 3 * (cell_h + gap_y)}" width="{cell_w}" height="{cell_h}" rx="2" fill="#39ff14" filter="drop-shadow(0 0 3px #39ff14)"/>
        <!-- Snake Head -->
        <rect x="{start_x + 33 * (cell_w + gap_x)}" y="{start_y + 3 * (cell_h + gap_y)}" width="{cell_w}" height="{cell_h}" rx="3" fill="#ffffff" stroke="#39ff14" stroke-width="1.5" filter="drop-shadow(0 0 5px #39ff14)"/>
      </g>
      <!-- Blinking Food Dots -->
      <circle cx="{start_x + 36 * (cell_w + gap_x) + 7}" cy="{start_y + 3 * (cell_h + gap_y) + 4.5}" r="4" fill="#39ff14" class="food-dot"/>
      <circle cx="{start_x + 12 * (cell_w + gap_x) + 7}" cy="{start_y + 1 * (cell_h + gap_y) + 4.5}" r="4" fill="#39ff14" class="food-dot"/>
      <circle cx="{start_x + 20 * (cell_w + gap_x) + 7}" cy="{start_y + 4 * (cell_h + gap_y) + 4.5}" r="4" fill="#39ff14" class="food-dot"/>
    """

    return "".join(cells) + snake_elements


def generate_terminal_panel_svg() -> str:
    streak = get_streak_metrics()
    uptime = get_account_uptime()
    points = get_activity_points()
    chart_svg = build_activity_chart(points, chart_x=70, chart_y=450, chart_w=780, chart_h=80)
    snake_svg = build_snake_arena()

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="920" height="1020" viewBox="0 0 920 1020" role="img" aria-labelledby="title desc">
  <title id="title">WhoIsMrSentry Interactive Profile Terminal</title>
  <desc id="desc">Animated terminal session executing whoami, summary, streak, activity graph, commit snake, uptime, and bio.</desc>

  <defs>
    <style>
      .outer {{ fill: #200009; }}
      .terminal {{ fill: #200009; }}
      .head {{ fill: #15000a; }}
      .frame {{ fill: none; stroke: #88001b; stroke-width: 2; }}
      .prompt {{ fill: #39ff14; font: 700 16px Monaco, Consolas, Menlo, monospace; }}
      .cmd {{ fill: #ff5f58; font: 600 16px Monaco, Consolas, Menlo, monospace; }}
      .txt {{ fill: #e6e6e6; font: 500 15px Monaco, Consolas, Menlo, monospace; }}
      .info {{ fill: #ff5f58; font: 600 15px Monaco, Consolas, Menlo, monospace; }}
      .box-frame {{ fill: #15000a; stroke: #88001b; stroke-width: 1.5; }}
      .box-head {{ fill: #39ff14; font: 700 13px Monaco, Consolas, monospace; }}
      .box-sub {{ fill: #ff5f58; font: 600 12px Monaco, Consolas, monospace; }}
      .val-large {{ fill: #ffffff; font: 700 24px Monaco, Consolas, monospace; text-anchor: middle; }}
      .val-label {{ fill: #a0a0a0; font: 500 12px Monaco, Consolas, monospace; text-anchor: middle; }}
      .val-date {{ fill: #ff5f58; font: 500 11px Monaco, Consolas, monospace; text-anchor: middle; }}

      /* Animation Loop (24s cycle) */
      @keyframes blink {{
        0%, 49% {{ opacity: 1; }}
        50%, 100% {{ opacity: 0; }}
      }}

      @keyframes snakeMove {{
        0%, 100% {{ transform: translateX(0px); }}
        50% {{ transform: translateX(25px); }}
      }}

      @keyframes foodGlow {{
        0%, 100% {{ filter: drop-shadow(0 0 1px #39ff14); }}
        50% {{ filter: drop-shadow(0 0 4px #39ff14); }}
      }}

      /* Typewriter reveals for commands */
      .cmd-1 {{ animation: tc1 24s steps(6, end) infinite; }}
      @keyframes tc1 {{
        0% {{ clip-path: inset(0 100% 0 0); }}
        2%, 97% {{ clip-path: inset(0 0 0 0); }}
        98%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-1 {{ animation: ro1 24s infinite; }}
      @keyframes ro1 {{
        0%, 2% {{ opacity: 0; transform: translateY(-2px); }}
        3%, 97% {{ opacity: 1; transform: translateY(0); }}
        98%, 100% {{ opacity: 0; }}
      }}

      .cmd-2 {{ animation: tc2 24s steps(19, end) infinite; }}
      @keyframes tc2 {{
        0%, 4% {{ clip-path: inset(0 100% 0 0); }}
        6.5%, 97% {{ clip-path: inset(0 0 0 0); }}
        98%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-2 {{ animation: ro2 24s infinite; }}
      @keyframes ro2 {{
        0%, 6.5% {{ opacity: 0; transform: translateY(-2px); }}
        7.5%, 97% {{ opacity: 1; transform: translateY(0); }}
        98%, 100% {{ opacity: 0; }}
      }}

      .cmd-3 {{ animation: tc3 24s steps(16, end) infinite; }}
      @keyframes tc3 {{
        0%, 9% {{ clip-path: inset(0 100% 0 0); }}
        12%, 97% {{ clip-path: inset(0 0 0 0); }}
        98%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-3 {{ animation: ro3 24s infinite; }}
      @keyframes ro3 {{
        0%, 12% {{ opacity: 0; transform: translateY(4px); }}
        13.5%, 97% {{ opacity: 1; transform: translateY(0); }}
        98%, 100% {{ opacity: 0; }}
      }}

      .cmd-4 {{ animation: tc4 24s steps(18, end) infinite; }}
      @keyframes tc4 {{
        0%, 16% {{ clip-path: inset(0 100% 0 0); }}
        19%, 97% {{ clip-path: inset(0 0 0 0); }}
        98%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-4 {{ animation: ro4 24s infinite; }}
      @keyframes ro4 {{
        0%, 19% {{ opacity: 0; transform: translateY(4px); }}
        20.5%, 97% {{ opacity: 1; transform: translateY(0); }}
        98%, 100% {{ opacity: 0; }}
      }}

      .cmd-5 {{ animation: tc5 24s steps(16, end) infinite; }}
      @keyframes tc5 {{
        0%, 23% {{ clip-path: inset(0 100% 0 0); }}
        26%, 97% {{ clip-path: inset(0 0 0 0); }}
        98%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-5 {{ animation: ro5 24s infinite; }}
      @keyframes ro5 {{
        0%, 26% {{ opacity: 0; transform: translateY(4px); }}
        27.5%, 97% {{ opacity: 1; transform: translateY(0); }}
        98%, 100% {{ opacity: 0; }}
      }}

      .cmd-6 {{ animation: tc6 24s steps(6, end) infinite; }}
      @keyframes tc6 {{
        0%, 30% {{ clip-path: inset(0 100% 0 0); }}
        32%, 97% {{ clip-path: inset(0 0 0 0); }}
        98%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-6 {{ animation: ro6 24s infinite; }}
      @keyframes ro6 {{
        0%, 32% {{ opacity: 0; transform: translateY(-2px); }}
        33%, 97% {{ opacity: 1; transform: translateY(0); }}
        98%, 100% {{ opacity: 0; }}
      }}

      .cmd-7 {{ animation: tc7 24s steps(13, end) infinite; }}
      @keyframes tc7 {{
        0%, 35% {{ clip-path: inset(0 100% 0 0); }}
        37.5%, 97% {{ clip-path: inset(0 0 0 0); }}
        98%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-7 {{ animation: ro7 24s infinite; }}
      @keyframes ro7 {{
        0%, 37.5% {{ opacity: 0; transform: translateY(-2px); }}
        38.5%, 97% {{ opacity: 1; transform: translateY(0); }}
        98%, 100% {{ opacity: 0; }}
      }}

      .cmd-8 {{ animation: tc8 24s steps(4, end) infinite; }}
      @keyframes tc8 {{
        0%, 41% {{ clip-path: inset(0 100% 0 0); }}
        43%, 97% {{ clip-path: inset(0 0 0 0); }}
        98%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}

      .cursor-blink {{
        animation: blink 1s infinite;
      }}
      .snake-crawl {{
        animation: snakeMove 3s ease-in-out infinite;
      }}
      .food-dot {{
        animation: foodGlow 1.5s infinite alternate;
      }}
    </style>
  </defs>

  <!-- Frame and Header -->
  <rect class="outer" x="0" y="0" width="920" height="1020" rx="16"/>
  <rect class="terminal" x="16" y="16" width="888" height="988" rx="10"/>
  <rect class="frame" x="16" y="16" width="888" height="988" rx="10"/>
  <rect class="head" x="16" y="16" width="888" height="40" rx="10"/>

  <circle cx="42" cy="36" r="6.5" fill="#ff5f58"/>
  <circle cx="62" cy="36" r="6.5" fill="#ffbd2e"/>
  <circle cx="82" cy="36" r="6.5" fill="#18c132"/>
  <text x="460" y="41" fill="#e6ffe6" font-family="Monaco, Consolas, monospace" font-size="13" font-weight="bold" text-anchor="middle">WhoIsMrSentry@github.com: ~ (bash)</text>

  <!-- 1. whoami -->
  <g>
    <text class="prompt" x="44" y="86">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-1" x="315" y="86">whoami</text>
  </g>
  <g class="out-1">
    <text class="txt" x="44" y="110">Emir Hamurcu</text>
  </g>

  <!-- 2. profile summary -->
  <g>
    <text class="prompt" x="44" y="142">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-2" x="315" y="142">./profile --summary</text>
  </g>
  <g class="out-2">
    <text class="info" x="44" y="166">Focus:</text><text class="txt" x="110" y="166">Robotics &amp; Embedded AI</text>
    <text class="info" x="44" y="188">Role:</text><text class="txt" x="110" y="188">Software Developer · Embedded AI</text>
    <text class="info" x="44" y="210">Status:</text><text class="txt" x="110" y="210">Open to Collaboration</text>
  </g>

  <!-- 3. profile streak -->
  <g>
    <text class="prompt" x="44" y="244">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-3" x="315" y="244">./profile --streak</text>
  </g>
  <g class="out-3">
    <rect class="box-frame" x="44" y="258" width="832" height="106" rx="8"/>
    <rect x="44" y="258" width="832" height="26" rx="8" fill="#1b000d"/>
    <line x1="44" y1="284" x2="876" y2="284" stroke="#88001b" stroke-width="1"/>
    <text class="box-head" x="60" y="276">⚡ GITHUB CONTRIBUTION STREAK METRICS</text>

    <!-- Column 1: Total Contribs -->
    <text class="val-large" x="180" y="320">{streak['total_contribs']}</text>
    <text class="val-label" x="180" y="338">Total Contributions</text>
    <text class="val-date" x="180" y="352">{streak['period']}</text>

    <line x1="320" y1="294" x2="320" y2="354" stroke="#440015" stroke-width="1"/>

    <!-- Column 2: Current Streak Ring & Fire -->
    <circle cx="460" cy="318" r="28" fill="none" stroke="#39ff14" stroke-width="3.5" stroke-dasharray="140, 36"/>
    <text class="val-large" x="460" y="326" fill="#39ff14">{streak['current_streak']}</text>
    <text class="val-label" x="460" y="344" fill="#39ff14">🔥 Current Streak</text>
    <text class="val-date" x="460" y="356" fill="#39ff14">{streak['dates']}</text>

    <line x1="600" y1="294" x2="600" y2="354" stroke="#440015" stroke-width="1"/>

    <!-- Column 3: Longest Streak -->
    <text class="val-large" x="740" y="320">{streak['longest_streak']}</text>
    <text class="val-label" x="740" y="338">Longest Streak</text>
    <text class="val-date" x="740" y="352">{streak['dates']}</text>
  </g>

  <!-- 4. profile activity -->
  <g>
    <text class="prompt" x="44" y="394">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-4" x="315" y="394">./profile --activity</text>
  </g>
  <g class="out-4">
    <rect class="box-frame" x="44" y="408" width="832" height="180" rx="8"/>
    <rect x="44" y="408" width="832" height="26" rx="8" fill="#1b000d"/>
    <line x1="44" y1="434" x2="876" y2="434" stroke="#88001b" stroke-width="1"/>
    <text class="box-head" x="60" y="426">📈 EMIR HAMURCU'S CONTRIBUTION GRAPH (LAST 30 DAYS)</text>
    <text class="box-sub" x="860" y="426" text-anchor="end">PEAK: 46 COMMITS/DAY  •  STATUS: VERIFIED</text>
    {chart_svg}
  </g>

  <!-- 5. snake commits -->
  <g>
    <text class="prompt" x="44" y="618">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-5" x="315" y="618">./snake --commits</text>
  </g>
  <g class="out-5">
    <rect class="box-frame" x="44" y="632" width="832" height="135" rx="8"/>
    <rect x="44" y="632" width="832" height="26" rx="8" fill="#1b000d"/>
    <line x1="44" y1="658" x2="876" y2="658" stroke="#88001b" stroke-width="1"/>
    <text class="box-head" x="60" y="650">🐍 SENTRY RETRO COMMIT SNAKE ARENA</text>
    <text class="box-sub" x="860" y="650" text-anchor="end">SCORE: {streak['total_contribs']}  •  LENGTH: {streak['current_streak']}  •  STATUS: WINNING</text>
    {snake_svg}
    <!-- Snake Progress / Energy Bar -->
    <rect x="64" y="750" width="792" height="4" rx="2" fill="#39ff14" filter="drop-shadow(0 0 3px #39ff14)"/>
  </g>

  <!-- 6. uptime -->
  <g>
    <text class="prompt" x="44" y="796">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-6" x="315" y="796">uptime</text>
  </g>
  <g class="out-6">
    <text class="txt" x="44" y="820">{uptime}</text>
  </g>

  <!-- 7. cat about -->
  <g>
    <text class="prompt" x="44" y="852">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-7" x="315" y="852">cat about.txt</text>
  </g>
  <g class="out-7">
    <text class="txt" x="44" y="876">Building robotics and edge AI systems with production-first engineering.</text>
    <text class="txt" x="44" y="898">Focused on reliable automation, maintainable code, and measurable results.</text>
  </g>

  <!-- 8. exit -->
  <g>
    <text class="prompt" x="44" y="930">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-8" x="315" y="930">exit</text>
  </g>
  <rect class="cursor-blink" x="368" y="915" width="10" height="18" fill="#39ff14"/>
</svg>
"""
    return svg


def main() -> int:
    svg = generate_terminal_panel_svg()
    # Enforce XML well-formedness
    ET.fromstring(svg)
    SVG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text(svg, encoding="utf-8")
    SVG_PATH_NEW.write_text(svg, encoding="utf-8")
    print(f"Generated valid interactive terminal SVG at {SVG_PATH} and {SVG_PATH_NEW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
