from datetime import datetime, timezone

from crypto_radar.providers.hyperliquid import Candle
from crypto_radar.support_resistance import calculate_levels


def candle(ts: str, high: float, low: float, open_: float = 100.0, close: float = 101.0) -> Candle:
    opened = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
    return Candle("BTC", "1d", opened, open_, high, low, close, 10.0)


def test_calculate_levels_uses_previous_completed_day_week_and_month() -> None:
    candles = [
        candle("2026-01-30T00:00:00Z", 130, 90),
        candle("2026-01-31T00:00:00Z", 131, 91),
        candle("2026-02-01T00:00:00Z", 140, 100),
        candle("2026-02-02T00:00:00Z", 141, 101),
        candle("2026-02-08T00:00:00Z", 150, 110),
        candle("2026-02-09T00:00:00Z", 151, 111),
        candle("2026-02-10T00:00:00Z", 160, 120),
    ]

    levels = calculate_levels(candles, as_of=datetime(2026, 2, 10, tzinfo=timezone.utc))

    assert [(item.period, item.strength, item.resistance, item.support) for item in levels] == [
        ("month", "strong", 131, 90),
        ("week", "medium", 150, 101),
        ("day", "weak", 151, 111),
    ]


def test_calculate_levels_ignores_current_incomplete_period() -> None:
    candles = [candle("2026-02-10T00:00:00Z", 200, 50)]

    assert calculate_levels(candles, as_of=datetime(2026, 2, 10, 12, tzinfo=timezone.utc)) == []
