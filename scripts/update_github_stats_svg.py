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


def safe_get_total_commits() -> str:
    """Return total commit contributions as string, or 'N/A' if unavailable."""
    if not GITHUB_TOKEN:
        return "N/A"
    try:
        return str(get_total_commit_contributions_all_time(USERNAME))
    except Exception:
        return "N/A"


def replace_css_prompt_color(svg: str) -> str:
    # Replace .f color (prompt user) to neon green.
    return svg.replace(".f{fill:rgb(238,0,238)", ".f{fill:#39FF14")


def replace_symbol(svg: str, symbol_id: str, new_inner: str) -> str:
    pattern = re.compile(rf"(<symbol id=\"{re.escape(symbol_id)}\">)(.*?)(</symbol>)")
    m = pattern.search(svg)
    if not m:
        raise RuntimeError(f"symbol id={symbol_id} not found")
    return svg[: m.start(2)] + new_inner + svg[m.end(2) :]


def main():
    svg = SVG_PATH.read_text(encoding="utf-8")

    svg = replace_css_prompt_color(svg)

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
    inner_10 = (
        '<text x="4.008" y="1.67" class="i">███</text>'
        '<text x="21.041999999999998" y="1.67" class="i">███</text>'
        '<text x="30.059999999999995" y="1.67" class="j">Public Repos:</text>'
        f'<text x="44.087999999999994" y="1.67" class="g">{public_repos}</text>'
    )
    svg = replace_symbol(svg, "10", inner_10)

    # Repurpose symbol 11 (was Stars) to Commits (GitHub)
    commits_total = safe_get_total_commits()

    inner_11 = (
        '<text x="4.008" y="1.67" class="i">████</text>'
        '<text x="20.04" y="1.67" class="i">████</text>'
        '<text x="30.059999999999995" y="1.67" class="j">Commits:</text>'
        f'<text x="39.077999999999996" y="1.67" class="g">{commits_total}</text>'
    )
    svg = replace_symbol(svg, "11", inner_11)

    SVG_PATH.write_text(svg, encoding="utf-8")
    print("Updated", SVG_PATH)
    print("Repos(total) =", TOTAL_REPOS_STATIC)
    print("Public repos  =", public_repos)
    print("Commits       =", commits_total)


if __name__ == "__main__":
    main()
