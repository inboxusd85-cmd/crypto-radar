from pathlib import Path

from fastapi.testclient import TestClient

from crypto_radar.candle_history import CandleHistory
from crypto_radar.events import AlertEventJournal
from crypto_radar.history import MetricHistory
from crypto_radar.outcome_worker import replay_once, run_once
from crypto_radar.outcomes import OutcomeStore
from crypto_radar.providers.hyperliquid import Candle
from crypto_radar.web.app import create_app


def test_archive_validation_endpoint_is_read_only(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.sqlite3"
    archive = tmp_path / "archive.sqlite3"
    monkeypatch.setenv("CRYPTO_RADAR_BACKFILL_HISTORY", str(archive))
    response = TestClient(create_app(history_path=source)).get("/api/v1/reviews/validation/archive?limit=10")
    assert response.status_code == 200
    payload = response.json()
    assert payload["read_only"] is True
    assert payload["event_count"] == 0
    assert payload["validation"]["by_horizon"]["1h"]["sample_size"] == 0
    assert payload["time_split"]["dataset_gate"]["train_1h"]["status"] == "blocked"
