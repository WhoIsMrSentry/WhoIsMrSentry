#!/usr/bin/env python3
import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ASSETS_DIR = Path("assets")

GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "WhoIsMrSentry")
PROFILE_REPO_OWNER = os.environ.get("PROFILE_REPO_OWNER", GITHUB_USERNAME)
PROFILE_REPO_NAME = os.environ.get("PROFILE_REPO_NAME", "WhoIsMrSentry")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
REQUEST_TIMEOUT = 30


def github_json(url: str) -> dict | list:
    headers = {
        "User-Agent": "whoismrsentry-achievement-metrics/1.0",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sanitize_message(value: object) -> str:
    text = str(value).replace("\n", " ").strip()
    return text if text else "N/A"


def read_previous_message(path: Path, fallback: str = "N/A") -> str:
    if not path.exists():
        return fallback

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

    message = data.get("message")
    return sanitize_message(message) if message is not None else fallback


def write_shields_endpoint_json(path: Path, label: str, message: str) -> None:
    payload = {
        "schemaVersion": 1,
        "label": label,
        "message": sanitize_message(message),
        "color": "88001b",
        "labelColor": "000000",
        "style": "for-the-badge",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def get_public_repos_count() -> int:
    data = github_json(f"https://api.github.com/users/{GITHUB_USERNAME}")
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected response for user profile")
    return int(data.get("public_repos", 0))


def get_total_stars_count() -> int:
    total = 0
    page = 1

    while True:
        url = (
            f"https://api.github.com/users/{GITHUB_USERNAME}/repos"
            f"?type=owner&per_page=100&page={page}"
        )
        data = github_json(url)
        if not isinstance(data, list):
            raise RuntimeError("Unexpected response for repository list")
        if not data:
            break

        for repo in data:
            total += int((repo or {}).get("stargazers_count", 0))

        if len(data) < 100:
            break
        page += 1

    return total


def get_last_commit_date() -> str:
    url = (
        f"https://api.github.com/repos/{PROFILE_REPO_OWNER}/{PROFILE_REPO_NAME}/commits"
        "?per_page=1"
    )
    data = github_json(url)
    if not isinstance(data, list) or not data:
        return "N/A"

    commit_obj = data[0].get("commit") or {}
    committer = commit_obj.get("committer") or {}
    date_str = committer.get("date")
    if not date_str:
        return "N/A"

    parsed = dt.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return parsed.date().isoformat()


def get_monthly_commit_count() -> int:
    since = (dt.datetime.now(dt.UTC) - dt.timedelta(days=30)).isoformat().replace("+00:00", "Z")
    encoded_since = urllib.parse.quote(since, safe=":TZ-")

    total = 0
    page = 1
    while True:
        url = (
            f"https://api.github.com/repos/{PROFILE_REPO_OWNER}/{PROFILE_REPO_NAME}/commits"
            f"?per_page=100&page={page}&since={encoded_since}"
        )
        data = github_json(url)
        if not isinstance(data, list):
            raise RuntimeError("Unexpected response for commit activity")
        if not data:
            break

        total += len(data)
        if len(data) < 100:
            break
        page += 1

    return total


def get_open_work_items_count() -> int:
    data = github_json(f"https://api.github.com/repos/{PROFILE_REPO_OWNER}/{PROFILE_REPO_NAME}")
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected response for repository details")
    return int(data.get("open_issues_count", 0))


def search_total_count(query: str) -> int:
    encoded_q = urllib.parse.quote(query, safe=":/+")
    url = f"https://api.github.com/search/issues?q={encoded_q}&per_page=1"
    data = github_json(url)
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected response for search endpoint")
    return int(data.get("total_count", 0))


def get_closed_work_items_count() -> int:
    base = f"repo:{PROFILE_REPO_OWNER}/{PROFILE_REPO_NAME}"
    closed_issues = search_total_count(f"{base} is:issue is:closed")
    closed_prs = search_total_count(f"{base} is:pr is:closed")
    return closed_issues + closed_prs


def safe_metric(metric_name: str, getter, previous_value: str) -> str:
    try:
        return sanitize_message(getter())
    except Exception as exc:
        print(f"WARN: failed to fetch {metric_name}: {exc}; using previous value={previous_value}")
        return previous_value


def main() -> int:
    metric_defs = [
        ("proof_public_repos.json", "Public Repos", get_public_repos_count),
        ("proof_total_stars.json", "Total Stars", get_total_stars_count),
        ("proof_last_commit.json", "Last Commit", get_last_commit_date),
        ("proof_monthly_commits.json", "Monthly Commits", get_monthly_commit_count),
        ("proof_open_work_items.json", "Open Issues + PRs", get_open_work_items_count),
        ("proof_closed_work_items.json", "Closed Issues + PRs", get_closed_work_items_count),
    ]

    for filename, label, getter in metric_defs:
        out_path = ASSETS_DIR / filename
        previous = read_previous_message(out_path, fallback="N/A")
        value = safe_metric(label, getter, previous)
        write_shields_endpoint_json(out_path, label=label, message=value)
        print(f"Wrote {out_path} => {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
