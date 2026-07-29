from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from .providers.hyperliquid import Candle


@dataclass(frozen=True)
class SupportResistanceLevel:
    period: str
    strength: str
    resistance: float
    support: float
    start: str
    end: str


def _previous_month(day: date) -> tuple[date, date]:
    first = day.replace(day=1)
    previous_end = first - timedelta(days=1)
    return previous_end.replace(day=1), previous_end


def _period_bounds(period: str, as_of: date) -> tuple[date, date]:
    if period == "day":
        previous = as_of - timedelta(days=1)
        return previous, previous
    if period == "week":
        current_monday = as_of - timedelta(days=as_of.weekday())
        return current_monday - timedelta(days=7), current_monday - timedelta(days=1)
    if period == "month":
        return _previous_month(as_of)
    raise ValueError(f"unsupported period: {period}")


def calculate_levels(candles: list[Candle], as_of: datetime | None = None) -> list[SupportResistanceLevel]:
    """Calculate previous completed calendar period high/low levels from daily OHLC candles."""
    reference = (as_of or datetime.now(timezone.utc)).date()
    result: list[SupportResistanceLevel] = []
    definitions = (("month", "strong"), ("week", "medium"), ("day", "weak"))
    for period, strength in definitions:
        start, end = _period_bounds(period, reference)
        selected = []
        for candle in candles:
            candle_date = datetime.fromtimestamp(candle.open_time / 1000, tz=timezone.utc).date()
            if start <= candle_date <= end:
                selected.append(candle)
        if not selected:
            continue
        result.append(SupportResistanceLevel(
            period=period,
            strength=strength,
            resistance=max(item.high for item in selected),
            support=min(item.low for item in selected),
            start=start.isoformat(),
            end=end.isoformat(),
        ))
    return result
