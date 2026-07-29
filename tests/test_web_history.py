from pathlib import Path

from fastapi.testclient import TestClient

from crypto_radar.providers.hyperliquid import MarketSnapshot
from crypto_radar.web.app import create_app


class StubProvider:
    def fetch(self, assets: set[str]) -> list[MarketSnapshot]:
        return [MarketSnapshot("BTC", 100.0, 99.9, 0.0001, 20.0, 5000.0)]

    def fetch_candles(self, asset: str, timeframe: str, start_ms: int, end_ms: int):
        from crypto_radar.providers.hyperliquid import Candle

        interval = {"1m": 60_000, "10m": 600_000, "1h": 3_600_000, "6h": 21_600_000, "1d": 86_400_000}[timeframe]
        return [Candle(asset, timeframe, end_ms - (39 - index) * interval, 100 + index, 102 + index, 99 + index, 101 + index, 10.0) for index in range(40)]


def test_overview_does_not_persist_metric_history(tmp_path: Path) -> None:
    app = create_app(history_path=tmp_path / "history.sqlite3", provider=StubProvider())
    client = TestClient(app)

    assert client.get("/api/v1/overview?assets=BTC").status_code == 200
    response = client.get("/api/v1/assets/BTC/history?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["asset"] == "BTC"
    assert set(payload["metrics"]) == {"funding_rate", "mark_mid_spread", "turnover_ratio", "mark_price"}
    assert payload["metrics"]["mark_price"] == []


def test_asset_history_rejects_unknown_metric(tmp_path: Path) -> None:
    app = create_app(history_path=tmp_path / "history.sqlite3", provider=StubProvider())
    response = TestClient(app).get("/api/v1/assets/BTC/history?metric=leverage")

    assert response.status_code == 422


def test_asset_indicators_returns_timestamped_demark_signal(tmp_path: Path) -> None:
    app = create_app(history_path=tmp_path / "history.sqlite3", provider=StubProvider())
    response = TestClient(app).get("/api/v1/assets/BTC/indicators?timeframes=1m")

    assert response.status_code == 200
    payload = response.json()
    assert payload["asset"] == "BTC"
    assert payload["signals"][0]["observed_at"] == payload["generated_at"]
    measurements = payload["signals"][0]["measurements"]
    assert measurements["timeframe"] == "1m"
    assert {"demark", "demark_direction", "volume_ratio", "volume_regime"} <= measurements.keys()
    assert {"rei_direction", "demark_zone", "demark_exhaustion"} <= measurements.keys()
    assert "demark_context" in payload["aggregate"]
    assert payload["aggregate"]["market_direction"] == "шорт"


def test_asset_candle_and_indicator_history_expose_persisted_collector_data(tmp_path: Path) -> None:
    app = create_app(history_path=tmp_path / "history.sqlite3", provider=StubProvider())
    client = TestClient(app)

    assert client.get("/api/v1/assets/BTC/indicators?timeframes=1m").status_code == 200
    candles = client.get("/api/v1/assets/BTC/candles?timeframe=1m&limit=20")
    observations = client.get("/api/v1/assets/BTC/indicator-history?timeframe=1m&limit=20")

    assert candles.status_code == 200
    assert candles.json()["candles"][-1]["timeframe"] == "1m"
    assert {"open_time", "open", "high", "low", "close", "volume"} <= candles.json()["candles"][-1].keys()
    assert observations.status_code == 200
    assert observations.json()["observations"][-1]["timeframe"] == "1m"
    assert {"demark", "market_direction"} <= observations.json()["observations"][-1].keys()
