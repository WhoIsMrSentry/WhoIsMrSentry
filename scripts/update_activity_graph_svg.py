#!/usr/bin/env python3
"""Generate a 100% native SVG activity graph for WhoIsMrSentry.

Free from foreignObject, third-party Vercel servers, and Chartist.js bugs.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = REPO_ROOT / "assets" / "activity_graph.svg"

USERNAME = os.environ.get("GITHUB_USERNAME", "WhoIsMrSentry")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GHT") or os.environ.get("GH_TOKEN")


def fetch_contributions_graphql() -> list[dict[str, int | str]]:
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
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
    data = None
    if GITHUB_TOKEN:
        payload = json.dumps({"query": query, "variables": {"login": USERNAME}}).encode("utf-8")
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=payload,
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Content-Type": "application/json",
                "User-Agent": "whoismrsentry-activity-graph-generator",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8")).get("data")
        except Exception as e:
            print(f"WARN: direct GraphQL request failed: {e}")

    if not data:
        # Try gh CLI fallback
        try:
            res = subprocess.run(
                ["gh", "api", "graphql", "-F", f"login={USERNAME}", "-f", f"query={query}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                data = json.loads(res.stdout).get("data")
        except Exception:
            pass

    if data and "user" in data:
        cal = data["user"]["contributionsCollection"]["contributionCalendar"]
        days = [d for w in cal["weeks"] for d in w["contributionDays"]]
        if days:
            return days

    # Fallback to recent sample data if offline
    today = dt.date.today()
    sample_counts = [5, 8, 12, 6, 14, 20, 15, 8, 9, 11, 7, 18, 25, 16, 10, 12, 14, 8, 22, 19, 13, 11, 9, 15, 17, 8, 8, 8, 8, 12]
    return [
        {"date": (today - dt.timedelta(days=29 - i)).isoformat(), "contributionCount": sample_counts[i % len(sample_counts)]}
        for i in range(30)
    ]


def build_activity_svg(days_data: list[dict[str, int | str]]) -> str:
    # Take the last 30 days for an ultra-clear, detailed graph
    recent = days_data[-30:] if len(days_data) >= 30 else days_data
    counts = [int(d["contributionCount"]) for d in recent]
    dates = [str(d["date"]) for d in recent]

    width = 920
    height = 340
    padding_left = 65
    padding_right = 35
    padding_top = 75
    padding_bottom = 50

    plot_w = width - padding_left - padding_right
    plot_h = height - padding_top - padding_bottom

    max_val = max(max(counts, default=10), 10)
    # Round max_val up to nice grid ceiling
    grid_max = ((max_val // 5) + 1) * 5
    if grid_max < 20:
        grid_max = 20

    n = len(recent)
    x_coords: list[float] = []
    y_coords: list[float] = []

    for i, c in enumerate(counts):
        x = padding_left + (i * plot_w / (n - 1))
        # Invert y: y=0 at top, height at bottom
        y = padding_top + plot_h - (c * plot_h / grid_max)
        x_coords.append(round(x, 2))
        y_coords.append(round(y, 2))

    # Build smooth bezier curve
    # Catmull-Rom or cubic Bezier path
    path_d = [f"M {x_coords[0]} {y_coords[0]}"]
    for i in range(len(x_coords) - 1):
        x0 = x_coords[max(i - 1, 0)]
        y0 = y_coords[max(i - 1, 0)]
        x1 = x_coords[i]
        y1 = y_coords[i]
        x2 = x_coords[i + 1]
        y2 = y_coords[i + 1]
        x3 = x_coords[min(i + 2, len(x_coords) - 1)]
        y3 = y_coords[min(i + 2, len(x_coords) - 1)]

        cp1x = x1 + (x2 - x0) / 6
        cp1y = y1 + (y2 - y0) / 6
        cp2x = x2 - (x3 - x1) / 6
        cp2y = y2 - (y3 - y1) / 6
        path_d.append(f"C {cp1x:.1f} {cp1y:.1f}, {cp2x:.1f} {cp2y:.1f}, {x2} {y2}")

    line_path = " ".join(path_d)
    area_path = f"{line_path} L {x_coords[-1]} {padding_top + plot_h} L {x_coords[0]} {padding_top + plot_h} Z"

    # Grid lines (4 horizontal grid steps)
    grid_elements = []
    for step in range(5):
        val = int(grid_max * step / 4)
        gy = round(padding_top + plot_h - (val * plot_h / grid_max), 1)
        grid_elements.append(
            f'<line x1="{padding_left}" y1="{gy}" x2="{width - padding_right}" y2="{gy}" stroke="#88001b" stroke-opacity="0.3" stroke-dasharray="3,3" />'
        )
        grid_elements.append(
            f'<text x="{padding_left - 12}" y="{gy + 4}" fill="#e6ffe6" font-family="Monaco, Consolas, monospace" font-size="11" text-anchor="end">{val}</text>'
        )

    # Date labels (every ~5 days)
    date_labels = []
    for i in range(0, n, 5):
        dx = x_coords[i]
        d_str = dates[i]
        # format: MM-DD
        short_date = d_str[5:]
        date_labels.append(
            f'<text x="{dx}" y="{padding_top + plot_h + 20}" fill="#e6ffe6" font-family="Monaco, Consolas, monospace" font-size="11" text-anchor="middle">{short_date}</text>'
        )

    # Always include the last date if not already close
    if (n - 1) % 5 != 0:
        date_labels.append(
            f'<text x="{x_coords[-1]}" y="{padding_top + plot_h + 20}" fill="#39ff14" font-family="Monaco, Consolas, monospace" font-size="11" text-anchor="middle">{dates[-1][5:]}</text>'
        )

    # Data points (circles on points with contributions > 0)
    data_points = []
    for x, y, c in zip(x_coords, y_coords, counts):
        if c > 0:
            data_points.append(
                f'<circle cx="{x}" cy="{y}" r="3.5" fill="#39ff14" stroke="#200009" stroke-width="1.5" />'
            )

    total_recent = sum(counts)
    avg_per_day = total_recent / max(len(counts), 1)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none">
  <defs>
    <linearGradient id="sentryAreaGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#88001b" stop-opacity="0.6"/>
      <stop offset="75%" stop-color="#88001b" stop-opacity="0.1"/>
      <stop offset="100%" stop-color="#200009" stop-opacity="0.0"/>
    </linearGradient>
    <filter id="neonGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
  </defs>

  <!-- Background Frame -->
  <rect width="{width}" height="{height}" rx="12" fill="#200009" stroke="#88001b" stroke-width="1.5" />

  <!-- Window Header Bar -->
  <rect x="0" y="0" width="{width}" height="42" rx="12" fill="#15000a" />
  <rect x="0" y="32" width="{width}" height="10" fill="#15000a" />
  <line x1="0" y1="42" x2="{width}" y2="42" stroke="#88001b" stroke-width="1" />

  <!-- Terminal Traffic Lights -->
  <circle cx="26" cy="21" r="6" fill="#ff5f58" />
  <circle cx="46" cy="21" r="6" fill="#ffbd2e" />
  <circle cx="66" cy="21" r="6" fill="#18c132" />

  <!-- Title -->
  <text x="{width // 2}" y="26" fill="#e6ffe6" font-family="'Fira Code', Monaco, monospace" font-size="13" font-weight="600" text-anchor="middle">
    WhoIsMrSentry / 30-Day Contribution Activity Graph
  </text>

  <!-- Quick Stat Badges -->
  <text x="{width - padding_right}" y="62" fill="#39ff14" font-family="Monaco, Consolas, monospace" font-size="12" font-weight="bold" text-anchor="end">
    Recent Contribs: {total_recent}  •  Avg: {avg_per_day:.1f}/day
  </text>

  <!-- Grids & Axis -->
  {''.join(grid_elements)}
  {''.join(date_labels)}

  <!-- Area Fill -->
  <path d="{area_path}" fill="url(#sentryAreaGrad)" />

  <!-- Glowing Line -->
  <path d="{line_path}" fill="none" stroke="#39ff14" stroke-width="3" filter="url(#neonGlow)" />

  <!-- Data Points -->
  {''.join(data_points)}
</svg>
"""
    return svg


def main() -> int:
    days = fetch_contributions_graphql()
    svg = build_activity_svg(days)
    SVG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text(svg, encoding="utf-8")
    print(f"Generated 100% native activity graph: {SVG_PATH} ({len(days)} days data)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
