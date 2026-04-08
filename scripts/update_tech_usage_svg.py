#!/usr/bin/env python3
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from html import escape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "assets" / "tech_usage.svg"

USERNAME = os.environ.get("GITHUB_USERNAME", "WhoIsMrSentry")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

MAX_LIB_ROWS = int(os.environ.get("TECH_USAGE_MAX_LIB_ROWS", "12"))
REQUEST_TIMEOUT = 30

JS_LIKE_LANGUAGES = {
    "JavaScript",
    "TypeScript",
    "HTML",
    "CSS",
    "Vue",
    "Svelte",
}

PYTHON_LANGUAGES = {"Python"}

# Manifest dependencies mapped to display labels.
JS_PACKAGE_MAP = {
    "react": "React",
    "react-dom": "React",
    "next": "Next.js",
    "svelte": "Svelte",
    "@sveltejs/kit": "SvelteKit",
    "vue": "Vue",
    "nuxt": "Nuxt",
    "@angular/core": "Angular",
    "express": "Express",
    "@nestjs/core": "NestJS",
    "vite": "Vite",
    "tailwindcss": "Tailwind CSS",
    "bootstrap": "Bootstrap",
    "redux": "Redux",
    "@reduxjs/toolkit": "Redux Toolkit",
    "socket.io": "Socket.IO",
    "three": "Three.js",
    "axios": "Axios",
}

PY_PACKAGE_MAP = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "djangorestframework": "Django REST",
    "opencv-python": "OpenCV",
    "opencv-contrib-python": "OpenCV",
    "tensorflow": "TensorFlow",
    "torch": "PyTorch",
    "pytorch": "PyTorch",
    "langchain": "LangChain",
    "numpy": "NumPy",
    "pandas": "Pandas",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
}

TOPIC_TECH_MAP = {
    "react": "React",
    "nextjs": "Next.js",
    "next-js": "Next.js",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "opencv": "OpenCV",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "langchain": "LangChain",
    "svelte": "Svelte",
    "vue": "Vue",
    "tailwindcss": "Tailwind CSS",
    "vite": "Vite",
    "express": "Express",
}

RAW_CACHE: dict[tuple[str, str, str, str], str | None] = {}


def http_json(url: str) -> dict | list:
    headers = {
        "User-Agent": "whoismrsentry-tech-usage-svg",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_owner_repos_api(login: str) -> list[dict]:
    repos: list[dict] = []
    page = 1

    while True:
        url = (
            f"https://api.github.com/users/{login}/repos"
            f"?type=owner&sort=updated&per_page=100&page={page}"
        )
        data = http_json(url)
        if not isinstance(data, list) or not data:
            break

        for repo_data in data:
            if repo_data.get("fork"):
                continue
            if repo_data.get("archived"):
                continue
            repos.append(
                {
                    "name": repo_data.get("name", ""),
                    "owner": {"login": (repo_data.get("owner") or {}).get("login", login)},
                    "language": repo_data.get("language") or "",
                    "default_branch": repo_data.get("default_branch") or "",
                    "topics": repo_data.get("topics") or [],
                }
            )

        if len(data) < 100:
            break
        page += 1

    return repos


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "whoismrsentry-tech-usage-svg",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def list_owner_repos_html(login: str) -> list[dict]:
    seen: set[str] = set()
    repos: list[dict] = []
    pattern = re.compile(
        rf'href="/{re.escape(login)}/([^"/]+)"[^>]*itemprop="name codeRepository"'
        rf'|itemprop="name codeRepository"[^>]*href="/{re.escape(login)}/([^"/]+)"'
    )

    for page in range(1, 11):
        html = fetch_text(f"https://github.com/{login}?tab=repositories&page={page}")
        names: list[str] = []
        for match in pattern.finditer(html):
            name = match.group(1) or match.group(2)
            if not name:
                continue
            name = name.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            names.append(name)

        if not names:
            break

        for name in names:
            repos.append(
                {
                    "name": name,
                    "owner": {"login": login},
                    "language": "",
                    "default_branch": "",
                    "topics": [],
                }
            )

    return repos


def list_owner_repos(login: str) -> tuple[list[dict], str]:
    try:
        repos = list_owner_repos_api(login)
        return repos, "api"
    except urllib.error.HTTPError as exc:
        if exc.code != 403:
            raise
        print("WARN: GitHub API rate limit hit, falling back to HTML/raw source")
        repos = list_owner_repos_html(login)
        return repos, "html"


def fetch_raw_repo_file(owner: str, repo: str, branch: str, rel_path: str) -> str | None:
    key = (owner, repo, branch, rel_path)
    if key in RAW_CACHE:
        return RAW_CACHE[key]

    encoded_path = urllib.parse.quote(rel_path, safe="/")
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{encoded_path}"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "whoismrsentry-tech-usage-svg",
                "Accept": "text/plain",
            },
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            RAW_CACHE[key] = text
            return text
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 404):
            RAW_CACHE[key] = None
            return None
        raise


