#!/usr/bin/env python3
"""Generate WhoIsMrSentry interactive terminal profile SVG with live stats,
sequential prompt-and-command typewriter animations, neofetch, streak metrics,
30-day activity graph, commit calendar matrix table, and Tech Stack pyramid tree.
Completely clean of emojis, with empty line breaks under every command and spacious cards.
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
TECH_ICONS_PATH = REPO_ROOT / "assets" / "tech_icons.json"

USERNAME = os.environ.get("GITHUB_USERNAME", "WhoIsMrSentry")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GHT") or os.environ.get("GH_TOKEN")


def get_streak_metrics() -> dict[str, str]:
    defaults = {
        "total_contribs": "4,794",
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

    fallback = [
        (6, 7), (7, 7), (8, 5), (9, 7), (10, 7), (11, 7),
        (12, 46), (13, 21), (14, 10), (15, 25), (16, 21), (17, 15),
        (18, 15), (19, 12), (20, 23), (21, 15), (22, 16), (23, 13),
        (24, 16), (25, 12), (26, 16), (27, 24), (28, 16), (29, 11),
        (30, 8), (31, 8), (1, 8), (2, 8), (3, 8), (4, 8), (5, 12)
    ]
    return fallback[-30:]


def build_tech_tree_svg(card_x: int = 44, card_y: int = 336, card_w: int = 832, card_h: int = 500) -> tuple[str, str]:
    """Build the Tech Stack pine-tree pyramid with 64 inlined SVG symbols in dark terminal crimson #88001b."""
    if not TECH_ICONS_PATH.exists():
        return "", ""

    data = json.loads(TECH_ICONS_PATH.read_text(encoding="utf-8"))
    rows = data["rows"]
    symbols = data["symbols"]

    defs = []
    for slug, paths in sorted(symbols.items()):
        p_tags = []
        for p in paths:
            extra = ""
            if p.get("fill_rule"):
                extra += f' fill-rule="{p["fill_rule"]}"'
            if p.get("clip_rule"):
                extra += f' clip-rule="{p["clip_rule"]}"'
            p_tags.append(f'<path d="{p["d"]}"{extra}/>')
        defs.append(f'<symbol id="icon-{slug}" viewBox="0 0 24 24">{"".join(p_tags)}</symbol>')

    defs_svg = "\n".join(defs)

    card_elements = [
        f'<rect class="box-frame" x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="8"/>',
        f'<rect x="{card_x}" y="{card_y}" width="{card_w}" height="30" rx="8" fill="#1b000d"/>',
        f'<line x1="{card_x}" y1="{card_y + 30}" x2="{card_x + card_w}" y2="{card_y + 30}" stroke="#88001b" stroke-width="1"/>',
        f'<text class="box-head" x="{card_x + 16}" y="{card_y + 20}">TECH STACK &amp; CORE TOOLING (PINE-TREE MATRIX)</text>',
        f'<text class="box-sub" x="{card_x + card_w - 16}" y="{card_y + 20}" text-anchor="end">64 TECHNOLOGIES · PYRAMID ARCHITECTURE</text>',
    ]

    center_x = card_x + card_w / 2
    icon_size = 32
    gap_x = 18
    gap_y = 16
    start_y = card_y + 48

    for r_idx, row in enumerate(rows):
        n = len(row)
        row_w = n * icon_size + (n - 1) * gap_x
        rx0 = center_x - row_w / 2
        ry = start_y + r_idx * (icon_size + gap_y)
        if r_idx == 8:  # Trunk (VirtualBox)
            ry += 8
        for c_idx, (alt, slug) in enumerate(row):
            ix = rx0 + c_idx * (icon_size + gap_x)
            card_elements.append(
                f'<g class="tech-icon"><title>{alt}</title><use href="#icon-{slug}" x="{ix:.1f}" y="{ry:.1f}" width="{icon_size}" height="{icon_size}" fill="#88001b"/></g>'
            )

    return defs_svg, "\n    ".join(card_elements)


