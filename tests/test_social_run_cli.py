import json
import os
import subprocess
import sys
from pathlib import Path

from crypto_radar.social import SocialPost
from crypto_radar.social_store import SocialPostStore


def run_social(args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "crypto_radar.cli", "social-run", *args],
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )


def test_social_run_offline_empty_history_is_successful(tmp_path):
    result = run_social(
        ["--history", str(tmp_path / "history.sqlite3"), "--offline", "--format", "json"],
        Path(__file__).parents[1],
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "offline"
    assert payload["posts_fetched"] == 0
    assert payload["signals_emitted"] == 0
    assert payload["event_stats"] == {"attempted": 0, "recorded": 0, "duplicates_skipped": 0}


def test_social_run_offline_records_quality_gated_signal(tmp_path):
    db = tmp_path / "history.sqlite3"
    store = SocialPostStore(db)
    store.upsert(SocialPost(
        platform="x", post_id="1", author_id="author-1", author_handle="analyst",
        text="HYPE risk exploit reported", created_at="2026-07-20T12:00:00Z",
        url="https://x.com/analyst/status/1", query="HYPE", engagement=10, source_quality=0.5,
    ))
    args = ["--history", str(db), "--query", "HYPE", "--offline", "--record-events", "--format", "json", "--observed-at", "2026-07-20T12:00:00Z"]
    first = run_social(args, Path(__file__).parents[1])
    second = run_social(args, Path(__file__).parents[1])
    assert first.returncode == 0
    assert second.returncode == 0
    first_payload = json.loads(first.stdout)
    second_payload = json.loads(second.stdout)
    assert first_payload["posts_fetched"] == 1
    assert first_payload["signals_emitted"] == 1
    assert first_payload["event_stats"] == {"attempted": 1, "recorded": 1, "duplicates_skipped": 0}
    assert second_payload["event_stats"] == {"attempted": 1, "recorded": 0, "duplicates_skipped": 1}
    assert first_payload["signals"][0]["requires_manual_review"] is True
    assert first_payload["signals"][0]["auto_trade"] is False
    assert first_payload["signals"][0]["signal_class"] == "social"
    assert first_payload["signals"][0]["measurements"]["confidence_model"] == "social-quality-v1"
