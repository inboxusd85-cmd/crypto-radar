from __future__ import annotations

from crypto_radar.td_structure import calculate_td_structure


def test_td_structure_returns_confirmed_points_without_latest_lookahead() -> None:
    closes = [10, 11, 12, 13, 12, 11, 10, 11, 12, 13, 14, 13, 12]
    highs = [value + 1 for value in closes]
    lows = [value - 1 for value in closes]

    result = calculate_td_structure(highs, lows, closes, left_bars=2, right_bars=2)

    assert result["td_point_highs"] == [3, 10]
    assert result["td_point_lows"] == [6]
    assert result["latest_confirmed_index"] == 10
    assert result["lookahead_safe"] is True


def test_td_structure_exposes_supply_demand_lines_and_breakout_state() -> None:
    closes = [10, 12, 11, 13, 12, 10, 11, 14, 13, 15, 14, 16, 17]
    highs = [value + 1 for value in closes]
    lows = [value - 1 for value in closes]

    result = calculate_td_structure(highs, lows, closes, left_bars=1, right_bars=1)

    assert result["td_demand_line"] is not None
    assert result["td_supply_line"] is not None
    assert result["demand_breakout"] in {"none", "true", "false"}
    assert result["supply_breakout"] in {"none", "true", "false"}