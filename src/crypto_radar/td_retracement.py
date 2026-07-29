from __future__ import annotations

from collections.abc import Sequence


def _points(values: Sequence[float], left: int, right: int, high: bool) -> list[int]:
    result: list[int] = []
    for i in range(left, len(values) - right):
        before = values[i-left:i]
        after = values[i+1:i+right+1]
        if high and values[i] > max(before) and values[i] >= max(after):
            result.append(i)
        elif not high and values[i] < min(before) and values[i] <= min(after):
            result.append(i)
    return result


def _zone(close: float, level382: float | None, level618: float | None) -> str:
    if level382 is None or level618 is None:
        return "unavailable"
    upper, lower = max(level382, level618), min(level382, level618)
    if close > upper:
        return "above_382"
    if close < lower:
        return "below_618"
    return "between_382_618"


def calculate_td_retracement(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], *, left_bars: int = 2, right_bars: int = 2
) -> dict[str, object]:
    if not len(highs) == len(lows) == len(closes):
        raise ValueError("highs, lows and closes must have equal lengths")
    if left_bars < 1 or right_bars < 1:
        raise ValueError("left_bars and right_bars must be positive")
    high_points = _points(highs, left_bars, right_bars, True)
    low_points = _points(lows, left_bars, right_bars, False)
    if not high_points or not low_points:
        return {"direction": "insufficient", "swing_low": None, "swing_high": None, "retracement_382": None, "retracement_618": None, "retracement_zone": "unavailable", "swing_low_index": None, "swing_high_index": None, "lookahead_safe": True}
    low_index = min(low_points, key=lambda i: lows[i])
    high_index = max(high_points, key=lambda i: highs[i])
    swing_low, swing_high = float(lows[low_index]), float(highs[high_index])
    distance = swing_high - swing_low
    level382 = round(swing_high - distance * 0.382, 3)
    level618 = round(swing_high - distance * 0.618, 3)
    return {"direction": "up", "swing_low": swing_low, "swing_high": swing_high, "swing_low_index": low_index, "swing_high_index": high_index, "retracement_382": level382, "retracement_618": level618, "retracement_zone": _zone(float(closes[-1]), level382, level618), "lookahead_safe": high_index <= len(closes) - right_bars - 1 and low_index <= len(closes) - right_bars - 1}
