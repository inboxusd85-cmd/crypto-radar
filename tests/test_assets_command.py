import json

import pytest

from crypto_radar.cli import format_assets, missing_assets
from crypto_radar.providers.hyperliquid import MarketSnapshot


def snapshots():
    return [
        MarketSnapshot("HYPE", 61.88, 61.8815, 0.0000125, 22320399.58, 255673541.4),
        MarketSnapshot("ZEC", 552.48, 552.48, 0.0000125, 584534.82, 100115705.78),
    ]


def test_assets_markdown_contains_hype_and_zec():
    text = format_assets(snapshots(), "markdown")
    assert "HYPE" in text
    assert "ZEC" in text
    assert "61.88" in text


def test_assets_json_is_machine_readable():
    payload = json.loads(format_assets(snapshots(), "json"))
    assert [item["asset"] for item in payload] == ["HYPE", "ZEC"]
    assert payload[0]["funding_rate"] == 0.0000125


def test_missing_assets_reports_only_unavailable_tickers():
    assert missing_assets({"HYPE", "ZEC", "DOGE"}, snapshots()) == {"DOGE"}
