#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from crypto_radar.github_watch import GitHubClient, GitHubWatchStore, poll_repositories


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Poll public GitHub repositories for read-only changes")
    parser.add_argument("--repos", default=os.getenv("GITHUB_WATCH_REPOS", ""), help="Comma-separated repository list (owner/name)")
    parser.add_argument("--history", default=os.getenv("HISTORY", str(PROJECT_ROOT / "data" / "crypto_radar.sqlite3")), help="SQLite history path")
    args = parser.parse_args(argv)
    repos = [item.strip() for item in args.repos.split(",") if item.strip()]
    history = Path(args.history)
    if not repos:
        return 0
    store = GitHubWatchStore(history)
    report = poll_repositories(repos, store, GitHubClient())
    if report["events"] or report["errors"]:
        report["kind"] = "github_watch_alert"
        report["latest_events"] = store.list_events(limit=min(20, max(1, int(report["events"]))))
        print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
