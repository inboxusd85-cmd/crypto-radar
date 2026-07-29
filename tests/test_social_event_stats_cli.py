import json
import os
import subprocess
import sys
from pathlib import Path


def test_social_record_events_keeps_json_stdout_and_reports_stats(tmp_path):
    db = tmp_path / "history.sqlite3"
    result = subprocess.run(
        [sys.executable, "-m", "crypto_radar.cli", "social-analyze", "--history", str(db), "--aggregate", "--as-signals", "--record-events"],
        cwd=Path(__file__).parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == []
    assert 'social_event_record_stats={"attempted": 0, "recorded": 0, "duplicates_skipped": 0}' in result.stderr
