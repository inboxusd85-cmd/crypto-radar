from __future__ import annotations

from crypto_radar.td_retracement import calculate_td_retracement


def test_td_retracement_returns_levels_from_confirmed_swing_points() -> None:
    highs = [11, 12, 15, 13, 12, 10, 11, 13, 14, 13, 12]
    lows = [9, 10, 11, 10, 8, 7, 8, 10, 11, 10, 9]
    closes = [10, 11, 14, 12, 11, 8, 10, 12, 13, 11, 10]

    result = calculate_td_retracement(highs, lows, closes, left_bars=1, right_bars=1)

    assert result["direction"] == "up"
    assert result["swing_low"] == 7
    assert result["swing_high"] == 15
    assert result["retracement_382"] == 11.944
    assert result["retracement_618"] == 10.056
    assert result["lookahead_safe"] is True


def test_td_retracement_reports_price_zone_without_fabricating_missing_levels() -> None:
    highs = [11, 10, 9, 8]
    lows = [9, 8, 7, 6]
    closes = [10, 9, 8, 7]

    result = calculate_td_retracement(highs, lows, closes, left_bars=1, right_bars=1)

    assert result["direction"] == "insufficient"
    assert result["retracement_382"] is None
    assert result["retracement_zone"] == "unavailable"