#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def fetch_repo_views(owner: str, repo: str, token: str) -> int:
    url = f"https://api.github.com/repos/{owner}/{repo}/traffic/views"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "WhoIsMrSentry-sentrybot-views/1.0",
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            "GitHub API request failed. Make sure your token has access to the target repo "
            "and includes traffic permission (public_repo for public, repo for private)."
            f" HTTP {exc.code}: {body}"
        ) from exc
    count = data.get("count")
    if count is None:
        raise ValueError("GitHub API response missing 'count'")
    return int(count)


def write_shields_endpoint_json(path: Path, count: int) -> None:
    payload = {
        "schemaVersion": 1,
        "label": "SentryBOT Views (14d)",
        "message": str(count),
        "color": "88001b",
        "labelColor": "000000",
        "style": "for-the-badge",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    token = (
        os.environ.get("SENTRYBOT_TOKEN")
        or os.environ.get("GH_PAT")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
    )
    if not token:
        print(
            "Missing token. Set SENTRYBOT_TOKEN (recommended) or GH_PAT/GITHUB_TOKEN/GH_TOKEN.",
            file=sys.stderr,
        )
        return 1

    owner = os.environ.get("SENTRYBOT_OWNER", "WhoIsMrSentry")
    repo = os.environ.get("SENTRYBOT_REPO", "SentryBOT")
    count = fetch_repo_views(owner, repo, token)
    out_path = Path("assets") / "sentrybot_views.json"
    write_shields_endpoint_json(out_path, count)
    print(f"Wrote {out_path} with views_14d={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
