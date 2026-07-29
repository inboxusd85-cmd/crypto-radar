from pathlib import Path

from fastapi.testclient import TestClient

from crypto_radar.history import MetricHistory
from crypto_radar.providers.hyperliquid import MarketSnapshot
from crypto_radar.web.app import create_app


class FakeProvider:
    def fetch(self, assets: set[str]) -> list[MarketSnapshot]:
        assert assets == {"BTC", "ETH"}
        return [
            MarketSnapshot("BTC", 65_000.0, 64_990.0, 0.00035, 40_000.0, 2_000_000_000.0),
            MarketSnapshot("ETH", 3_000.0, 2_999.0, 0.00001, 500_000.0, 1_000_000_000.0),
        ]


def test_overview_returns_market_data_without_writing_history(tmp_path: Path) -> None:
    history_path = tmp_path / "history.sqlite3"
    client = TestClient(create_app(history_path=history_path, provider=FakeProvider()))

    response = client.get("/api/v1/overview?assets=BTC,ETH")

    assert response.status_code == 200
    payload = response.json()
    assert [item["asset"] for item in payload["assets"]] == ["BTC", "ETH"]
    assert len(payload["signals"]) == 2
    assert payload["signals"][0]["auto_trade"] is False
    assert payload["signals"][0]["requires_manual_review"] is True
    assert payload["generated_at"].endswith("Z")
    assert payload["meta"] == {"requested_assets": ["BTC", "ETH"], "unavailable_assets": []}
    assert MetricHistory(history_path).values("BTC", "funding_rate") == []
