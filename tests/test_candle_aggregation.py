from crypto_radar.providers.hyperliquid import Candle, HyperliquidProvider


def test_aggregate_candles_builds_ohlcv_from_source_interval() -> None:
    source = [
        Candle("BTC", "1m", 60_000, 100.0, 103.0, 99.0, 102.0, 10.0),
        Candle("BTC", "1m", 120_000, 102.0, 104.0, 101.0, 103.0, 20.0),
        Candle("BTC", "1m", 660_000, 103.0, 105.0, 102.0, 104.0, 30.0),
    ]

    aggregated = HyperliquidProvider.aggregate_candles(source, "10m")

    assert aggregated == [
        Candle("BTC", "10m", 0, 100.0, 104.0, 99.0, 103.0, 30.0),
        Candle("BTC", "10m", 600_000, 103.0, 105.0, 102.0, 104.0, 30.0),
    ]


def test_fetch_candles_rejects_only_unknown_timeframes() -> None:
    assert set(HyperliquidProvider.supported_source_timeframes()) == {"1m", "1h", "1d"}


def test_weekly_candles_aggregate_daily_source() -> None:
    daily = [
        Candle("BTC", "1d", 0, 100.0, 103.0, 99.0, 102.0, 10.0),
        Candle("BTC", "1d", 86_400_000, 102.0, 105.0, 101.0, 104.0, 20.0),
    ]

    assert HyperliquidProvider.aggregate_candles(daily, "1w") == [
        Candle("BTC", "1w", 0, 100.0, 105.0, 99.0, 104.0, 30.0),
    ]
