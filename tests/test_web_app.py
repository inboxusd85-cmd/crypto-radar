from pathlib import Path
import sqlite3
import time

from fastapi.testclient import TestClient

from crypto_radar.web.app import create_app
from crypto_radar.github_watch import GitHubChange, GitHubWatchStore


def test_health_reports_read_only_market_status(tmp_path: Path) -> None:
    app = create_app(history_path=tmp_path / "history.sqlite3")

    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "api_version": "0.1.0",
        "database": {"ok": True},
        "provider": {"name": "hyperliquid", "last_success_at": None, "last_indicator_success_at": None},
        "social": {
            "enabled": False,
            "status": "available_on_demand",
            "mode": "separate_pipeline",
            "entrypoint": "social-run",
            "included_in_market_composite": False,
            "requires_manual_review": True,
        },
        "outcomes": {"worker": None},
    }


def test_github_watch_reports_configured_repositories_and_events(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GITHUB_WATCH_REPOS", "owner/project,other/repo")
    path = tmp_path / "history.sqlite3"
    store = GitHubWatchStore(path)
    store.record_event(GitHubChange("owner/project", "release", "release:v1", "2026-07-23T10:00:00Z", "Новый release v1", "https://github.com/owner/project/releases", {"tag": "v1"}))

    response = TestClient(create_app(history_path=path)).get("/api/v1/github/watch")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["repos"] == ["owner/project", "other/repo"]
    assert payload["events"][0]["kind"] == "release"


def test_github_watch_poll_is_safe_when_not_configured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GITHUB_WATCH_REPOS", raising=False)

    response = TestClient(create_app(history_path=tmp_path / "history.sqlite3")).post("/api/v1/github/watch/poll")

    assert response.status_code == 200
    assert response.json()["reason"] == "GITHUB_WATCH_REPOS is not configured"


def _write_worker_state(path: Path, payload: dict) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE outcome_worker_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        import json
        connection.execute("INSERT INTO outcome_worker_state(key, value) VALUES ('last_run', ?)", (json.dumps(payload),))


def test_health_distinguishes_stale_worker_from_worker_error(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite3"
    _write_worker_state(path, {"attempted": 3, "ready": 3, "pending": 0, "errors": 0, "completed_at": time.time() - 901})

    worker = TestClient(create_app(history_path=path)).get("/api/v1/health").json()["outcomes"]["worker"]

    assert worker["status"] == "stale"
    assert worker["stale"] is True
    assert worker["age_seconds"] >= 900


def test_health_keeps_fresh_worker_error_distinct_from_stale(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite3"
    _write_worker_state(path, {"attempted": 3, "ready": 2, "pending": 0, "errors": 1, "completed_at": time.time()})

    worker = TestClient(create_app(history_path=path)).get("/api/v1/health").json()["outcomes"]["worker"]

    assert worker["status"] == "error"
    assert worker["stale"] is False
    assert worker["age_seconds"] < 900
