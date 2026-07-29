from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class MetricHistory:
    def __init__(self, path: str | Path, max_samples: int = 100):
        if max_samples < 1:
            raise ValueError("max_samples must be positive")
        self.path = Path(path)
        self.max_samples = max_samples
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS metric_history ("
                "asset TEXT NOT NULL, metric TEXT NOT NULL, value REAL NOT NULL, observed_at REAL NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_metric_history_key "
                "ON metric_history(asset, metric, observed_at)"
            )

    def append(self, asset: str, metric: str, value: float, observed_at: float | None = None) -> None:
        timestamp = time.time() if observed_at is None else float(observed_at)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO metric_history(asset, metric, value, observed_at) VALUES (?, ?, ?, ?)",
                (asset, metric, float(value), timestamp),
            )
            connection.execute(
                "DELETE FROM metric_history WHERE asset = ? AND metric = ? AND rowid NOT IN "
                "(SELECT rowid FROM metric_history WHERE asset = ? AND metric = ? "
                "ORDER BY observed_at DESC, rowid DESC LIMIT ?)",
                (asset, metric, asset, metric, self.max_samples),
            )

    def values(self, asset: str, metric: str) -> list[float]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                "SELECT value FROM metric_history WHERE asset = ? AND metric = ? ORDER BY observed_at ASC",
                (asset, metric),
            ).fetchall()
        return [float(row[0]) for row in rows]

    def series(self, asset: str, metric: str, limit: int = 100) -> list[dict[str, float]]:
        if not 1 <= limit <= self.max_samples:
            raise ValueError(f"limit must be between 1 and {self.max_samples}")
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                "SELECT observed_at, value FROM metric_history "
                "WHERE asset = ? AND metric = ? ORDER BY observed_at DESC LIMIT ?",
                (asset, metric, limit),
            ).fetchall()
        return [{"observed_at": float(observed_at), "value": float(value)} for observed_at, value in reversed(rows)]
