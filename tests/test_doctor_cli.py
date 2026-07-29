import json
import os
import subprocess
import sys
from pathlib import Path


def test_doctor_reports_local_schema_as_ready(tmp_path):
    db = tmp_path / "history.sqlite3"
    result = subprocess.run(
        [sys.executable, "-m", "crypto_radar.cli", "doctor", "--history", str(db), "--format", "json"],
        cwd=Path(__file__).parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["checks"]["sqlite"]["ok"] is True
    assert payload["checks"]["schema"]["ok"] is True
    assert payload["checks"]["xurl"]["status"] in {"authenticated", "unauthenticated", "missing"}
    assert isinstance(payload["checks"]["xurl"]["authenticated"], bool)


def test_doctor_reports_missing_xurl_without_failing_local_checks(tmp_path):
    db = tmp_path / "history.sqlite3"
    result = subprocess.run(
        [sys.executable, "-m", "crypto_radar.cli", "doctor", "--history", str(db), "--format", "json", "--skip-xurl"],
        cwd=Path(__file__).parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["checks"]["xurl"]["status"] == "skipped"
    assert payload["checks"]["xurl"]["authenticated"] is False
