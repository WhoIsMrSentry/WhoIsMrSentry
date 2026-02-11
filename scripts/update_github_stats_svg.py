import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = REPO_ROOT / "github_stats.svg"

USERNAME = os.environ.get("GITHUB_USERNAME", "WhoIsMrSentry")
TOTAL_REPOS_STATIC = os.environ.get("TOTAL_REPOS", "46")  # user wants to update manually; default 46

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

LABEL_X = 30.059999999999995
# In this SVG template, one monospace character is ~1.002 units wide (see existing x deltas).
CHAR_W = 1.002


def fmt_x(x: float) -> str:
    s = f"{x:.3f}"
    return s.rstrip("0").rstrip(".")


def value_x_for_label(label: str) -> str:
    # +1 for a single space between label and value.
    return fmt_x(LABEL_X + (len(label) + 1) * CHAR_W)


def extract_symbol_value(svg: str, symbol_id: str, *, default: str = "N/A") -> str:
    """Extract the last <text class="g">...</text> value from a symbol block."""
    m = re.search(rf'<symbol id="{re.escape(symbol_id)}">(.*?)</symbol>', svg)
    if not m:
        return default
    inner = m.group(1)
    vals = re.findall(r'class="g">([^<]+)</text>', inner)
    if not vals:
        return default
    return vals[-1]


def make_stat_line(blocks: list[tuple[str, str]], label: str, value: str) -> str:
    parts: list[str] = []
    for x, block_text in blocks:
        parts.append(f'<text x="{x}" y="1.67" class="i">{block_text}</text>')

    parts.append(f'<text x="{fmt_x(LABEL_X)}" y="1.67" class="j">{label}</text>')
    parts.append(f'<text x="{value_x_for_label(label)}" y="1.67" class="g">{value}</text>')
    return "".join(parts)


def http_json(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
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
            "User-Agent": "whoismrsentry-profile-stats",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]


def get_public_repo_count() -> int:
    data = http_json(
        f"https://api.github.com/users/{USERNAME}",
        headers={"User-Agent": "whoismrsentry-profile-stats"},
    )
    return int(data.get("public_repos", 0))


def get_user_created_date(login: str) -> dt.date:
    q_created = "query($login: String!) { user(login: $login) { createdAt } }"
    created_at = graphql(q_created, {"login": login})["user"]["createdAt"]
    return dt.datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()


def get_total_commit_contributions_all_time(login: str) -> int:
    # Sum totalCommitContributions year-by-year from account creation to today.
    created_date = get_user_created_date(login)

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

        data = graphql(q_year, {"login": login, "from": from_dt, "to": to_dt})
        total += int(data["user"]["contributionsCollection"]["totalCommitContributions"])

    return total