def branch_candidates(repo: dict) -> list[str]:
    candidates: list[str] = []
    default_branch = (repo.get("default_branch") or "").strip()
    if default_branch:
        candidates.append(default_branch)
    if "main" not in candidates:
        candidates.append("main")
    if "master" not in candidates:
        candidates.append("master")
    return candidates


def fetch_repo_file(owner: str, repo: str, rel_path: str, branches: list[str]) -> str | None:
    for branch in branches:
        content = fetch_raw_repo_file(owner, repo, branch, rel_path)
        if content is not None:
            return content
    return None


def normalize_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def detect_js_packages(package_json_text: str) -> set[str]:
    found: set[str] = set()
    try:
        data = json.loads(package_json_text)
    except json.JSONDecodeError:
        return found

    sections = [
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
    ]
    for section in sections:
        section_data = data.get(section)
        if not isinstance(section_data, dict):
            continue
        for dep_name in section_data:
            dep_key = normalize_name(dep_name)
            label = JS_PACKAGE_MAP.get(dep_key)
            if label:
                found.add(label)
    return found


def detect_python_requirements(requirements_text: str) -> set[str]:
    found: set[str] = set()
    for raw_line in requirements_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue

        m = re.match(r"[A-Za-z0-9_.-]+", line)
        if not m:
            continue

        dep_key = normalize_name(m.group(0))
        label = PY_PACKAGE_MAP.get(dep_key)
        if label:
            found.add(label)

    return found


def detect_python_pyproject(pyproject_text: str) -> set[str]:
    found: set[str] = set()
    lowered = pyproject_text.lower()

    for dep_name, label in PY_PACKAGE_MAP.items():
        pattern = r"(?<![a-z0-9_.-])" + re.escape(dep_name) + r"(?![a-z0-9_.-])"
        if re.search(pattern, lowered):
            found.add(label)

    return found


def detect_tech_from_topics(repo: dict) -> set[str]:
    found: set[str] = set()
    for topic in repo.get("topics") or []:
        topic_key = normalize_name(str(topic))
        label = TOPIC_TECH_MAP.get(topic_key)
        if label:
            found.add(label)
    return found


def detect_repo_technologies(repo: dict) -> set[str]:
    techs: set[str] = set()
    techs.update(detect_tech_from_topics(repo))

    owner = repo["owner"]["login"]
    name = repo["name"]
    language = (repo.get("language") or "").strip()
    branches = branch_candidates(repo)

    scan_js = not language or language in JS_LIKE_LANGUAGES
    scan_py = not language or language in PYTHON_LANGUAGES

    if scan_js:
        package_json = fetch_repo_file(owner, name, "package.json", branches)
        if package_json:
            techs.update(detect_js_packages(package_json))

    if scan_py:
        requirements = fetch_repo_file(owner, name, "requirements.txt", branches)
        if requirements:
            techs.update(detect_python_requirements(requirements))

        pyproject = fetch_repo_file(owner, name, "pyproject.toml", branches)
        if pyproject:
            techs.update(detect_python_pyproject(pyproject))

        pipfile = fetch_repo_file(owner, name, "Pipfile", branches)
        if pipfile:
            techs.update(detect_python_pyproject(pipfile))

    return techs


