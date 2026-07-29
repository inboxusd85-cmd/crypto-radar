from crypto_radar.candle_history import CandleHistory
from crypto_radar.indicator_collector import IndicatorCollector
from crypto_radar.providers.hyperliquid import Candle


class StubProvider:
    def fetch_candles(self, asset, timeframe, start_ms, end_ms):
        interval = {"1m": 60_000, "10m": 600_000, "1h": 3_600_000, "6h": 21_600_000, "1d": 86_400_000, "1w": 604_800_000}[timeframe]
        return [Candle(asset, timeframe, index * interval, 100 + index, 102 + index, 99 + index, 101 + index, 10.0) for index in range(40)]


def test_collector_excludes_open_candle_and_persists_observation(tmp_path) -> None:
    history = CandleHistory(tmp_path / "history.sqlite3")
    result = IndicatorCollector(StubProvider(), history).collect(
        {"BTC"}, ("1m",), now_ms=39 * 60_000 + 1, observed_at="2026-07-21T15:00:00Z"
    )

    assert result["candles"][0]["closed"] == 39
    assert result["signals"][0]["measurements"]["timeframe"] == "1m"
    assert result["signals"][0]["measurements"]["volume_ratio"] > 0
    assert result["signals"][0]["measurements"]["candle_open_time"] == 38 * 60_000
    assert result["signals"][0]["measurements"]["closed_candle_count"] == 39
    assert history.latest_observation("BTC", "1m")["candle_open_time"] == 38 * 60_000
