from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .candle_history import CandleHistory
from .indicator_signals import generate_indicator_signal
from .providers.hyperliquid import Candle, HyperliquidProvider, SUPPORTED_CANDLE_INTERVALS
from .serialization import signal_to_dict


class IndicatorCollector:
    def __init__(self, provider: HyperliquidProvider, history: CandleHistory):
        self.provider = provider
        self.history = history

    def collect(
        self,
        assets: set[str],
        timeframes: tuple[str, ...] = ("1m", "10m", "1h", "6h", "1d", "1w"),
        *,
        now_ms: int | None = None,
        observed_at: str | None = None,
        fetch_limit: int = 80,
    ) -> dict[str, Any]:
        if not assets:
            raise ValueError("at least one asset is required")
        unknown = sorted(set(timeframes) - set(SUPPORTED_CANDLE_INTERVALS))
        if unknown:
            raise ValueError(f"unsupported timeframes: {', '.join(unknown)}")
        current_ms = now_ms if now_ms is not None else int(datetime.now(timezone.utc).timestamp() * 1000)
        timestamp = observed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        result: dict[str, Any] = {"observed_at": timestamp, "candles": [], "observations": [], "signals": []}
        for asset in sorted(assets):
            for timeframe in timeframes:
                interval_ms = SUPPORTED_CANDLE_INTERVALS[timeframe]
                fetched = self.provider.fetch_candles(asset, timeframe, current_ms - interval_ms * fetch_limit, current_ms)
                closed = [candle for candle in fetched if candle.open_time + interval_ms <= current_ms]
                candle_stats = self.history.upsert_many(closed, now_ms=current_ms)
                result["candles"].append({"asset": asset, "timeframe": timeframe, **candle_stats, "closed": len(closed)})
                stored = self.history.list_candles(asset, timeframe, limit=fetch_limit)
                if len(stored) < 15:
                    continue
                signal = generate_indicator_signal(
                    asset,
                    timeframe,
                    [candle.high for candle in stored],
                    [candle.low for candle in stored],
                    [candle.close for candle in stored],
                    [candle.volume for candle in stored],
                    observed_at=timestamp,
                )
                signal.measurements.update({"candle_open_time": stored[-1].open_time, "closed_candle_count": len(stored)})
                observation = {**signal.measurements, "asset": asset, "observed_at": timestamp, "market_direction": signal.market_direction}
                status = self.history.save_observation(observation)
                result["observations"].append({"asset": asset, "timeframe": timeframe, "status": status, "candle_open_time": stored[-1].open_time})
                result["signals"].append(signal_to_dict(signal))
        return result