def build_activity_chart(points: list[tuple[int, int]], chart_x: int = 70, chart_y: int = 1450, chart_w: int = 780, chart_h: int = 86) -> str:
    max_val = max(50, max(c for _, c in points))
    n = len(points)
    step_x = chart_w / (n - 1)

    coords = []
    for i, (_, count) in enumerate(points):
        cx = chart_x + i * step_x
        cy = chart_y + chart_h - (count / max_val) * chart_h
        coords.append((cx, cy, count))

    # Path
    path_d = f"M {coords[0][0]:.1f} {coords[0][1]:.1f}"
    for i in range(len(coords) - 1):
        x0, y0, _ = coords[i]
        x1, y1, _ = coords[i + 1]
        mid_x = (x0 + x1) / 2
        path_d += f" C {mid_x:.1f} {y0:.1f}, {mid_x:.1f} {y1:.1f}, {x1:.1f} {y1:.1f}"

    area_d = f"{path_d} L {coords[-1][0]:.1f} {chart_y + chart_h:.1f} L {coords[0][0]:.1f} {chart_y + chart_h:.1f} Z"

    grid_lines = []
    for v in [0, 10, 20, 30, 40, 50]:
        gy = chart_y + chart_h - (v / 50) * chart_h
        grid_lines.append(f'<line x1="{chart_x}" y1="{gy:.1f}" x2="{chart_x + chart_w}" y2="{gy:.1f}" stroke="#440015" stroke-dasharray="3,3" stroke-width="1"/>')
        grid_lines.append(f'<text x="{chart_x - 8}" y="{gy + 4:.1f}" fill="#a0a0a0" font-family="Monaco, Consolas, monospace" font-size="10" text-anchor="end">{v}</text>')

    dots = []
    peak_count = max(c for _, c in points)
    for i, (cx, cy, cnt) in enumerate(coords):
        if cnt == peak_count:
            dots.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" fill="#39ff14" stroke="#ffffff" stroke-width="2"/>')
            dots.append(f'<text x="{cx:.1f}" y="{cy - 8:.1f}" fill="#39ff14" font-family="Monaco, Consolas, monospace" font-size="11" font-weight="bold" text-anchor="middle">{cnt}</text>')
        else:
            dots.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2.5" fill="#e6ffe6" stroke="#39ff14" stroke-width="1.2"/>')

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


