#!/usr/bin/env python3
"""Run the Spotify README refresher locally and push updates on a schedule."""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
PYTHON = sys.executable


def _run(cmd: List[str]) -> str:
    """Execute a command inside the repo and raise on failure."""
    completed = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command {' '.join(cmd)} failed (exit {completed.returncode}):\n"
            f"STDOUT: {completed.stdout}\nSTDERR: {completed.stderr}"
        )
    return completed.stdout.strip()


def update_snippet() -> None:
    _run([PYTHON, "scripts/update_spotify.py"])


def has_readme_delta() -> bool:
    output = _run(["git", "status", "--porcelain", str(README.relative_to(ROOT))])
    return bool(output.strip())


def sync_branch(remote: str, branch: str) -> None:
    _run(["git", "fetch", remote, branch])
    _run(["git", "rebase", f"{remote}/{branch}"])


def commit_and_push(remote: str, branch: str) -> None:
    _run(["git", "add", str(README.relative_to(ROOT))])
    _run(["git", "commit", "-m", "chore: refresh Spotify now playing block"])
    _run(["git", "push", remote, f"HEAD:{branch}"])


def cycle(remote: str, branch: str, dry_run: bool) -> None:
    sync_branch(remote, branch)
    update_snippet()
    if not has_readme_delta():
        print("README.md unchanged — nothing to commit.")
        return
    if dry_run:
        print("README.md changed but dry-run enabled; skipping git push.")
        return
    commit_and_push(remote, branch)
    print(f"Pushed updated Spotify block to {remote}/{branch}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=int, default=1800, help="Seconds between updates (default: 1800)")
    parser.add_argument("--remote", default="origin", help="Remote name to push to (default: origin)")
    parser.add_argument("--branch", default="main", help="Branch to track (default: main)")
    parser.add_argument("--once", action="store_true", help="Run a single refresh and exit")
    parser.add_argument("--dry-run", action="store_true", help="Skip committing/pushing even when README changes")
    args = parser.parse_args()

    keep_running = True

    def _stop(signum, frame):  # type: ignore[unused-argument]
        nonlocal keep_running
        keep_running = False
        print("Received signal, exiting after current cycle…")

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    while keep_running:
        try:
            cycle(args.remote, args.branch, args.dry_run)
        except Exception as exc:  # pragma: no cover - operator feedback
            print(f"Spotify sync failed: {exc}")
        if args.once:
            break
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    main()