def as_rows(counter: Counter, total_repos: int, limit: int) -> list[tuple[str, int, float]]:
    rows: list[tuple[str, int, float]] = []
    if total_repos <= 0:
        return rows

    for label, count in counter.items():
        pct = (count / total_repos) * 100
        rows.append((label, count, pct))

    rows.sort(key=lambda item: (-item[2], -item[1], item[0].lower()))
    return rows[:limit]


def render_rows(rows: list[tuple[str, int, float]], y_start: int, bar_color: str) -> tuple[list[str], int]:
    lines: list[str] = []
    y = y_start

    if not rows:
        lines.append(f'<text x="40" y="{y}" class="muted">No dependency data found</text>')
        return lines, y + 32

    for label, count, pct in rows:
        bar_x = 395
        bar_y = y - 11
        bar_w = 425
        bar_h = 10
        fill_w = max(1, int(round((pct / 100.0) * bar_w)))

        left_text = f"{label} ({count} repos)"
        right_text = f"{pct:.1f}%"

        lines.append(f'<text x="40" y="{y}" class="label">{escape(left_text)}</text>')
        lines.append(
            f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" '
            'rx="5" fill="#2a0d18"/>'
        )
        lines.append(
            f'<rect x="{bar_x}" y="{bar_y}" width="{fill_w}" height="{bar_h}" '
            f'rx="5" fill="{bar_color}"/>'
        )
        lines.append(f'<text x="870" y="{y}" class="pct">{escape(right_text)}</text>')
        y += 28

    return lines, y


def build_svg(login: str, total_repos: int, rows: list[tuple[str, int, float]]) -> str:
    width = 920
    est_rows = max(1, len(rows))
    height = 180 + est_rows * 28

    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Libraries and Frameworks by Repo Usage</title>',
        '<desc id="desc">Percentage of repositories that include each library or framework.</desc>',
        '<style>',
        '.bg{fill:#200009}',
        '.title{fill:#00ff41;font:700 26px "JetBrains Mono",Consolas,monospace}',
        '.sub{fill:#e6ffe6;font:400 14px "JetBrains Mono",Consolas,monospace}',
        '.section{fill:#ff1744;font:700 16px "JetBrains Mono",Consolas,monospace}',
        '.label{fill:#e6ffe6;font:400 13px "JetBrains Mono",Consolas,monospace}',
        '.pct{fill:#e6ffe6;font:700 13px "JetBrains Mono",Consolas,monospace;text-anchor:end}',
        '.muted{fill:#9fb39f;font:400 13px "JetBrains Mono",Consolas,monospace}',
        '</style>',
        f'<rect class="bg" x="0" y="0" width="{width}" height="{height}"/>',
        f'<rect x="18" y="18" width="884" height="{height - 36}" rx="12" fill="none" stroke="#88001b" stroke-width="2"/>',
        '<text x="40" y="56" class="title">Libraries &amp; Frameworks Usage</text>',
        (
            f'<text x="40" y="80" class="sub">@{escape(login)} • {total_repos} repos • '
            'dependency/topic based (not bytes)</text>'
        ),
        '<text x="40" y="114" class="section">Top Libraries &amp; Frameworks</text>',
    ]

    row_lines, _ = render_rows(rows, y_start=138, bar_color="#ff1744")
    parts.extend(row_lines)

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> int:
    repos, source = list_owner_repos(USERNAME)
    total_repos = len(repos)

    if total_repos == 0:
        raise RuntimeError("No repositories found for the user")

    tech_counter: Counter = Counter()
    for repo in repos:
        for tech in detect_repo_technologies(repo):
            tech_counter[tech] += 1

    rows = as_rows(tech_counter, total_repos, MAX_LIB_ROWS)
    svg = build_svg(USERNAME, total_repos, rows)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(svg, encoding="utf-8")

    print(f"Wrote {OUT_PATH}")
    print(f"total_repos={total_repos} source={source}")
    print("libraries=", ", ".join(f"{name}:{pct:.1f}%" for name, _, pct in rows) or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
