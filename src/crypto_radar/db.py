from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Signal


@dataclass(frozen=True)
class SaveResult:
    signal_id: str
    inserted: bool


@dataclass(frozen=True)
class RawSaveResult:
    payload_id: str
    inserted: bool


class SignalStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    signal_id TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL UNIQUE,
                    asset TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS raw_payloads (
                    payload_id TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _stable_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def save(self, signal: Signal) -> SaveResult:
        payload = self._stable_json(signal.__dict__)
        content_hash = self._hash(payload)
        signal_id = content_hash[:16]
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO signals(signal_id, content_hash, asset, signal_type, payload) VALUES (?, ?, ?, ?, ?)",
                (signal_id, content_hash, signal.asset, signal.signal_type, payload),
            )
            return SaveResult(signal_id, cursor.rowcount == 1)

    def get(self, signal_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM signals WHERE signal_id = ?", (signal_id,)).fetchone()
        if row is None:
            raise KeyError(signal_id)
        return json.loads(row["payload"])

    def save_raw(self, payload: Any) -> RawSaveResult:
        serialized = self._stable_json(payload)
        content_hash = self._hash(serialized)
        payload_id = content_hash[:16]
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO raw_payloads(payload_id, content_hash, payload) VALUES (?, ?, ?)",
                (payload_id, content_hash, serialized),
            )
            return RawSaveResult(payload_id, cursor.rowcount == 1)

    def get_raw(self, payload_id: str) -> dict[str, str]:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM raw_payloads WHERE payload_id = ?", (payload_id,)).fetchone()
        if row is None:
            raise KeyError(payload_id)
        return {"payload": row["payload"]}
