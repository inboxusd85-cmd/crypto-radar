from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .providers.hyperliquid import Candle


class CandleHistory:
    def __init__(self, path: str | Path, max_candles: int = 500, retention_days: int = 30):
        if max_candles < 1 or retention_days < 1:
            raise ValueError("max_candles and retention_days must be positive")
        self.path = Path(path)
        self.max_candles = max_candles
        self.retention_days = retention_days
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS candle_history ("
                "asset TEXT NOT NULL, timeframe TEXT NOT NULL, open_time INTEGER NOT NULL, "
                "open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL, volume REAL NOT NULL, "
                "PRIMARY KEY(asset, timeframe, open_time))"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_candle_history_series "
                "ON candle_history(asset, timeframe, open_time DESC)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS indicator_history ("
                "asset TEXT NOT NULL, timeframe TEXT NOT NULL, candle_open_time INTEGER NOT NULL, "
                "observed_at TEXT NOT NULL, payload TEXT NOT NULL, recorded_at REAL NOT NULL, "
                "PRIMARY KEY(asset, timeframe, candle_open_time))"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_indicator_history_series "
                "ON indicator_history(asset, timeframe, candle_open_time DESC)"
            )

    def upsert_many(self, candles: list[Candle], now_ms: int | None = None) -> dict[str, int]:
        stats = {"inserted": 0, "updated": 0}
        with sqlite3.connect(self.path) as connection:
            for candle in candles:
                exists = connection.execute(
                    "SELECT 1 FROM candle_history WHERE asset = ? AND timeframe = ? AND open_time = ?",
                    (candle.asset, candle.timeframe, candle.open_time),
                ).fetchone()
                connection.execute(
                    "INSERT INTO candle_history(asset, timeframe, open_time, open, high, low, close, volume) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(asset, timeframe, open_time) DO UPDATE SET "
                    "open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, volume=excluded.volume",
                    (candle.asset, candle.timeframe, candle.open_time, candle.open, candle.high, candle.low, candle.close, candle.volume),
                )
                stats["updated" if exists else "inserted"] += 1
            if now_ms is not None:
                cutoff = int(now_ms) - self.retention_days * 86_400_000
                connection.execute("DELETE FROM candle_history WHERE timeframe NOT IN ('1d', '1w') AND open_time < ?", (cutoff,))
            for asset, timeframe in {(item.asset, item.timeframe) for item in candles}:
                if timeframe not in {"1d", "1w"} and now_ms is None:
                    connection.execute(
                        "DELETE FROM candle_history WHERE asset = ? AND timeframe = ? AND open_time NOT IN "
                        "(SELECT open_time FROM candle_history WHERE asset = ? AND timeframe = ? ORDER BY open_time DESC LIMIT ?)",
                        (asset, timeframe, asset, timeframe, self.max_candles),
                    )
        return stats

    def archive_upsert_many(self, candles: list[Candle]) -> dict[str, int]:
        """Upsert historical candles without applying live retention limits."""
        stats = {"inserted": 0, "updated": 0}
        with sqlite3.connect(self.path) as connection:
            for candle in candles:
                exists = connection.execute(
                    "SELECT 1 FROM candle_history WHERE asset = ? AND timeframe = ? AND open_time = ?",
                    (candle.asset, candle.timeframe, candle.open_time),
                ).fetchone()
                connection.execute(
                    "INSERT INTO candle_history(asset, timeframe, open_time, open, high, low, close, volume) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(asset, timeframe, open_time) DO UPDATE SET "
                    "open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, volume=excluded.volume",
                    (candle.asset, candle.timeframe, candle.open_time, candle.open, candle.high, candle.low, candle.close, candle.volume),
                )
                stats["updated" if exists else "inserted"] += 1
        return stats

    def list_candles(self, asset: str, timeframe: str, limit: int | None = None) -> list[Candle]:
        query = "SELECT asset, timeframe, open_time, open, high, low, close, volume FROM candle_history WHERE asset = ? AND timeframe = ? ORDER BY open_time ASC"
        parameters: list[Any] = [asset.upper(), timeframe]
        if limit is not None:
            if limit < 1:
                raise ValueError("limit must be positive")
            query = "SELECT asset, timeframe, open_time, open, high, low, close, volume FROM candle_history WHERE asset = ? AND timeframe = ? ORDER BY open_time DESC LIMIT ?"
            parameters.append(limit)
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(query, parameters).fetchall()
        rows.reverse() if limit is not None else None
        return [Candle(*row) for row in rows]

    def save_observation(self, observation: dict[str, Any]) -> str:
        key = (observation["asset"], observation["timeframe"], int(observation["candle_open_time"]))
        payload = json.dumps(observation, ensure_ascii=False, separators=(",", ":"))
        with sqlite3.connect(self.path) as connection:
            exists = connection.execute(
                "SELECT 1 FROM indicator_history WHERE asset = ? AND timeframe = ? AND candle_open_time = ?", key
            ).fetchone()
            connection.execute(
                "INSERT INTO indicator_history(asset, timeframe, candle_open_time, observed_at, payload, recorded_at) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(asset, timeframe, candle_open_time) DO UPDATE SET observed_at=excluded.observed_at, payload=excluded.payload, recorded_at=excluded.recorded_at",
                (*key, observation["observed_at"], payload, time.time()),
            )
        return "updated" if exists else "inserted"

    def latest_observation(self, asset: str, timeframe: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT payload FROM indicator_history WHERE asset = ? AND timeframe = ? ORDER BY candle_open_time DESC LIMIT 1",
                (asset.upper(), timeframe),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list_observations(self, asset: str, timeframe: str, limit: int = 100) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                "SELECT payload FROM indicator_history WHERE asset = ? AND timeframe = ? ORDER BY candle_open_time DESC LIMIT ?",
                (asset.upper(), timeframe, limit),
            ).fetchall()
        return [json.loads(row[0]) for row in reversed(rows)]
