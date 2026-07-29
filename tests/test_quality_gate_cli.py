import json
import subprocess
import sys
from pathlib import Path


def test_social_record_events_quality_gate_rejects_missing_evidence(tmp_path):
    db = tmp_path / "history.sqlite3"
    cmd = [sys.executable, "-m", "crypto_radar.cli", "social-analyze", "--history", str(db), "--aggregate", "--as-signals", "--record-events"]
    env = {"PYTHONPATH": "src"}
    result = subprocess.run(cmd, cwd=Path(__file__).parents[1], env={**__import__("os").environ, **env}, capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout) == []