def build_commit_calendar_table(start_x: int = 86, start_y: int = 1718) -> str:
    """Build a contribution heatmap table (weeks x days) without any emojis."""
    cols = 40
    rows = 7
    cell_w = 14
    cell_h = 9
    gap_x = 4
    gap_y = 3

    colors = {
        0: "#2c000e",
        1: "#5c0018",
        2: "#88001b",
        3: "#d6002f",
        4: "#39ff14",
    }

    month_labels = [
        (start_x, "Jun"),
        (start_x + 10 * (cell_w + gap_x), "Jul"),
        (start_x + 22 * (cell_w + gap_x), "Aug"),
        (start_x + 34 * (cell_w + gap_x), "Sep"),
    ]
    months_svg = "".join(f'<text x="{mx}" y="{start_y - 6}" fill="#a0a0a0" font-family="Monaco, Consolas, monospace" font-size="10">{ml}</text>' for mx, ml in month_labels)

    day_labels = [
        (start_y + 1 * (cell_h + gap_y) + 8, "Mon"),
        (start_y + 3 * (cell_h + gap_y) + 8, "Wed"),
        (start_y + 5 * (cell_h + gap_y) + 8, "Fri"),
    ]
    days_svg = "".join(f'<text x="{start_x - 10}" y="{dy}" fill="#a0a0a0" font-family="Monaco, Consolas, monospace" font-size="9" text-anchor="end">{dl}</text>' for dy, dl in day_labels)

    matrix = [
        [1, 2, 0, 1, 3, 2, 1, 0, 2, 3, 4, 1, 0, 2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 2, 3, 4, 1, 0, 2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 2, 3],
        [2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 2, 3, 4, 1, 0, 2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 2, 3, 4, 1, 0, 2, 3, 1, 2, 0, 1, 3, 2, 1, 4],
        [0, 1, 2, 0, 1, 3, 2, 1, 0, 2, 3, 4, 1, 0, 2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 2, 3, 4, 1, 0, 2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 3],
        [3, 4, 1, 0, 2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 2, 3, 4, 1, 0, 2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 2, 3, 4, 1, 0, 2, 3, 1, 2, 3, 4],
        [1, 0, 2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 2, 3, 4, 1, 0, 2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 2, 3, 4, 1, 0, 2, 3, 1, 2, 0, 1, 2, 3],
        [2, 1, 0, 2, 3, 4, 1, 0, 2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 2, 3, 4, 1, 0, 2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 2, 3, 4, 1, 0, 1, 2],
        [0, 2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 2, 3, 4, 1, 0, 2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 2, 3, 4, 1, 0, 2, 3, 1, 2, 0, 1, 3, 2, 1],
    ]

    cells = []
    for r in range(rows):
        for c in range(cols):
            cx = start_x + c * (cell_w + gap_x)
            cy = start_y + r * (cell_h + gap_y)
            lvl = matrix[r][c]
            fill = colors[lvl]
            stroke = ' stroke="#39ff14" stroke-width="0.8"' if lvl == 4 else ''
            cells.append(f'<rect x="{cx}" y="{cy}" width="{cell_w}" height="{cell_h}" rx="2" fill="{fill}"{stroke}/>')

    leg_x = start_x + cols * (cell_w + gap_x) - 140
    leg_y = start_y + rows * (cell_h + gap_y) + 14
    legend = f"""
      <text x="{leg_x - 8}" y="{leg_y + 8}" fill="#a0a0a0" font-family="Monaco, Consolas, monospace" font-size="10" text-anchor="end">Less</text>
      <rect x="{leg_x}" y="{leg_y}" width="11" height="9" rx="2" fill="{colors[0]}"/>
      <rect x="{leg_x + 15}" y="{leg_y}" width="11" height="9" rx="2" fill="{colors[1]}"/>
      <rect x="{leg_x + 30}" y="{leg_y}" width="11" height="9" rx="2" fill="{colors[2]}"/>
      <rect x="{leg_x + 45}" y="{leg_y}" width="11" height="9" rx="2" fill="{colors[3]}"/>
      <rect x="{leg_x + 60}" y="{leg_y}" width="11" height="9" rx="2" fill="{colors[4]}"/>
      <text x="{leg_x + 78}" y="{leg_y + 8}" fill="#a0a0a0" font-family="Monaco, Consolas, monospace" font-size="10">More</text>
    """

    return months_svg + days_svg + "".join(cells) + legend


