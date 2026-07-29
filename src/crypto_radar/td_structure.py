from __future__ import annotations

from collections.abc import Sequence


def _validate(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], left_bars: int, right_bars: int) -> None:
    if not len(highs) == len(lows) == len(closes):
        raise ValueError("highs, lows and closes must have equal lengths")
    if left_bars < 1 or right_bars < 1:
        raise ValueError("left_bars and right_bars must be positive")


def _confirmed_points(values: Sequence[float], left_bars: int, right_bars: int, is_high: bool) -> list[int]:
    points: list[int] = []
    last_confirmable = len(values) - right_bars
    for index in range(left_bars, last_confirmable):
        left = values[index - left_bars:index]
        right = values[index + 1:index + right_bars + 1]
        if is_high and values[index] > max(left) and values[index] >= max(right):
            points.append(index)
        if not is_high and values[index] < min(left) and values[index] <= min(right):
            points.append(index)
    return points


def _breakout(close: float | None, line: float | None, direction: str) -> str:
    if close is None or line is None:
        return "none"
    if direction == "above":
        return "true" if close > line else "false"
    return "true" if close < line else "false"


def calculate_td_structure(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    left_bars: int = 2,
    right_bars: int = 2,
) -> dict[str, object]:
    _validate(highs, lows, closes, left_bars, right_bars)
    if not closes:
        return {
            "td_point_highs": [], "td_point_lows": [], "latest_confirmed_index": None,
            "td_demand_line": None, "td_supply_line": None,
            "demand_breakout": "none", "supply_breakout": "none", "lookahead_safe": True,
        }
    point_highs = _confirmed_points(highs, left_bars, right_bars, True)
    point_lows = _confirmed_points(lows, left_bars, right_bars, False)
    latest_confirmed_index = max(point_highs + point_lows, default=None)
    supply_line = highs[point_highs[-1]] if point_highs else None
    demand_line = lows[point_lows[-1]] if point_lows else None
    close = closes[-1]
    return {
        "td_point_highs": point_highs,
        "td_point_lows": point_lows,
        "latest_confirmed_index": latest_confirmed_index,
        "td_demand_line": demand_line,
        "td_supply_line": supply_line,
        "demand_breakout": _breakout(close, demand_line, "below"),
        "supply_breakout": _breakout(close, supply_line, "above"),
        "lookahead_safe": latest_confirmed_index is None or latest_confirmed_index <= len(closes) - right_bars - 1,
    }
