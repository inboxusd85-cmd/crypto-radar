from pathlib import Path

from crypto_radar.candle_history import CandleHistory
from crypto_radar.history import MetricHistory
from crypto_radar.outcome_worker import replay_once, run_once
from crypto_radar.events import AlertEventJournal
from crypto_radar.outcomes import OutcomeStore
from crypto_radar.providers.hyperliquid import Candle


def test_worker_recovers_legacy_entry_price_from_candle_open_when_metrics_are_retained_after_event(tmp_path: Path) -> None:
    db = tmp_path / "history.sqlite3"
    CandleHistory(db).upsert_many([
        Candle("BTC", "1h", 1_700_000_000_000, 100.0, 102.0, 99.0, 101.0, 1.0),
        Candle("BTC", "1h", 1_700_003_600_000, 101.0, 103.0, 100.0, 102.0, 1.0),
        Candle("BTC", "1h", 1_700_007_200_000, 102.0, 104.0, 101.0, 103.0, 1.0),
    ])
    event = {"event_id": "legacy-candle-1", "asset": "BTC", "observed_at": "2023-11-14T22:30:00Z", "measurements": {}}

    report = run_once(db, events=[event])

    assert report["ready"] == 1
    assert report["pending"] == 3


def test_worker_recovers_legacy_entry_price_from_metric_history(tmp_path: Path) -> None:
    db = tmp_path / "history.sqlite3"
    MetricHistory(db).append("BTC", "mark_price", 100.0, observed_at=1_700_000_000)
    CandleHistory(db).upsert_many([
        Candle("BTC", "1h", 1_700_003_600_000, 100.0, 102.0, 99.0, 101.0, 1.0),
    ])
    event = {"event_id": "legacy-1", "asset": "BTC", "observed_at": "2023-11-14T22:13:20Z", "measurements": {}}

    report = run_once(db, events=[event])

    assert report["ready"] == 1
    assert report["pending"] == 3


def test_replay_once_writes_only_to_archive_database(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite3"
    archive = tmp_path / "archive.sqlite3"
    event = {"event_id": "replay-1", "asset": "BTC", "observed_at": "2023-11-14T22:13:20Z", "measurements": {"mark_price": 100.0}}
    import json
    import sqlite3
    AlertEventJournal(source)
    with sqlite3.connect(source) as connection:
        connection.execute("INSERT INTO alert_events(event_id, signal_id, asset, severity, signal_type, observed_at, recorded_at, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("replay-1", "signal-1", "BTC", "medium", "market", event["observed_at"], 0.0, json.dumps(event)))
    CandleHistory(archive).upsert_many([
        Candle("BTC", "1h", 1_700_000_000_000, 100, 101, 99, 102, 1),
        Candle("BTC", "1h", 1_700_003_600_000, 102, 103, 101, 104, 1),
    ])
    before = OutcomeStore(source).get("replay-1")
    report = replay_once(source, archive)
    assert report["read_only"] is True
    assert report["ready"] >= 1
    assert OutcomeStore(source).get("replay-1") == before
    assert OutcomeStore(archive).get("replay-1")


def test_archive_validation_report_is_read_only_and_exposes_gate(tmp_path: Path) -> None:
    from crypto_radar.outcome_worker import build_archive_validation_report
    source = tmp_path / "source.sqlite3"
    archive = tmp_path / "archive.sqlite3"
    import json
    import sqlite3
    AlertEventJournal(source)
    event = {"event_id": "validation-1", "asset": "BTC", "observed_at": "2023-11-14T22:13:20Z", "measurements": {"mark_price": 100.0}}
    with sqlite3.connect(source) as connection:
        connection.execute("INSERT INTO alert_events(event_id, signal_id, asset, severity, signal_type, observed_at, recorded_at, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("validation-1", "signal-1", "BTC", "medium", "market", event["observed_at"], 0.0, json.dumps(event)))
    CandleHistory(archive).upsert_many([
        Candle("BTC", "1h", 1_700_000_000_000, 100, 101, 99, 102, 1),
        Candle("BTC", "1h", 1_700_003_600_000, 102, 103, 101, 104, 1),
    ])
    replay_once(source, archive, limit=10)
    report = build_archive_validation_report(source, archive, limit=10)
    assert report["read_only"] is True
    assert report["event_count"] == 1
    assert report["validation"]["by_horizon"]["1h"]["sample_size"] == 1
    assert report["time_split"]["dataset_gate"]["train_1h"]["status"] == "blocked"
