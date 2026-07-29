from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path

from .models import Signal


class AlertDeduplicator:
    def __init__(self, path: str | Path, cooldown_seconds: float = 900.0):
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")
        self.path = Path(path)
        self.cooldown_seconds = float(cooldown_seconds)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS alert_dedup ("
                "fingerprint TEXT PRIMARY KEY, asset TEXT NOT NULL, signal_type TEXT NOT NULL, "
                "severity TEXT NOT NULL, basis TEXT NOT NULL, emitted_at REAL NOT NULL)"
            )

    @staticmethod
    def fingerprint(signal: Signal) -> str:
        if signal.signal_type == "composite_market_risk":
            stable_detail = signal.measurements.get("factor_signature", "")
        else:
            stable_detail = signal.basis
        payload = "\x1f".join((signal.asset, signal.signal_type, signal.severity, str(stable_detail)))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def should_emit(self, signal: Signal, now: float | None = None) -> bool:
        timestamp = time.time() if now is None else float(now)
        fingerprint = self.fingerprint(signal)
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT emitted_at FROM alert_dedup WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
            if row is not None and timestamp - float(row[0]) < self.cooldown_seconds:
                return False
            connection.execute(
                "INSERT INTO alert_dedup(fingerprint, asset, signal_type, severity, basis, emitted_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(fingerprint) DO UPDATE SET emitted_at=excluded.emitted_at",
                (fingerprint, signal.asset, signal.signal_type, signal.severity, signal.basis, timestamp),
            )
        return True
