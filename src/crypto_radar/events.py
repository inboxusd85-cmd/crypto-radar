from __future__ import annotations

import base64
import json
import sqlite3
import time
import uuid
from pathlib import Path

from .models import Signal
from .serialization import signal_to_dict


class AlertEventJournal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            self._ensure_schema(connection)

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        columns = connection.execute("PRAGMA table_info(alert_events)").fetchall()
        if columns:
            primary_key = next((row[1] for row in columns if row[5] == 1), None)
            if primary_key == "signal_id":
                connection.execute("ALTER TABLE alert_events RENAME TO alert_events_legacy")
                AlertEventJournal._create_schema(connection)
                rows = connection.execute(
                    "SELECT signal_id, asset, severity, signal_type, observed_at, recorded_at, payload "
                    "FROM alert_events_legacy"
                ).fetchall()
                for signal_id, asset, severity, signal_type, observed_at, recorded_at, payload in rows:
                    event_id = f"legacy-{uuid.uuid4().hex}"
                    data = json.loads(payload)
                    data["event_id"] = event_id
                    connection.execute(
                        "INSERT INTO alert_events(event_id, signal_id, asset, severity, signal_type, observed_at, recorded_at, payload) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (event_id, signal_id, asset, severity, signal_type, observed_at, recorded_at,
                         json.dumps(data, ensure_ascii=False, separators=(",", ":"))),
                    )
                connection.execute("DROP TABLE alert_events_legacy")
                return
        AlertEventJournal._create_schema(connection)

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS alert_events ("
            "event_id TEXT PRIMARY KEY, signal_id TEXT NOT NULL, asset TEXT NOT NULL, severity TEXT NOT NULL, "
            "signal_type TEXT NOT NULL, observed_at TEXT NOT NULL, recorded_at REAL NOT NULL, payload TEXT NOT NULL)"
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_alert_events_asset ON alert_events(asset, recorded_at DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_alert_events_signal ON alert_events(signal_id, recorded_at DESC)")
        connection.execute("DROP INDEX IF EXISTS uq_alert_events_observation")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_social_alert_events_observation ON alert_events(signal_id, observed_at) WHERE signal_type = 'social_claim'")

    def record(self, signal: Signal, recorded_at: float | None = None) -> bool:
        timestamp = time.time() if recorded_at is None else float(recorded_at)
        event_id = uuid.uuid4().hex
        data = signal_to_dict(signal)
        data["event_id"] = event_id
        data["recorded_at"] = timestamp
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        with sqlite3.connect(self.path) as connection:
            try:
                connection.execute(
                    "INSERT INTO alert_events(event_id, signal_id, asset, severity, signal_type, observed_at, recorded_at, payload) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (event_id, signal.signal_id, signal.asset, signal.severity, signal.signal_type,
                     signal.observed_at, timestamp, payload),
                )
            except sqlite3.IntegrityError as exc:
                if "uq_alert_events_observation" not in str(exc) and "alert_events.signal_id" not in str(exc):
                    raise
                return False
        return True

    def record_many(self, signals: list[Signal], recorded_at: float | None = None) -> dict[str, int]:
        stats = {"attempted": len(signals), "recorded": 0, "duplicates_skipped": 0}
        batch_timestamp = time.time() if recorded_at is None else float(recorded_at)
        with sqlite3.connect(self.path) as connection:
            for signal in signals:
                timestamp = batch_timestamp
                event_id = uuid.uuid4().hex
                data = signal_to_dict(signal)
                data["event_id"] = event_id
                data["recorded_at"] = timestamp
                payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                try:
                    connection.execute(
                        "INSERT INTO alert_events(event_id, signal_id, asset, severity, signal_type, observed_at, recorded_at, payload) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (event_id, signal.signal_id, signal.asset, signal.severity, signal.signal_type,
                         signal.observed_at, timestamp, payload),
                    )
                except sqlite3.IntegrityError as exc:
                    if "uq_social_alert_events_observation" not in str(exc) and "alert_events.signal_id" not in str(exc):
                        raise
                    stats["duplicates_skipped"] += 1
                else:
                    stats["recorded"] += 1
        return stats

    def list_events_page(
        self,
        asset: str | None = None,
        severity: str | None = None,
        before: float | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        clauses: list[str] = []
        parameters: list[object] = []
        if asset:
            clauses.append("asset = ?")
            parameters.append(asset.upper())
        if severity:
            clauses.append("severity = ?")
            parameters.append(severity)
        if cursor is not None:
            recorded_at_text, event_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
            cursor_recorded_at = float(recorded_at_text)
            clauses.append("(recorded_at < ? OR (recorded_at = ? AND event_id < ?))")
            parameters.extend([cursor_recorded_at, cursor_recorded_at, event_id])
        elif before is not None:
            clauses.append("recorded_at < ?")
            parameters.append(float(before))
        query = "SELECT payload, recorded_at, event_id FROM alert_events"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY recorded_at DESC, event_id DESC LIMIT ?"
        parameters.append(limit)
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(query, parameters).fetchall()
        events = [json.loads(payload) for payload, _, _ in rows]
        next_cursor = None
        if len(rows) == limit:
            next_cursor = base64.urlsafe_b64encode(f"{rows[-1][1]}|{rows[-1][2]}".encode()).decode()
        return {
            "events": events,
            "next_before": float(rows[-1][1]) if len(rows) == limit else None,
            "next_cursor": next_cursor,
        }

    def list_events(self, asset: str | None = None, limit: int = 50) -> list[dict]:
        if limit < 1:
            raise ValueError("limit must be positive")
        query = "SELECT payload FROM alert_events"
        parameters: list[object] = []
        if asset:
            query += " WHERE asset = ?"
            parameters.append(asset.upper())
        query += " ORDER BY recorded_at DESC LIMIT ?"
        parameters.append(limit)
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [json.loads(row[0]) for row in rows]
