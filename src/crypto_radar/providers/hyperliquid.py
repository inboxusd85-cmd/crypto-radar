from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen


INFO_URL = "https://api.hyperliquid.xyz/info"
SOURCE_URL = "https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint"
CANDLE_SOURCE_URL = "https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/candles"
SUPPORTED_CANDLE_INTERVALS = {"1m": 60_000, "10m": 600_000, "1h": 3_600_000, "6h": 21_600_000, "1d": 86_400_000, "1w": 604_800_000}
SOURCE_CANDLE_INTERVALS = {"1m": "1m", "10m": "1m", "1h": "1h", "6h": "1h", "1d": "1d", "1w": "1d"}


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarketSnapshot:
    asset: str
    mark_price: float
    mid_price: float | None
    funding_rate: float
    open_interest: float
    day_notional_volume: float


@dataclass(frozen=True)
class Candle:
    asset: str
    timeframe: str
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class HyperliquidProvider:
    def __init__(self, endpoint: str = INFO_URL, timeout: float = 20.0, retries: int = 2):
        self.endpoint = endpoint
        self.timeout = timeout
        self.retries = retries

    @staticmethod
    def parse_meta_and_contexts(payload: list, assets: set[str]) -> list[MarketSnapshot]:
        if not isinstance(payload, list) or len(payload) != 2:
            raise ValueError("Hyperliquid metaAndAssetCtxs response must contain two arrays")
        meta, contexts = payload
        universe = meta.get("universe", [])
        snapshots: list[MarketSnapshot] = []
        for listing, context in zip(universe, contexts):
            asset = listing.get("name")
            if asset not in assets:
                continue
            try:
                snapshots.append(MarketSnapshot(
                    asset=asset,
                    mark_price=float(context["markPx"]),
                    mid_price=float(context["midPx"]) if context.get("midPx") else None,
                    funding_rate=float(context["funding"]),
                    open_interest=float(context["openInterest"]),
                    day_notional_volume=float(context["dayNtlVlm"]),
                ))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Malformed Hyperliquid context for {asset}") from exc
        return snapshots

    def fetch(self, assets: set[str] = {"BTC", "ETH", "SOL"}) -> list[MarketSnapshot]:
        body = json.dumps({"type": "metaAndAssetCtxs"}).encode("utf-8")
        request = Request(self.endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read())
                return self.parse_meta_and_contexts(payload, assets)
            except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.25 * (attempt + 1))
        raise ProviderError(f"Hyperliquid request failed after {self.retries + 1} attempts: {last_error}") from last_error

    @staticmethod
    def supported_source_timeframes() -> tuple[str, ...]:
        return tuple(dict.fromkeys(SOURCE_CANDLE_INTERVALS.values()))

    @staticmethod
    def aggregate_candles(candles: list[Candle], timeframe: str) -> list[Candle]:
        if timeframe not in SUPPORTED_CANDLE_INTERVALS:
            raise ValueError(f"unsupported candle timeframe: {timeframe}")
        interval = SUPPORTED_CANDLE_INTERVALS[timeframe]
        buckets: dict[int, list[Candle]] = {}
        for candle in candles:
            bucket = candle.open_time // interval * interval
            buckets.setdefault(bucket, []).append(candle)
        result: list[Candle] = []
        for open_time, items in sorted(buckets.items()):
            result.append(Candle(
                items[0].asset, timeframe, open_time, items[0].open,
                max(item.high for item in items), min(item.low for item in items),
                items[-1].close, sum(item.volume for item in items),
            ))
        return result

    @staticmethod
    def parse_candles(payload: list, asset: str, timeframe: str) -> list[Candle]:
        if timeframe not in SUPPORTED_CANDLE_INTERVALS:
            raise ValueError(f"unsupported candle timeframe: {timeframe}")
        if not isinstance(payload, list):
            raise ValueError("Hyperliquid candle response must be an array")
        candles: list[Candle] = []
        for item in payload:
            try:
                candles.append(Candle(asset, timeframe, int(item["t"]), float(item["o"]), float(item["h"]), float(item["l"]), float(item["c"]), float(item["v"])))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Malformed Hyperliquid candle for {asset} {timeframe}") from exc
        return candles

    def fetch_candles(self, asset: str, timeframe: str, start_ms: int, end_ms: int) -> list[Candle]:
        if timeframe not in SUPPORTED_CANDLE_INTERVALS:
            raise ValueError(f"unsupported candle timeframe: {timeframe}")
        source_timeframe = SOURCE_CANDLE_INTERVALS[timeframe]
        source_interval_ms = SUPPORTED_CANDLE_INTERVALS[source_timeframe]
        target_interval_ms = SUPPORTED_CANDLE_INTERVALS[timeframe]
        source_start_ms = int(start_ms)
        body = json.dumps({"type": "candleSnapshot", "req": {"coin": asset.strip().upper(), "interval": source_timeframe, "startTime": source_start_ms, "endTime": int(end_ms)}}).encode("utf-8")
        request = Request(self.endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read())
                source = self.parse_candles(payload, asset.strip().upper(), source_timeframe)
                return source if source_timeframe == timeframe else self.aggregate_candles(source, timeframe)
            except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.25 * (attempt + 1))
        raise ProviderError(f"Hyperliquid candle request failed after {self.retries + 1} attempts: {last_error}") from last_error
