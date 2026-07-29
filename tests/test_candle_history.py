from crypto_radar.candle_history import CandleHistory
from crypto_radar.providers.hyperliquid import Candle


def candle(open_time: int, timeframe: str = "1m") -> Candle:
    return Candle("BTC", timeframe, open_time, 100.0, 102.0, 99.0, 101.0, 10.0)


def test_candle_history_upserts_and_deduplicates_by_asset_timeframe_open_time(tmp_path) -> None:
    store = CandleHistory(tmp_path / "history.sqlite3")

    assert store.upsert_many([candle(0), candle(60_000), candle(60_000)], now_ms=60_000) == {"inserted": 2, "updated": 1}
    assert len(store.list_candles("BTC", "1m")) == 2


def test_intraday_candles_are_retained_for_30_days(tmp_path) -> None:
    store = CandleHistory(tmp_path / "history.sqlite3")
    day = 86_400_000
    store.upsert_many([candle(0), candle(day), candle(29 * day), candle(30 * day)], now_ms=30 * day)

    assert [item.open_time for item in store.list_candles("BTC", "1m")] == [0, day, 29 * day, 30 * day]
    store.upsert_many([candle(31 * day)], now_ms=31 * day)
    assert [item.open_time for item in store.list_candles("BTC", "1m")] == [day, 29 * day, 30 * day, 31 * day]


def test_daily_candles_are_not_deleted_by_retention(tmp_path) -> None:
    store = CandleHistory(tmp_path / "history.sqlite3")
    day = 86_400_000
    store.upsert_many([candle(0, "1d"), candle(365 * day, "1d")], now_ms=365 * day)

    assert [item.open_time for item in store.list_candles("BTC", "1d")] == [0, 365 * day]


def test_indicator_observations_are_idempotent(tmp_path) -> None:
    store = CandleHistory(tmp_path / "history.sqlite3")
    observation = {
        "asset": "BTC", "timeframe": "1m", "candle_open_time": 60_000,
        "observed_at": "2026-07-21T15:00:00Z", "rsi": 60.0,
        "rsi_direction": "лонг", "aroon_up": 80.0, "aroon_down": 20.0,
        "aroon_direction": "лонг", "adx": 30.0, "trend_strength": "сильный",
        "market_direction": "лонг",
    }

    assert store.save_observation(observation) == "inserted"
    assert store.save_observation({**observation, "rsi": 61.0}) == "updated"
    assert store.latest_observation("BTC", "1m")["rsi"] == 61.0
