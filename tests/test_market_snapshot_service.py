from pathlib import Path

from crypto_radar.history import MetricHistory
from crypto_radar.market_snapshot_service import MarketSnapshotService
from crypto_radar.providers.hyperliquid import MarketSnapshot


class FakeProvider:
    def fetch(self, assets: set[str]) -> list[MarketSnapshot]:
        assert assets == {"BTC"}
        return [
            MarketSnapshot(
                asset="BTC",
                mark_price=65_000.0,
                mid_price=64_990.0,
                funding_rate=0.00035,
                open_interest=40_000.0,
                day_notional_volume=2_000_000_000.0,
            )
        ]


def test_snapshot_service_returns_composite_without_persisting_metrics(tmp_path: Path) -> None:
    history_path = tmp_path / "history.sqlite3"
    result = MarketSnapshotService(FakeProvider(), history_path).collect({"BTC"}, observed_at="2026-07-21T12:00:00Z")

    assert [snapshot.asset for snapshot in result.snapshots] == ["BTC"]
    assert result.unavailable_assets == set()
    assert len(result.composites) == 1
    assert result.composites[0].asset == "BTC"
    assert result.composites[0].observed_at == "2026-07-21T12:00:00Z"
    assert MetricHistory(history_path).values("BTC", "funding_rate") == []
