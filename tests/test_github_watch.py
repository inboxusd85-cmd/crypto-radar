from pathlib import Path
import json
import os
import subprocess
import sys
from http.client import RemoteDisconnected

import pytest

from crypto_radar import github_watch
from crypto_radar.github_watch import GitHubSnapshot, diff_snapshot, GitHubWatchStore, summarize_events


def snapshot(**overrides) -> GitHubSnapshot:
    payload = {
        "repo": "owner/project",
        "full_name": "owner/project",
        "html_url": "https://github.com/owner/project",
        "description": "Project",
        "stars": 10,
        "forks": 2,
        "open_issues": 1,
        "default_branch": "main",
        "last_push_at": "2026-07-23T10:00:00Z",
        "latest_release": None,
        "latest_release_at": None,
        "latest_issue_or_pr_at": None,
    }
    payload.update(overrides)
    return GitHubSnapshot(**payload)


def test_diff_detects_stars_fork_release_and_push() -> None:
    old = snapshot()
    new = snapshot(stars=13, forks=3, last_push_at="2026-07-23T11:00:00Z", latest_release="v1.2.0", latest_release_at="2026-07-23T10:30:00Z")

    changes = diff_snapshot(old, new)

    assert [item.kind for item in changes] == ["stars", "fork", "release", "push"]
    assert changes[0].value == {"from": 10, "to": 13, "delta": 3}


def test_store_persists_snapshot_and_deduplicates_events(tmp_path: Path) -> None:
    store = GitHubWatchStore(tmp_path / "watch.sqlite3")
    event = diff_snapshot(snapshot(), snapshot(stars=11))[0]

    assert store.record_snapshot(snapshot()) is True
    assert store.record_snapshot(snapshot()) is False
    assert store.record_event(event) is True
    assert store.record_event(event) is False
    assert store.list_events(limit=10)[0]["kind"] == "stars"
    assert store.list_events(kinds=["release"], limit=10) == []
    assert store.list_events(since="2026-07-23T00:00:00Z", limit=10)[0]["repo"] == "owner/project"


def test_summary_assigns_explainable_severity_and_counts() -> None:
    events = [
        {"repo": "owner/project", "kind": "release", "value": {"tag": "v1"}},
        {"repo": "owner/project", "kind": "stars", "value": {"delta": 2}},
        {"repo": "other/repo", "kind": "stars", "value": {"delta": 25}},
    ]

    summary = summarize_events(events)

    assert summary["total"] == 3
    assert summary["by_kind"] == {"release": 1, "stars": 2}
    assert summary["by_severity"] == {"low": 1, "medium": 1, "high": 1}
    assert summary["latest"]["kind"] == "stars"


def test_fetch_json_normalizes_remote_disconnect_to_runtime_error(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise RemoteDisconnected("remote closed")

    monkeypatch.setattr(github_watch, "urlopen", fail)
    with pytest.raises(RuntimeError, match="GitHub request failed"):
        github_watch.GitHubClient()._fetch_json("https://api.github.com/repos/owner/project")


def test_watch_script_exposes_explicit_history_and_repository_arguments() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/watch_github.py", "--help"],
        cwd=Path(__file__).parents[1],
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )

    assert result.returncode == 0
    assert "--history" in result.stdout
    assert "--repos" in result.stdout
