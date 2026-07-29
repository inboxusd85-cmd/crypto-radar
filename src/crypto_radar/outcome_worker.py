from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from .candle_history import CandleHistory
from .events import AlertEventJournal
from .outcomes import OutcomeStore, build_time_split_report, build_validation_report, materialize_event_outcomes


def run_once(
    history_path: str | Path,
    events: Iterable[dict[str, Any]] | None = None,
    limit: int = 500,
) -> dict[str, int]:
    """Materialize outcomes for one batch; safe to invoke from cron repeatedly."""
    path = Path(history_path)
    source = list(events) if events is not None else AlertEventJournal(path).list_events(limit=limit)
    stats = {"attempted": len(source), "ready": 0, "pending": 0, "errors": 0}
    history = CandleHistory(path)
    store = OutcomeStore(path)
    for event in source:
        try:
            outcomes = materialize_event_outcomes(event, history, store)
        except (KeyError, TypeError, ValueError):
            stats["errors"] += 1
            continue
        stats["ready"] += sum(item.get("status") == "ready" for item in outcomes.values())
        stats["pending"] += sum(item.get("status") == "pending" for item in outcomes.values())
    stats["status"] = "error" if stats["errors"] else "ok"
    store.record_worker_run(stats)
    return stats


def replay_once(source_path: str | Path, archive_path: str | Path, limit: int = 500) -> dict[str, int | str | bool]:
    """Replay source events against an isolated archive DB without touching source outcomes."""
    if limit < 1:
        raise ValueError("limit must be positive")
    source = Path(source_path)
    archive = Path(archive_path)
    events = AlertEventJournal(source).list_events(limit=limit)
    stats: dict[str, int | str | bool] = {"read_only": True, "source_events": len(events), "attempted": len(events), "ready": 0, "pending": 0, "errors": 0}
    history = CandleHistory(archive)
    store = OutcomeStore(archive)
    for event in events:
        try:
            outcomes = materialize_event_outcomes(event, history, store)
        except (KeyError, TypeError, ValueError):
            stats["errors"] = int(stats["errors"]) + 1
            continue
        stats["ready"] = int(stats["ready"]) + sum(item.get("status") == "ready" for item in outcomes.values())
        stats["pending"] = int(stats["pending"]) + sum(item.get("status") == "pending" for item in outcomes.values())
    stats["status"] = "error" if stats["errors"] else "ok"
    store.record_worker_run(stats)
    return stats


def build_archive_validation_report(source_path: str | Path, archive_path: str | Path, limit: int = 500, train_fraction: float = 0.8) -> dict[str, Any]:
    """Build read-only validation metrics from source events and isolated archive outcomes."""
    if limit < 1:
        raise ValueError("limit must be positive")
    events = AlertEventJournal(source_path).list_events(limit=limit)
    store = OutcomeStore(archive_path)
    rows = [{**event, "outcomes": store.get(str(event.get("event_id", "")))} for event in events]
    return {
        "read_only": True,
        "source_db": str(source_path),
        "archive_db": str(archive_path),
        "event_count": len(rows),
        "validation": build_validation_report(rows),
        "time_split": build_time_split_report(rows, train_fraction=train_fraction),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize Crypto Radar forward outcomes once")
    parser.add_argument("--db", type=Path, default=Path("data/crypto_radar.sqlite3"))
    parser.add_argument("--replay-from", type=Path, help="Read events from this source DB and write outcomes only to --db")
    parser.add_argument("--validation-from", type=Path, help="Read source events and report validation against outcomes in --db")
    parser.add_argument("--train-fraction", type=float, default=0.8)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.validation_from:
        report = build_archive_validation_report(args.validation_from, args.db, args.limit, args.train_fraction)
    else:
        report = replay_once(args.replay_from, args.db, args.limit) if args.replay_from else run_once(args.db, limit=args.limit)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
