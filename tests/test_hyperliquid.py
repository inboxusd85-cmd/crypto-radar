import json
from pathlib import Path

import pytest

from crypto_radar.providers.hyperliquid import HyperliquidProvider, ProviderError


FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "hyperliquid_meta.json").read_text())


def test_parse_selected_assets_from_meta_and_contexts():
    snapshots = HyperliquidProvider.parse_meta_and_contexts(FIXTURE, {"BTC", "ETH", "SOL", "HYPE", "ZEC"})
    assert [snapshot.asset for snapshot in snapshots] == ["BTC", "ETH", "SOL", "HYPE", "ZEC"]
    btc = snapshots[0]
    assert btc.mark_price == 65520.0
    assert btc.funding_rate == pytest.approx(0.0000080041)
    assert btc.open_interest == pytest.approx(39946.13006)
    assert btc.day_notional_volume == pytest.approx(2242782413.1914086)


def test_unknown_asset_is_not_fabricated():
    snapshots = HyperliquidProvider.parse_meta_and_contexts(FIXTURE, {"DOGE"})
    assert snapshots == []


def test_fetch_reports_provider_failure_without_fabricating_data():
    provider = HyperliquidProvider(endpoint="https://invalid.example", retries=1)
    with pytest.raises(ProviderError, match="Hyperliquid request failed"):
        provider.fetch()


def test_parse_candles_normalizes_hyperliquid_payload():
    candles = HyperliquidProvider.parse_candles([{"t": 1000, "o": "100", "h": "105", "l": "99", "c": "103", "v": "12.5"}], "btc", "1m")
    assert candles[0].asset == "btc"
    assert candles[0].timeframe == "1m"
    assert candles[0].close == 103.0


def test_parse_candles_rejects_unknown_timeframe():
    with pytest.raises(ValueError, match="unsupported candle timeframe"):
        HyperliquidProvider.parse_candles([], "BTC", "5m")
