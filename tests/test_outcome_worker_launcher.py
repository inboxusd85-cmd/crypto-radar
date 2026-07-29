from pathlib import Path
import json
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_outcome_worker_launcher_runs_from_any_cwd(tmp_path: Path) -> None:
    launcher = ROOT / "scripts" / "run_outcome_worker.sh"
    assert launcher.is_file()
    assert os.access(launcher, os.X_OK)

    result = subprocess.run(
        [str(launcher)],
        cwd=tmp_path,
        env={**os.environ, "HISTORY": str(tmp_path / "worker.sqlite3"), "LIMIT": "3"},
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {"attempted": 0, "ready": 0, "pending": 0, "errors": 0, "status": "ok"}


def test_outcome_worker_launcher_rejects_non_positive_limit(tmp_path: Path) -> None:
    launcher = ROOT / "scripts" / "run_outcome_worker.sh"

    result = subprocess.run(
        [str(launcher)],
        cwd=tmp_path,
        env={**os.environ, "HISTORY": str(tmp_path / "worker.sqlite3"), "LIMIT": "0"},
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "--limit must be positive" in result.stderr


def test_outcome_watchdog_alerts_when_worker_has_not_started(tmp_path: Path) -> None:
    watchdog = ROOT / "scripts" / "watch_outcome_worker.py"
    result = subprocess.run(
        [sys.executable, str(watchdog)],
        cwd=ROOT,
        env={**os.environ, "HISTORY": str(tmp_path / "worker.sqlite3")},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["kind"] == "outcome_worker_alert"
    assert payload["reason"] == "not_started"


def test_outcome_watchdog_is_silent_when_worker_is_fresh(tmp_path: Path) -> None:
    import sqlite3
    import time

    db = tmp_path / "worker.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE outcome_worker_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO outcome_worker_state(key, value) VALUES ('last_run', ?)",
            (json.dumps({"status": "ok", "errors": 0, "completed_at": time.time()}),),
        )

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "watch_outcome_worker.py")],
        cwd=ROOT,
        env={**os.environ, "HISTORY": str(db)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout == ""


def test_outcome_watchdog_alerts_when_worker_is_stale(tmp_path: Path) -> None:
    import sqlite3
    import time

    db = tmp_path / "worker.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE outcome_worker_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO outcome_worker_state(key, value) VALUES ('last_run', ?)",
            (json.dumps({"status": "ok", "errors": 0, "completed_at": time.time() - 901}),),
        )

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "watch_outcome_worker.py")],
        cwd=ROOT,
        env={**os.environ, "HISTORY": str(db)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["kind"] == "outcome_worker_alert"
    assert payload["reason"] == "stale"


def test_outcome_watchdog_alerts_worker_error(tmp_path: Path) -> None:
    import sqlite3
    import time

    db = tmp_path / "worker.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE outcome_worker_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO outcome_worker_state(key, value) VALUES ('last_run', ?)",
            (json.dumps({"status": "error", "errors": 2, "completed_at": time.time()}),),
        )

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "watch_outcome_worker.py")],
        cwd=ROOT,
        env={**os.environ, "HISTORY": str(db)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["reason"] == "error"
    assert payload["errors"] == 2


def test_outcome_watchdog_handles_existing_database_without_worker_table(tmp_path: Path) -> None:
    import sqlite3

    db = tmp_path / "worker.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "watch_outcome_worker.py")],
        cwd=ROOT,
        env={**os.environ, "HISTORY": str(db)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["reason"] == "not_started"


def test_market_cycle_watchdog_alerts_when_no_events_exist(tmp_path: Path) -> None:
    watchdog = ROOT / "scripts" / "watch_market_cycle.py"
    result = subprocess.run(
        [sys.executable, str(watchdog)],
        cwd=ROOT,
        env={**os.environ, "HISTORY": str(tmp_path / "cycle.sqlite3")},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["kind"] == "market_cycle_alert"
    assert payload["reason"] == "not_started"


def test_market_cycle_watchdog_is_silent_for_fresh_event(tmp_path: Path) -> None:
    import sqlite3
    import time

    db = tmp_path / "cycle.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE alert_events (recorded_at REAL NOT NULL)")
        connection.execute("INSERT INTO alert_events(recorded_at) VALUES (?)", (time.time(),))

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "watch_market_cycle.py")],
        cwd=ROOT,
        env={**os.environ, "HISTORY": str(db)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_market_cycle_watchdog_alerts_for_stale_event(tmp_path: Path) -> None:
    import sqlite3
    import time

    db = tmp_path / "cycle.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE alert_events (recorded_at REAL NOT NULL)")
        connection.execute("INSERT INTO alert_events(recorded_at) VALUES (?)", (time.time() - 901,))

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "watch_market_cycle.py")],
        cwd=ROOT,
        env={**os.environ, "HISTORY": str(db)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["kind"] == "market_cycle_alert"
    assert payload["reason"] == "stale"