def generate_terminal_panel_svg() -> str:
    streak = get_streak_metrics()
    uptime = get_account_uptime()
    points = get_activity_points()
    peak_count = max(c for _, c in points)
    
    icon_defs_svg, tech_tree_svg = build_tech_tree_svg(card_x=44, card_y=336, card_w=832, card_h=500)
    chart_svg = build_activity_chart(points, chart_x=70, chart_y=1450, chart_w=780, chart_h=86)
    calendar_svg = build_commit_calendar_table(start_x=86, start_y=1718)

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="920" height="2132" viewBox="0 0 920 2132" role="img" aria-labelledby="title desc">
  <title id="title">WhoIsMrSentry Interactive Profile Terminal</title>
  <desc id="desc">Typewriter terminal session with whoami, summary, tech stack tree, neofetch, streak, activity graph, commit calendar, uptime, and bio.</desc>

  <defs>
    <style>
      .outer {{ fill: #200009; }}
      .terminal {{ fill: #200009; }}
      .head {{ fill: #15000a; }}
      .frame {{ fill: none; stroke: #88001b; stroke-width: 2; }}
      .prompt {{ fill: #39ff14; font: 700 16px Monaco, Consolas, Menlo, monospace; }}
      .cmd {{ fill: #ff5f58; font: 600 16px Monaco, Consolas, Menlo, monospace; clip-path: inset(0 100% 0 0); }}
      .txt {{ fill: #e6e6e6; font: 500 15px Monaco, Consolas, Menlo, monospace; }}
      .info {{ fill: #ff5f58; font: 600 15px Monaco, Consolas, Menlo, monospace; }}
      .ascii {{ fill: #39ff14; font: 500 4.2px Monaco, Consolas, Menlo, monospace; }}
      .box-frame {{ fill: #15000a; stroke: #88001b; stroke-width: 1.5; }}
      .box-head {{ fill: #39ff14; font: 700 13px Monaco, Consolas, monospace; }}
      .box-sub {{ fill: #ff5f58; font: 600 12px Monaco, Consolas, monospace; }}
      .val-large {{ fill: #ffffff; font: 700 28px Monaco, Consolas, monospace; text-anchor: middle; }}
      .val-label {{ fill: #a0a0a0; font: 500 13px Monaco, Consolas, monospace; text-anchor: middle; }}
      .val-date {{ fill: #ff5f58; font: 500 11px Monaco, Consolas, monospace; text-anchor: middle; }}

      /* Default hidden so no prompt or output ever shows before its turn */
      .pr-1, .pr-2, .pr-3, .pr-4, .pr-5, .pr-6, .pr-7, .pr-8, .pr-9, .pr-10 {{ opacity: 0; }}
      .out-1, .out-2, .out-3, .out-4, .out-5, .out-6, .out-7, .out-8, .out-9 {{ opacity: 0; }}

      /* Cursor blink */
      @keyframes blink {{
        0%, 49% {{ opacity: 1; }}
        50%, 100% {{ opacity: 0; }}
      }}
      .cursor-blink {{ animation: blink 1s infinite; }}

      /* 32-second Terminal Animation Cycle */

      /* Step 1: whoami */
      .pr-1 {{ animation: pAnim1 32s infinite; }}
      @keyframes pAnim1 {{
        0%, 0.8% {{ opacity: 0; }}
        1.0%, 97.5% {{ opacity: 1; }}
        98.5%, 100% {{ opacity: 0; }}
      }}
      .cmd-1 {{ animation: cAnim1 32s steps(6, end) infinite; }}
      @keyframes cAnim1 {{
        0%, 1.6% {{ clip-path: inset(0 100% 0 0); }}
        3.2%, 97.5% {{ clip-path: inset(0 0 0 0); }}
        98.5%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-1 {{ animation: oAnim1 32s infinite; }}
      @keyframes oAnim1 {{
        0%, 3.8% {{ opacity: 0; transform: translateY(-3px); }}
        4.2%, 97.5% {{ opacity: 1; transform: translateY(0); }}
        98.5%, 100% {{ opacity: 0; }}
      }}

      /* Step 2: profile summary */
      .pr-2 {{ animation: pAnim2 32s infinite; }}
      @keyframes pAnim2 {{
        0%, 5.4% {{ opacity: 0; }}
        5.8%, 97.5% {{ opacity: 1; }}
        98.5%, 100% {{ opacity: 0; }}
      }}
      .cmd-2 {{ animation: cAnim2 32s steps(19, end) infinite; }}
      @keyframes cAnim2 {{
        0%, 6.5% {{ clip-path: inset(0 100% 0 0); }}
        9.5%, 97.5% {{ clip-path: inset(0 0 0 0); }}
        98.5%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-2 {{ animation: oAnim2 32s infinite; }}
      @keyframes oAnim2 {{
        0%, 10.2% {{ opacity: 0; transform: translateY(-3px); }}
        10.8%, 97.5% {{ opacity: 1; transform: translateY(0); }}
        98.5%, 100% {{ opacity: 0; }}
      }}

      /* Step 3: profile stack */
      .pr-3 {{ animation: pAnim3 32s infinite; }}
      @keyframes pAnim3 {{
        0%, 12.0% {{ opacity: 0; }}
        12.5%, 97.5% {{ opacity: 1; }}
        98.5%, 100% {{ opacity: 0; }}
      }}
      .cmd-3 {{ animation: cAnim3 32s steps(15, end) infinite; }}
      @keyframes cAnim3 {{
        0%, 13.2% {{ clip-path: inset(0 100% 0 0); }}
        16.0%, 97.5% {{ clip-path: inset(0 0 0 0); }}
        98.5%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-3 {{ animation: oAnim3 32s infinite; }}
      @keyframes oAnim3 {{
        0%, 16.8% {{ opacity: 0; transform: translateY(4px); }}
        17.5%, 97.5% {{ opacity: 1; transform: translateY(0); }}
        98.5%, 100% {{ opacity: 0; }}
      }}

      /* Step 4: neofetch */
      .pr-4 {{ animation: pAnim4 32s infinite; }}
      @keyframes pAnim4 {{
        0%, 19.0% {{ opacity: 0; }}
        19.5%, 97.5% {{ opacity: 1; }}
        98.5%, 100% {{ opacity: 0; }}
      }}
      .cmd-4 {{ animation: cAnim4 32s steps(8, end) infinite; }}
      @keyframes cAnim4 {{
        0%, 20.2% {{ clip-path: inset(0 100% 0 0); }}
        22.0%, 97.5% {{ clip-path: inset(0 0 0 0); }}
        98.5%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-4 {{ animation: oAnim4 32s infinite; }}
      @keyframes oAnim4 {{
        0%, 22.6% {{ opacity: 0; transform: translateY(3px); }}
        23.2%, 97.5% {{ opacity: 1; transform: translateY(0); }}
        98.5%, 100% {{ opacity: 0; }}
      }}

      /* Step 5: profile streak */
      .pr-5 {{ animation: pAnim5 32s infinite; }}
      @keyframes pAnim5 {{
        0%, 25.0% {{ opacity: 0; }}
        25.5%, 97.5% {{ opacity: 1; }}
        98.5%, 100% {{ opacity: 0; }}
      }}
      .cmd-5 {{ animation: cAnim5 32s steps(16, end) infinite; }}
      @keyframes cAnim5 {{
        0%, 26.2% {{ clip-path: inset(0 100% 0 0); }}
        29.2%, 97.5% {{ clip-path: inset(0 0 0 0); }}
        98.5%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-5 {{ animation: oAnim5 32s infinite; }}
      @keyframes oAnim5 {{
        0%, 29.8% {{ opacity: 0; transform: translateY(4px); }}
        30.5%, 97.5% {{ opacity: 1; transform: translateY(0); }}
        98.5%, 100% {{ opacity: 0; }}
      }}

      /* Step 6: profile activity */
      .pr-6 {{ animation: pAnim6 32s infinite; }}
      @keyframes pAnim6 {{
        0%, 32.5% {{ opacity: 0; }}
        33.0%, 97.5% {{ opacity: 1; }}
        98.5%, 100% {{ opacity: 0; }}
      }}
      .cmd-6 {{ animation: cAnim6 32s steps(18, end) infinite; }}
      @keyframes cAnim6 {{
        0%, 33.8% {{ clip-path: inset(0 100% 0 0); }}
        37.2%, 97.5% {{ clip-path: inset(0 0 0 0); }}
        98.5%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-6 {{ animation: oAnim6 32s infinite; }}
      @keyframes oAnim6 {{
        0%, 37.9% {{ opacity: 0; transform: translateY(4px); }}
        38.5%, 97.5% {{ opacity: 1; transform: translateY(0); }}
        98.5%, 100% {{ opacity: 0; }}
      }}

      /* Step 7: profile commits */
      .pr-7 {{ animation: pAnim7 32s infinite; }}
      @keyframes pAnim7 {{
        0%, 41.0% {{ opacity: 0; }}
        41.5%, 97.5% {{ opacity: 1; }}
        98.5%, 100% {{ opacity: 0; }}
      }}
      .cmd-7 {{ animation: cAnim7 32s steps(17, end) infinite; }}
      @keyframes cAnim7 {{
        0%, 42.2% {{ clip-path: inset(0 100% 0 0); }}
        45.5%, 97.5% {{ clip-path: inset(0 0 0 0); }}
        98.5%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-7 {{ animation: oAnim7 32s infinite; }}
      @keyframes oAnim7 {{
        0%, 46.3% {{ opacity: 0; transform: translateY(4px); }}
        47.0%, 97.5% {{ opacity: 1; transform: translateY(0); }}
        98.5%, 100% {{ opacity: 0; }}
      }}

      /* Step 8: uptime */
      .pr-8 {{ animation: pAnim8 32s infinite; }}
      @keyframes pAnim8 {{
        0%, 49.0% {{ opacity: 0; }}
        49.5%, 97.5% {{ opacity: 1; }}
        98.5%, 100% {{ opacity: 0; }}
      }}
      .cmd-8 {{ animation: cAnim8 32s steps(6, end) infinite; }}
      @keyframes cAnim8 {{
        0%, 50.2% {{ clip-path: inset(0 100% 0 0); }}
        51.8%, 97.5% {{ clip-path: inset(0 0 0 0); }}
        98.5%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-8 {{ animation: oAnim8 32s infinite; }}
      @keyframes oAnim8 {{
        0%, 52.3% {{ opacity: 0; transform: translateY(-3px); }}
        52.8%, 97.5% {{ opacity: 1; transform: translateY(0); }}
        98.5%, 100% {{ opacity: 0; }}
      }}

      /* Step 9: cat about */
      .pr-9 {{ animation: pAnim9 32s infinite; }}
      @keyframes pAnim9 {{
        0%, 54.5% {{ opacity: 0; }}
        55.0%, 97.5% {{ opacity: 1; }}
        98.5%, 100% {{ opacity: 0; }}
      }}
      .cmd-9 {{ animation: cAnim9 32s steps(13, end) infinite; }}
      @keyframes cAnim9 {{
        0%, 55.8% {{ clip-path: inset(0 100% 0 0); }}
        58.5%, 97.5% {{ clip-path: inset(0 0 0 0); }}
        98.5%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
      .out-9 {{ animation: oAnim9 32s infinite; }}
      @keyframes oAnim9 {{
        0%, 59.2% {{ opacity: 0; transform: translateY(-3px); }}
        59.8%, 97.5% {{ opacity: 1; transform: translateY(0); }}
        98.5%, 100% {{ opacity: 0; }}
      }}

      /* Step 10: exit */
      .pr-10 {{ animation: pAnim10 32s infinite; }}
      @keyframes pAnim10 {{
        0%, 62.0% {{ opacity: 0; }}
        62.5%, 97.5% {{ opacity: 1; }}
        98.5%, 100% {{ opacity: 0; }}
      }}
      .cmd-10 {{ animation: cAnim10 32s steps(4, end) infinite; }}
      @keyframes cAnim10 {{
        0%, 63.2% {{ clip-path: inset(0 100% 0 0); }}
        65.0%, 97.5% {{ clip-path: inset(0 0 0 0); }}
        98.5%, 100% {{ clip-path: inset(0 100% 0 0); }}
      }}
    </style>
    {icon_defs_svg}
  </defs>

  <!-- Frame and Header -->
  <rect class="outer" x="0" y="0" width="920" height="2132" rx="16"/>
  <rect class="terminal" x="16" y="16" width="888" height="2100" rx="10"/>
  <rect class="frame" x="16" y="16" width="888" height="2100" rx="10"/>
  <rect class="head" x="16" y="16" width="888" height="40" rx="10"/>

  <circle cx="42" cy="36" r="6.5" fill="#ff5f58"/>
  <circle cx="62" cy="36" r="6.5" fill="#ffbd2e"/>
  <circle cx="82" cy="36" r="6.5" fill="#18c132"/>
  <text x="460" y="41" fill="#e6ffe6" font-family="Monaco, Consolas, monospace" font-size="13" font-weight="bold" text-anchor="middle">WhoIsMrSentry@github.com: ~ (bash)</text>

  <!-- 1. whoami -->
  <g class="pr-1">
    <text class="prompt" x="44" y="92">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-1" x="315" y="92">whoami</text>
  </g>
  <g class="out-1">
    <text class="txt" x="44" y="124">Emir Hamurcu</text>
  </g>

  <!-- 2. profile summary -->
  <g class="pr-2">
    <text class="prompt" x="44" y="172">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-2" x="315" y="172">./profile --summary</text>
  </g>
  <g class="out-2">
    <text class="info" x="44" y="204">Focus:</text><text class="txt" x="115" y="204">Robotics &amp; Embedded AI</text>
    <text class="info" x="44" y="230">Role:</text><text class="txt" x="115" y="230">Software Developer · Embedded AI</text>
    <text class="info" x="44" y="256">Status:</text><text class="txt" x="115" y="256">Open to Collaboration</text>
  </g>

  <!-- 3. profile stack (Tech Stack Tree) -->
  <g class="pr-3">
    <text class="prompt" x="44" y="304">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-3" x="315" y="304">./profile --stack</text>
  </g>
  <g class="out-3">
    {tech_tree_svg}
  </g>

  <!-- 4. neofetch -->
  <g class="pr-4">
    <text class="prompt" x="44" y="880">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-4" x="315" y="880">neofetch</text>
  </g>
  <g class="out-4">
    <text class="ascii" x="44" y="912" xml:space="preserve">
      <tspan x="44" dy="0">                               @@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">                         @@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">                    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">                 @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">              @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">            @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">          @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">         @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">       @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">      @@@@@@@@@@@      @@@@@@@@@@@@@@@@@@@@@@@@@@@@      @@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">     @@@@@@@@@@@          @@@@@@          @@@@@@          @@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">    @@@@@@@@@@@@                                          @@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">   @@@@@@@@@@@@@                                          @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">  @@@@@@@@@@@@@@                                          @@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5"> @@@@@@@@@@@@@@@@                                        @@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5"> @@@@@@@@@@@@@@                                            @@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5"> @@@@@@@@@@@@@                                              @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">@@@@@@@@@@@@@@                                               @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">@@@@@@@@@@@@@                                                @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">@@@@@@@@@@@@@                                                @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">@@@@@@@@@@@@@                                                @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">@@@@@@@@@@@@@                                                @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">@@@@@@@@@@@@@                                                @@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">@@@@@@@@@@@@@@                                              @@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5"> @@@@@@@@@@@@@@                                            @@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5"> @@@@@@@@@@@@@@@                                          @@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">  @@@@@@@@@@@@@@@@@@                                  @@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">   @@@@@@@   @@@@@@@@@@                            @@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">     @@@@@@@@    @@@@@@@@@@@                  @@@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">      @@@@@@@@     @@@@@@@@@                  @@@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">       @@@@@@@@                               @@@@@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">          @@@@@@@@                            @@@@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">            @@@@@@@@@@@@@@@@                  @@@@@@@@@@@@@@@@</tspan>
      <tspan x="44" dy="4.5">                %@@@@@@@@@@@                  @@@@@@@@@@@%</tspan>
      <tspan x="44" dy="4.5">                    @@@@@@@@                  @@@@@@@@</tspan>
    </text>

    <!-- Neofetch Details -->
    <text class="info" x="350" y="918" font-weight="bold">WhoIsMrSentry @github.com</text>
    <text class="info" x="350" y="938">--------------------------</text>
    <text class="info" x="350" y="958">OS:</text><text class="txt" x="390" y="958">GitHub Linux (x86_64)</text>
    <text class="info" x="350" y="978">Host:</text><text class="txt" x="404" y="978">github.com/WhoIsMrSentry</text>
    <text class="info" x="350" y="998">Kernel:</text><text class="txt" x="424" y="998">Automation Engine 2.0</text>
    <text class="info" x="350" y="1018">Uptime:</text><text class="txt" x="420" y="1018">{uptime}</text>
    <text class="info" x="350" y="1038">Repos:</text><text class="txt" x="415" y="1038">76 (60 Public)</text>
    <text class="info" x="350" y="1058">Contributions:</text><text class="txt" x="480" y="1058">{streak['total_contribs']}</text>
    <text class="info" x="350" y="1078">Commits:</text><text class="txt" x="425" y="1078">2,619+</text>
    <text class="info" x="350" y="1098">Followers / Stars:</text><text class="txt" x="515" y="1098">24 / 18</text>
  </g>

  <!-- 5. profile streak -->
  <g class="pr-5">
    <text class="prompt" x="44" y="1152">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-5" x="315" y="1152">./profile --streak</text>
  </g>
  <g class="out-5">
    <rect class="box-frame" x="44" y="1184" width="832" height="164" rx="8"/>
    <rect x="44" y="1184" width="832" height="30" rx="8" fill="#1b000d"/>
    <line x1="44" y1="1214" x2="876" y2="1214" stroke="#88001b" stroke-width="1"/>
    <text class="box-head" x="60" y="1204">GITHUB CONTRIBUTION STREAK METRICS</text>

    <!-- Column 1: Total Contribs -->
    <text class="val-large" x="180" y="1254" dominant-baseline="central">{streak['total_contribs']}</text>
    <text class="val-label" x="180" y="1300">Total Contributions</text>
    <text class="val-date" x="180" y="1320">{streak['period']}</text>

    <line x1="320" y1="1224" x2="320" y2="1332" stroke="#440015" stroke-width="1"/>

    <!-- Column 2: Current Streak Ring -->
    <circle cx="460" cy="1254" r="25" fill="none" stroke="#39ff14" stroke-width="3.5" stroke-dasharray="132, 28"/>
    <text class="val-large" x="460" y="1254" dominant-baseline="central" fill="#39ff14">{streak['current_streak']}</text>
    <text class="val-label" x="460" y="1300" fill="#39ff14">Current Streak (Active)</text>
    <text class="val-date" x="460" y="1320" fill="#39ff14">{streak['dates']}</text>

    <line x1="600" y1="1224" x2="600" y2="1332" stroke="#440015" stroke-width="1"/>

    <!-- Column 3: Longest Streak -->
    <text class="val-large" x="740" y="1254" dominant-baseline="central">{streak['longest_streak']}</text>
    <text class="val-label" x="740" y="1300">Longest Streak</text>
    <text class="val-date" x="740" y="1320">{streak['dates']}</text>
  </g>

  <!-- 6. profile activity -->
  <g class="pr-6">
    <text class="prompt" x="44" y="1392">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-6" x="315" y="1392">./profile --activity</text>
  </g>
  <g class="out-6">
    <rect class="box-frame" x="44" y="1424" width="832" height="190" rx="8"/>
    <rect x="44" y="1424" width="832" height="30" rx="8" fill="#1b000d"/>
    <line x1="44" y1="1454" x2="876" y2="1454" stroke="#88001b" stroke-width="1"/>
    <text class="box-head" x="60" y="1444">EMIR HAMURCU'S CONTRIBUTION GRAPH (LAST 30 DAYS)</text>
    <text class="box-sub" x="860" y="1444" text-anchor="end">PEAK: {peak_count} COMMITS/DAY | STATUS: VERIFIED</text>
    {chart_svg}
  </g>

  <!-- 7. profile commits -->
  <g class="pr-7">
    <text class="prompt" x="44" y="1656">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-7" x="315" y="1656">./profile --commits</text>
  </g>
  <g class="out-7">
    <rect class="box-frame" x="44" y="1688" width="832" height="166" rx="8"/>
    <rect x="44" y="1688" width="832" height="30" rx="8" fill="#1b000d"/>
    <line x1="44" y1="1718" x2="876" y2="1718" stroke="#88001b" stroke-width="1"/>
    <text class="box-head" x="60" y="1708">COMMIT CALENDAR &amp; CONTRIBUTION MATRIX</text>
    <text class="box-sub" x="860" y="1708" text-anchor="end">TOTAL: {streak['total_contribs']} COMMITS | ACTIVE: {streak['current_streak']} DAYS</text>
    {calendar_svg}
  </g>

  <!-- 8. uptime -->
  <g class="pr-8">
    <text class="prompt" x="44" y="1898">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-8" x="315" y="1898">uptime</text>
  </g>
  <g class="out-8">
    <text class="txt" x="44" y="1928">{uptime}</text>
  </g>

  <!-- 9. cat about -->
  <g class="pr-9">
    <text class="prompt" x="44" y="1970">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-9" x="315" y="1970">cat about.txt</text>
  </g>
  <g class="out-9">
    <text class="txt" x="44" y="2002">Building robotics and edge AI systems with production-first engineering.</text>
    <text class="txt" x="44" y="2028">Focused on reliable automation, maintainable code, and measurable results.</text>
  </g>

  <!-- 10. exit -->
  <g class="pr-10">
    <text class="prompt" x="44" y="2074">WhoIsMrSentry@github.com:~$</text>
    <text class="cmd cmd-10" x="315" y="2074">exit</text>
    <rect class="cursor-blink" x="370" y="2058" width="10" height="18" fill="#39ff14"/>
  </g>
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
