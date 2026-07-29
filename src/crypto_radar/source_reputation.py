from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from pathlib import Path
import uuid


_VALID_OUTCOMES = {"confirmed", "refuted", "uncertain"}


def reputation_decay(reviewed_at: str, now: datetime | None = None, half_life_hours: float = 168.0) -> float:
    if half_life_hours <= 0:
        raise ValueError("half_life_hours must be positive")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    reviewed = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00")).astimezone(timezone.utc)
    age_hours = max(0.0, (current - reviewed).total_seconds() / 3600.0)
    return 2.0 ** (-age_hours / half_life_hours)


def decayed_reputation(score: float, reviewed_at: str, now: datetime | None = None, half_life_hours: float = 168.0) -> float:
    decay = reputation_decay(reviewed_at, now=now, half_life_hours=half_life_hours)
    return round(0.5 + (max(0.0, min(1.0, score)) - 0.5) * decay, 4)


class SourceReputationStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS source_reputation ("
                "author_handle TEXT PRIMARY KEY, confirmed INTEGER NOT NULL DEFAULT 0, "
                "refuted INTEGER NOT NULL DEFAULT 0, uncertain INTEGER NOT NULL DEFAULT 0)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS source_reputation_outcomes ("
                "outcome_id TEXT PRIMARY KEY, author_handle TEXT NOT NULL, outcome TEXT NOT NULL, "
                "reference TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', recorded_at TEXT NOT NULL)"
            )

    @staticmethod
    def _record(author_handle: str, confirmed: int, refuted: int, uncertain: int) -> dict:
        score = (1.0 + confirmed) / (2.0 + confirmed + refuted)
        return {
            "author_handle": author_handle,
            "score": round(max(0.0, min(1.0, score)), 4),
            "confirmed": confirmed,
            "refuted": refuted,
            "uncertain": uncertain,
        }

    def get(self, author_handle: str, as_of: datetime | None = None, half_life_hours: float = 168.0) -> dict:
        author = author_handle.strip().lower()
        if not author:
            raise ValueError("author_handle is required")
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT confirmed, refuted, uncertain FROM source_reputation WHERE author_handle = ?",
                (author,),
            ).fetchone()
        record = self._record(author, *(row or (0, 0, 0)))
        if as_of is not None and record["confirmed"] + record["refuted"] + record["uncertain"]:
            outcomes = self.list_outcomes(author, limit=1)
            if outcomes:
                record["reputation_decay"] = round(reputation_decay(outcomes[0]["recorded_at"], as_of, half_life_hours), 4)
                record["score"] = decayed_reputation(record["score"], outcomes[0]["recorded_at"], as_of, half_life_hours)
                record["last_reviewed_at"] = outcomes[0]["recorded_at"]
        return record

    def record_outcome(
        self,
        author_handle: str,
        outcome: str,
        reference: str = "",
        note: str = "",
    ) -> dict:
        author = author_handle.strip().lower()
        if not author:
            raise ValueError("author_handle is required")
        if outcome not in _VALID_OUTCOMES:
            raise ValueError(f"outcome must be one of {sorted(_VALID_OUTCOMES)}")
        recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO source_reputation(author_handle, confirmed, refuted, uncertain) VALUES (?, 0, 0, 0) "
                "ON CONFLICT(author_handle) DO NOTHING",
                (author,),
            )
            connection.execute(
                f"UPDATE source_reputation SET {outcome} = {outcome} + 1 WHERE author_handle = ?",
                (author,),
            )
            connection.execute(
                "INSERT INTO source_reputation_outcomes(outcome_id, author_handle, outcome, reference, note, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, author, outcome, reference, note, recorded_at),
            )
        return self.get(author)

    def list_outcomes(self, author_handle: str | None = None, limit: int = 50) -> list[dict]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        query = (
            "SELECT outcome_id, author_handle, outcome, reference, note, recorded_at "
            "FROM source_reputation_outcomes"
        )
        parameters: tuple = ()
        if author_handle:
            query += " WHERE author_handle = ?"
            parameters = (author_handle.strip().lower(),)
        query += " ORDER BY recorded_at DESC, outcome_id DESC LIMIT ?"
        parameters += (limit,)
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(query, parameters).fetchall()
        keys = ("outcome_id", "author_handle", "outcome", "reference", "note", "recorded_at")
        return [dict(zip(keys, row)) for row in rows]
