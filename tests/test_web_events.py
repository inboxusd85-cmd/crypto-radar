from pathlib import Path

from fastapi.testclient import TestClient

from crypto_radar.events import AlertEventJournal
from crypto_radar.models import Signal
from crypto_radar.web.app import create_app


def event(asset: str, severity: str, observed_at: str) -> Signal:
    return Signal(asset, "composite_market_risk", "fact", "basis", ["https://example.com"], severity=severity, observed_at=observed_at)


def test_events_endpoint_filters_and_returns_cursor(tmp_path: Path) -> None:
    history_path = tmp_path / "history.sqlite3"
    journal = AlertEventJournal(history_path)
    journal.record(event("BTC", "high", "2026-07-21T10:00:00Z"), recorded_at=10.0)
    journal.record(event("ETH", "high", "2026-07-21T10:01:00Z"), recorded_at=20.0)
    client = TestClient(create_app(history_path=history_path))

    response = client.get("/api/v1/events?severity=high&limit=1")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["events"][0]["asset"] == "ETH"
    assert response.json()["next_before"] == 20.0