def get_total_contributions_all_time(login: str) -> int:
    """All contribution types total (the number you see in the contribution graph)."""
    created_date = get_user_created_date(login)

    today = dt.date.today()
    total = 0

    q_year = """
        query($login: String!, $from: DateTime!, $to: DateTime!) {
            user(login: $login) {
                contributionsCollection(from: $from, to: $to) {
                    contributionCalendar {
                        totalContributions
                    }
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

        data = graphql(q_year, {"login": login, "from": from_dt, "to": to_dt})
        total += int(
            data["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
        )

    return total


def safe_get_total_commits() -> str:
    """Return total commit contributions (all time) as string, or 'N/A' if unavailable."""
    if not GITHUB_TOKEN:
        return "N/A"
    try:
        return str(get_total_commit_contributions_all_time(USERNAME))
    except Exception as e:
        print(f"WARN: failed to fetch commit contributions: {e}")
        return "N/A"


def safe_get_total_contributions() -> str:
    """Return total contributions (all types) as string, or 'N/A' if unavailable."""
    if not GITHUB_TOKEN:
        return "N/A"
    try:
        return str(get_total_contributions_all_time(USERNAME))
    except Exception as e:
        print(f"WARN: failed to fetch contributions: {e}")
        return "N/A"


def replace_css_prompt_color(svg: str) -> str:
    # Replace .f color (prompt user) to neon green (generator may vary the previous value).
    svg, n = re.subn(r"\.f\{fill:[^;]+", ".f{fill:#39FF14", svg, count=1)
    return svg


def replace_symbol(svg: str, symbol_id: str, new_inner: str) -> str:
    pattern = re.compile(rf"(<symbol id=\"{re.escape(symbol_id)}\">)(.*?)(</symbol>)")
    m = pattern.search(svg)
    if not m:
        raise RuntimeError(f"symbol id={symbol_id} not found")
    return svg[: m.start(2)] + new_inner + svg[m.end(2) :]


def main():
    svg = SVG_PATH.read_text(encoding="utf-8")

    svg = replace_css_prompt_color(svg)

    # Preserve generator-computed values for these so we don't add more API calls.
    os_name = extract_symbol_value(svg, "8", default="GitHub")
    followers = extract_symbol_value(svg, "12")
    pull_requests = extract_symbol_value(svg, "13")
    issues = extract_symbol_value(svg, "14")

    public_repos = get_public_repo_count()

    # Update "Repos" (symbol 9) value (keep label as Repos)
    # Original: <text ... class="j">Repos:</text><text ... class="g">25</text>
    symbol_9 = re.search(r'<symbol id="9">(.*?)</symbol>', svg)
    if not symbol_9:
        raise RuntimeError("symbol 9 not found")
    inner_9 = symbol_9.group(1)
    inner_9 = re.sub(r'(<text[^>]*class="j">Repos:</text>\s*<text[^>]*class="g">)(\d+)(</text>)',
                     rf"\g<1>{TOTAL_REPOS_STATIC}\g<3>", inner_9)
    svg = replace_symbol(svg, "9", inner_9)

    # Repurpose symbol 10 (was Gists) to Public Repos
    inner_10 = make_stat_line(
        [("4.008", "███"), ("21.041999999999998", "███")],
        "Public Repos:",
        str(public_repos),
    )
    svg = replace_symbol(svg, "10", inner_10)

    # Repurpose symbol 11 (was Stars) to Contributions (GitHub all time)
    contributions_total = safe_get_total_contributions()

    inner_11 = make_stat_line(
        [("4.008", "████"), ("20.04", "████")],
        "Contributions:",
        contributions_total,
    )
    svg = replace_symbol(svg, "11", inner_11)

    # Repurpose symbol 15 (previously an empty spacer) to Commits (GitHub all time)
    commits_total = safe_get_total_commits()
    inner_15 = make_stat_line(
        [("6.012", "██"), ("17.034", "█████")],
        "Commits:",
        commits_total,
    )
    svg = replace_symbol(svg, "15", inner_15)

    # Re-layout OS / Followers / Pull Requests / Issues as well (stair/merdiven effect).
    svg = replace_symbol(
        svg,
        "8",
        make_stat_line(
            [("4.008", "████"), ("20.04", "████")],
            "OS:",
            os_name,
        ),
    )
    svg = replace_symbol(
        svg,
        "12",
        make_stat_line(
            [("4.008", "█████"), ("19.037999999999997", "█████")],
            "Followers:",
            followers,
        ),
    )
    svg = replace_symbol(
        svg,
        "13",
        make_stat_line(
            [("5.01", "██"), ("8.016", "████"), ("16.032", "███████")],
            "Pull Requests:",
            pull_requests,
        ),
    )
    svg = replace_symbol(
        svg,
        "14",
        make_stat_line(
            [("6.012", "██"), ("17.034", "█████")],
            "Issues:",
            issues,
        ),
    )

    SVG_PATH.write_text(svg, encoding="utf-8")
    print("Updated", SVG_PATH)
    print("Repos(total) =", TOTAL_REPOS_STATIC)
    print("Public repos  =", public_repos)
    print("Contributions =", contributions_total)
    print("Commits       =", commits_total)


if __name__ == "__main__":
    main()
