from __future__ import annotations

from collections.abc import Sequence
import math


def classify_demark_direction(demark: float) -> str:
    if demark < 0.30:
        return "лонг"
    if demark > 0.70:
        return "шорт"
    return "нейтральное"


def classify_rei_direction(rei: float) -> str:
    if rei < -60:
        return "лонг"
    if rei > 60:
        return "шорт"
    return "нейтральное"


def _demark_zone(demark: float) -> str:
    if demark < 0.30:
        return "oversold"
    if demark > 0.70:
        return "overbought"
    return "neutral"


def _demark_exhaustion(previous: float, current: float) -> str:
    if previous < 0.30 <= current:
        return "buy_setup"
    if previous > 0.70 >= current:
        return "sell_setup"
    return "none"


def _validate_ohlc(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int) -> None:
    if period < 2:
        raise ValueError("period must be at least 2")
    if not len(highs) == len(lows) == len(closes):
        raise ValueError("highs, lows, and closes must have the same length")
    if len(closes) < period + 1:
        raise ValueError(f"at least {period + 1} OHLC points are required")
    if any(high < low for high, low in zip(highs, lows)):
        raise ValueError("high must be greater than or equal to low")
    if any(not math.isfinite(float(value)) for series in (highs, lows, closes) for value in series):
        raise ValueError("OHLC values must be finite")


def _ema(values: Sequence[float], period: int) -> float:
    result = values[0]
    alpha = 2.0 / (period + 1)
    for value in values[1:]:
        result = alpha * value + (1.0 - alpha) * result
    return result


def _demark(highs: Sequence[float], lows: Sequence[float], period: int, smoothing: str = "SMA") -> float:
    demax = [0.0] + [max(high - previous, 0.0) for previous, high in zip(highs[:-1], highs[1:])]
    demin = [0.0] + [max(previous - low, 0.0) for previous, low in zip(lows[:-1], lows[1:])]
    demax_window = demax[-period:]
    demin_window = demin[-period:]
    if smoothing == "SMA":
        max_value = sum(demax_window) / period
        min_value = sum(demin_window) / period
    elif smoothing == "SMMA":
        max_value = demax_window[0]
        min_value = demin_window[0]
        for max_item, min_item in zip(demax_window[1:], demin_window[1:]):
            max_value = (max_value * (period - 1) + max_item) / period
            min_value = (min_value * (period - 1) + min_item) / period
    else:
        max_value = _ema(demax_window, period)
        min_value = _ema(demin_window, period)
    denominator = max_value + min_value
    return max_value / denominator if denominator > 0 else 0.5


def _rei(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 8) -> float:
    if len(closes) < period + 8:
        return 0.0
    positive = []
    denominator = []
    for index in range(7, len(closes)):
        high_delta = highs[index] - highs[index - 2]
        low_delta = lows[index] - lows[index - 2]
        valid_up = highs[index - 2] > closes[index - 7] or highs[index] > highs[index - 5]
        valid_down = lows[index - 2] < closes[index - 7] or lows[index] < lows[index - 5]
        contribution = high_delta + low_delta if valid_up and valid_down else 0.0
        positive.append(contribution)
        denominator.append(abs(high_delta) + abs(low_delta))
    numerator = sum(positive[-period:])
    total = sum(denominator[-period:])
    return max(-100.0, min(100.0, 100.0 * numerator / total)) if total else 0.0


def _rei_regime(rei: float) -> str:
    if rei < -60:
        return "oversold"
    if rei > 60:
        return "overbought"
    return "neutral"


def calculate_indicator_snapshot(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    period: int = 13,
) -> dict[str, float | str]:
    _validate_ohlc(highs, lows, closes, period)
    demark = _demark(highs, lows, period)
    previous_demark = _demark(highs[:-1], lows[:-1], period)
    rei = _rei(highs, lows, closes)
    return {
        "period": float(period),
        "demark": demark,
        "demark_direction": classify_demark_direction(demark),
        "demark_zone": _demark_zone(demark),
        "demark_exhaustion": _demark_exhaustion(previous_demark, demark),
        "rei": rei,
        "rei_period": 8.0,
        "rei_regime": _rei_regime(rei),
        "rei_direction": classify_rei_direction(rei),
    }
