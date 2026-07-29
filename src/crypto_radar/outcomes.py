from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .candle_history import CandleHistory
from .history import MetricHistory


REVIEW_STATUSES = {"pending", "confirmed", "refuted", "deferred"}
HORIZON_HOURS = {"1h": 1, "6h": 6, "1d": 24, "1w": 168}
MAX_CANDLE_LAG_MS = 3_600_000


def _epoch_ms(value: str | float | int) -> int:
    if isinstance(value, (float, int)):
        return int(float(value) * 1000) if float(value) < 10_000_000_000 else int(value)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return int(parsed.timestamp() * 1000)


def _direction_sign(value: object) -> int:
    if value in {"лонг", "рост"}:
        return 1
    if value in {"шорт", "снижение"}:
        return -1
    return 0


def summarize_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize observable 1h outcomes without treating pending rows as failures."""
    by_severity: dict[str, dict[str, Any]] = {}
    by_status: dict[str, dict[str, Any]] = {}
    by_horizon: dict[str, dict[str, Any]] = {
        horizon: {"ready_count": 0, "coverage_pct": None, "average_return_pct": None, "directional_accuracy_pct": None, "_returns": [], "_directional_matches": 0, "_directional_total": 0}
        for horizon in HORIZON_HOURS
    }
    ready_returns: list[float] = []
    directional_matches = 0
    directional_total = 0
    for row in rows:
        severity = str(row.get("severity", "unknown"))
        status = str(row.get("review", {}).get("status", "unknown"))
        bucket = by_severity.setdefault(severity, {"count": 0, "ready_count_1h": 0, "average_return_pct_1h": None})
        status_bucket = by_status.setdefault(status, {"count": 0, "ready_count_1h": 0, "average_return_pct_1h": None})
        bucket["count"] += 1
        status_bucket["count"] += 1
        for horizon, horizon_bucket in by_horizon.items():
            outcome = row.get("outcomes", {}).get(horizon, {})
            if outcome.get("status") != "ready" or not isinstance(outcome.get("return_pct"), (int, float)):
                continue
            value = float(outcome["return_pct"])
            horizon_bucket["ready_count"] += 1
            horizon_bucket["_returns"].append(value)
            direction = row.get("market_direction")
            direction_sign = _direction_sign(direction)
            if direction_sign and value != 0:
                horizon_bucket["_directional_total"] += 1
                horizon_bucket["_directional_matches"] += int(direction_sign == (1 if value > 0 else -1))

        outcome = row.get("outcomes", {}).get("1h", {})
        if outcome.get("status") != "ready" or not isinstance(outcome.get("return_pct"), (int, float)):
            continue
        value = float(outcome["return_pct"])
        ready_returns.append(value)
        bucket["ready_count_1h"] += 1
        bucket_returns = bucket.setdefault("_returns", [])
        status_returns = status_bucket.setdefault("_returns", [])
        bucket_returns.append(value)
        status_returns.append(value)
        status_bucket["ready_count_1h"] += 1
        direction = row.get("market_direction")
        direction_sign = _direction_sign(direction)
        if direction_sign and value != 0:
            directional_total += 1
            directional_matches += int(direction_sign == (1 if value > 0 else -1))
    for buckets in (by_severity, by_status):
        for bucket in buckets.values():
            values = bucket.pop("_returns", [])
            bucket["average_return_pct_1h"] = round(sum(values) / len(values), 6) if values else None
    for horizon_bucket in by_horizon.values():
        values = horizon_bucket.pop("_returns")
        ready_count = horizon_bucket["ready_count"]
        horizon_bucket["coverage_pct"] = round(ready_count / len(rows) * 100, 2) if rows else None
        horizon_bucket["average_return_pct"] = round(sum(values) / len(values), 6) if values else None
        total = horizon_bucket.pop("_directional_total")
        matches = horizon_bucket.pop("_directional_matches")
        horizon_bucket["directional_accuracy_pct"] = round(matches / total * 100, 2) if total else None
    ready_count = len(ready_returns)
    return {
        "reviewed_count": len(rows),
        "ready_count_1h": ready_count,
        "coverage_pct_1h": round(ready_count / len(rows) * 100, 2) if rows else None,
        "average_return_pct_1h": round(sum(ready_returns) / ready_count, 6) if ready_returns else None,
        "directional_accuracy_pct_1h": round(directional_matches / directional_total * 100, 2) if directional_total else None,
        "by_severity": dict(sorted(by_severity.items())),
        "by_status": dict(sorted(by_status.items())),
        "by_horizon": dict(by_horizon),
    }


def calculate_forward_outcomes(
    history: CandleHistory,
    asset: str,
    timeframe: str,
    signal_open_time: int,
    entry_price: float,
) -> dict[str, dict[str, Any]]:
    """Calculate first available close at or after each forward horizon."""
    candles = history.list_candles(asset, timeframe, limit=500)
    outcomes: dict[str, dict[str, Any]] = {}
    for horizon, hours in HORIZON_HOURS.items():
        target = signal_open_time + hours * 3_600_000
        candle = next((item for item in candles if item.open_time >= target), None)
        if candle is None:
            outcomes[horizon] = {"status": "pending"}
            continue
        if candle.open_time - target > MAX_CANDLE_LAG_MS:
            outcomes[horizon] = {"status": "pending", "reason": "data_gap"}
            continue
        close = float(candle.close)
        outcomes[horizon] = {
            "status": "ready",
            "close": close,
            "return_pct": round((close / entry_price - 1) * 100, 6),
        }
    return outcomes


def calculate_news_outcomes(
    history: CandleHistory,
    asset: str,
    timeframe: str,
    published_at: str | float | int,
) -> dict[str, Any]:
    """Calculate forward news outcomes without labeling when entry/forward data is missing."""
    publication_ms = _epoch_ms(published_at)
    candles = history.list_candles(asset, timeframe, limit=500)
    entry = next((candle for candle in candles if candle.open_time >= publication_ms), None)
    if entry is None:
        return {
            "entry": {"status": "pending", "reason": "missing_entry_candle"},
            "outcomes": {horizon: {"status": "pending", "reason": "missing_entry_candle"} for horizon in HORIZON_HOURS},
        }
    return {
        "entry": {"status": "ready", "price": float(entry.close), "open_time": entry.open_time},
        "outcomes": calculate_forward_outcomes(history, asset, timeframe, entry.open_time, float(entry.close)),
    }


def summarize_news_readiness(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Summarize ready/pending/data-gap outcome coverage without collapsing unknowns."""
    summary = {
        horizon: {"ready_count": 0, "pending_count": 0, "data_gap_count": 0, "coverage_pct": 0.0}
        for horizon in HORIZON_HOURS
    }
    for record in records:
        outcomes = record.get("outcomes", {}).get("outcomes", record.get("outcomes", {}))
        for horizon, bucket in summary.items():
            status = outcomes.get(horizon, {}).get("status", "pending")
            if status == "ready":
                bucket["ready_count"] += 1
            elif status == "data_gap":
                bucket["data_gap_count"] += 1
            else:
                bucket["pending_count"] += 1
    total = len(records)
    for bucket in summary.values():
        bucket["coverage_pct"] = round(bucket["ready_count"] / total * 100, 2) if total else 0.0
    return summary


def summarize_news_event_types(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize news outcomes by taxonomy without joining them to market composite quality."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        buckets.setdefault(str(record.get("event_type", "general")), []).append(record)
    result: dict[str, Any] = {}
    for event_type, items in sorted(buckets.items()):
        readiness = summarize_news_readiness(items)
        for horizon, bucket in readiness.items():
            values = [
                float(item["outcomes"]["outcomes"][horizon]["return_pct"])
                for item in items
                if item.get("outcomes", {}).get("outcomes", {}).get(horizon, {}).get("status") == "ready"
                and isinstance(item["outcomes"]["outcomes"][horizon].get("return_pct"), (int, float))
            ]
            bucket["average_return_pct"] = round(sum(values) / len(values), 6) if values else None
            ready_count = bucket["ready_count"]
            bucket["quality_status"] = "insufficient_sample" if ready_count < 10 else "collecting" if ready_count < 100 else "review_candidate"
            if ready_count < 10:
                bucket["positive_rate_pct"] = None
                bucket["negative_rate_pct"] = None
                bucket["flat_rate_pct"] = None
                bucket["directional_accuracy_pct"] = None
                bucket["directional_sample_count"] = None
                bucket["directional_accuracy_ci95_pct"] = None
            else:
                positive = sum(value > 0 for value in values)
                negative = sum(value < 0 for value in values)
                flat = sum(value == 0 for value in values)
                bucket["positive_rate_pct"] = round(positive / ready_count * 100, 2)
                bucket["negative_rate_pct"] = round(negative / ready_count * 100, 2)
                bucket["flat_rate_pct"] = round(flat / ready_count * 100, 2)
                directional = [
                    (float(item.get("production_score", 0)), float(item["outcomes"]["outcomes"][horizon]["return_pct"]))
                    for item in items
                    if item.get("outcomes", {}).get("outcomes", {}).get(horizon, {}).get("status") == "ready"
                    and isinstance(item.get("production_score"), (int, float))
                    and item["production_score"] != 0
                    and isinstance(item["outcomes"]["outcomes"][horizon].get("return_pct"), (int, float))
                    and item["outcomes"]["outcomes"][horizon]["return_pct"] != 0
                ]
                bucket["directional_accuracy_pct"] = round(sum((score > 0) == (value > 0) for score, value in directional) / len(directional) * 100, 2) if directional else None
                bucket["directional_sample_count"] = len(directional)
                if directional:
                    successes = sum((score > 0) == (value > 0) for score, value in directional)
                    n = len(directional)
                    z = 1.96
                    center = (successes / n + z * z / (2 * n)) / (1 + z * z / n)
                    half = z * math.sqrt((successes / n * (1 - successes / n) + z * z / (4 * n)) / n) / (1 + z * z / n)
                    bucket["directional_accuracy_ci95_pct"] = [round((center - half) * 100, 2), round((center + half) * 100, 2)]
                else:
                    bucket["directional_accuracy_ci95_pct"] = None
        score_distribution = {"positive": 0, "neutral": 0, "negative": 0}
        for item in items:
            score = item.get("production_score", 0)
            if isinstance(score, (int, float)):
                score_distribution["positive" if score > 0 else "negative" if score < 0 else "neutral"] += 1
        sample_status = "insufficient_sample" if len(items) < 10 else "collecting" if len(items) < 100 else "sufficient_for_review"
        result[event_type] = {"count": len(items), "sample_status": sample_status, "score_distribution": score_distribution, "by_horizon": readiness}
    return result


def summarize_news_training_readiness(
    readiness: dict[str, dict[str, Any]],
    *,
    min_samples: int = 100,
    min_coverage_pct: float = 80.0,
) -> dict[str, Any]:
    """Expose a conservative, explainable gate before offline model training."""
    horizons: dict[str, dict[str, Any]] = {}
    for horizon, bucket in readiness.items():
        reasons: list[str] = []
        if bucket["ready_count"] < min_samples:
            reasons.append("insufficient_samples")
        if bucket["coverage_pct"] < min_coverage_pct:
            reasons.append("insufficient_coverage")
        horizons[horizon] = {
            "status": "ready" if not reasons else "blocked",
            "ready_count": bucket["ready_count"],
            "coverage_pct": bucket["coverage_pct"],
            "reasons": reasons,
        }
    return {"min_samples": min_samples, "min_coverage_pct": min_coverage_pct, "horizons": horizons}


def build_news_training_plan(
    readiness: dict[str, dict[str, Any]],
    horizon: str,
    *,
    min_samples: int = 100,
    min_coverage_pct: float = 80.0,
) -> dict[str, Any]:
    """Return a training plan only when the selected horizon passes the data gate."""
    bucket = readiness.get(horizon)
    if bucket is None:
        return {"status": "blocked", "horizon": horizon, "ready_count": 0, "coverage_pct": 0.0, "reasons": ["unknown_horizon"]}
    reasons: list[str] = []
    if bucket["ready_count"] < min_samples:
        reasons.append("insufficient_samples")
    if bucket["coverage_pct"] < min_coverage_pct:
        reasons.append("insufficient_coverage")
    return {
        "status": "ready" if not reasons else "blocked",
        "horizon": horizon,
        "ready_count": bucket["ready_count"],
        "coverage_pct": bucket["coverage_pct"],
        "reasons": reasons,
    }


def split_news_dataset(
    records: list[dict[str, Any]],
    horizon: str,
    *,
    validation_fraction: float = 0.2,
) -> dict[str, Any]:
    """Create a chronological split from ready records without future leakage."""
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1")
    eligible = [
        record for record in records
        if record.get("outcomes", {}).get(horizon, {}).get("status") == "ready"
        and isinstance(record.get("outcomes", {}).get(horizon, {}).get("return_pct"), (int, float))
    ]
    eligible.sort(key=lambda record: record["published_at"])
    validation_count = max(1, int(len(eligible) * validation_fraction + 0.999999)) if eligible else 0
    split_at = len(eligible) - validation_count
    return {
        "train": eligible[:split_at],
        "validation": eligible[split_at:],
        "eligible_count": len(eligible),
        "excluded_count": len(records) - len(eligible),
    }


def prepare_news_training_dataset(
    records: list[dict[str, Any]],
    horizon: str,
    *,
    validation_fraction: float = 0.2,
    min_samples: int = 100,
    min_coverage_pct: float = 80.0,
) -> dict[str, Any]:
    """Gate and split a news dataset for future offline training without leakage."""
    readiness = summarize_news_readiness(records)
    plan = build_news_training_plan(
        readiness,
        horizon,
        min_samples=min_samples,
        min_coverage_pct=min_coverage_pct,
    )
    if plan["status"] == "blocked":
        return plan
    return {**plan, "split": split_news_dataset(records, horizon, validation_fraction=validation_fraction)}


class OutcomeStore:
    """Persistent, idempotent forward outcomes keyed by event and horizon."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS signal_outcomes ("
                "event_id TEXT NOT NULL, horizon TEXT NOT NULL, payload TEXT NOT NULL, "
                "created_at REAL NOT NULL, updated_at REAL NOT NULL, PRIMARY KEY(event_id, horizon))"
            )

    def get(self, event_id: str) -> dict[str, dict[str, Any]]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                "SELECT horizon, payload FROM signal_outcomes WHERE event_id = ? ORDER BY horizon", (event_id,)
            ).fetchall()
        return {horizon: __import__("json").loads(payload) for horizon, payload in rows}

    def save_pending_or_ready(self, event_id: str, outcomes: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        now = datetime.now().timestamp()
        with sqlite3.connect(self.path) as connection:
            for horizon, outcome in outcomes.items():
                existing = connection.execute(
                    "SELECT payload FROM signal_outcomes WHERE event_id = ? AND horizon = ?", (event_id, horizon)
                ).fetchone()
                if existing and __import__("json").loads(existing[0]).get("status") == "ready":
                    continue
                payload = __import__("json").dumps(outcome, ensure_ascii=False, separators=(",", ":"))
                connection.execute(
                    "INSERT INTO signal_outcomes(event_id, horizon, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(event_id, horizon) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                    (event_id, horizon, payload, now, now),
                )
        return self.get(event_id)

    def record_worker_run(self, stats: dict[str, Any]) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS outcome_worker_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO outcome_worker_state(key, value) VALUES ('last_run', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (json.dumps({**stats, "completed_at": datetime.now().timestamp()}, ensure_ascii=False),),
            )

    def worker_state(self) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS outcome_worker_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            row = connection.execute("SELECT value FROM outcome_worker_state WHERE key = 'last_run'").fetchone()
        return json.loads(row[0]) if row else None


def resolve_entry_price(event: dict[str, Any], history_path: str | Path) -> float | None:
    measurements = event.get("measurements") if isinstance(event.get("measurements"), dict) else {}
    candidate = measurements.get("entry_price", measurements.get("mark_price"))
    if isinstance(candidate, (int, float)):
        return float(candidate)
    observed_at = event.get("observed_at")
    asset = event.get("asset")
    if not isinstance(observed_at, str) or not isinstance(asset, str):
        return None
    points = MetricHistory(history_path).series(asset, "mark_price", limit=100)
    observed_epoch = _epoch_ms(observed_at) / 1000
    prior = [point for point in points if point["observed_at"] <= observed_epoch]
    if prior:
        return float(prior[-1]["value"])
    candles = CandleHistory(history_path).list_candles(asset, "1h", limit=500)
    prior_candles = [candle for candle in candles if candle.open_time <= _epoch_ms(observed_at)]
    return float(prior_candles[-1].open) if prior_candles else None


def materialize_event_outcomes(event: dict[str, Any], history: CandleHistory, store: OutcomeStore) -> dict[str, dict[str, Any]]:
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event_id is required")
    measurements = event.get("measurements", {})
    entry_price = resolve_entry_price(event, history.path)
    observed_at = event.get("observed_at")
    if entry_price is None or not observed_at:
        return store.save_pending_or_ready(event_id, {horizon: {"status": "pending", "reason": "missing_entry_price"} for horizon in HORIZON_HOURS})
    timeframe = measurements.get("timeframe", "1h")
    if not isinstance(timeframe, str) or timeframe not in {"1m", "10m", "1h", "6h", "1d", "1w"}:
        timeframe = "1h"
    calculated = calculate_forward_outcomes(history, event["asset"], timeframe, _epoch_ms(observed_at), float(entry_price))
    return store.save_pending_or_ready(event_id, calculated)


class OutcomeReviewStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS outcome_reviews ("
                "event_id TEXT PRIMARY KEY, status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', reviewed_at REAL NOT NULL)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_outcome_reviews_status ON outcome_reviews(status, reviewed_at DESC)")

    def review(self, event_id: str, status: str, note: str = "", reviewed_at: float | None = None) -> dict[str, Any]:
        if not event_id.strip():
            raise ValueError("event_id is required")
        if status not in REVIEW_STATUSES:
            raise ValueError(f"unsupported review status: {status}")
        timestamp = float(reviewed_at) if reviewed_at is not None else datetime.now().timestamp()
        result = {"event_id": event_id, "status": status, "note": note, "reviewed_at": timestamp}
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO outcome_reviews(event_id, status, note, reviewed_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(event_id) DO UPDATE SET status=excluded.status, note=excluded.note, reviewed_at=excluded.reviewed_at",
                (event_id, status, note, timestamp),
            )
        return result

    def list_reviews(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if status is not None and status not in REVIEW_STATUSES:
            raise ValueError(f"unsupported review status: {status}")
        query = "SELECT event_id, status, note, reviewed_at FROM outcome_reviews"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY reviewed_at DESC LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            {"event_id": row[0], "status": row[1], "note": row[2], "reviewed_at": row[3]}
            for row in rows
        ]


def build_time_split_report(rows: list[dict[str, Any]], train_fraction: float = 0.8) -> dict[str, Any]:
    """Build an exploratory chronological train/test report without changing policy."""
    if not 0.5 <= train_fraction < 1:
        raise ValueError("train_fraction must be between 0.5 and 1")
    ordered = sorted(rows, key=lambda row: str(row.get("observed_at", "")))
    split_at = max(1, min(len(ordered) - 1, int(len(ordered) * train_fraction))) if len(ordered) > 1 else len(ordered)

    def summarize(part: list[dict[str, Any]]) -> dict[str, Any]:
        by_horizon: dict[str, dict[str, Any]] = {}
        for horizon in HORIZON_HOURS:
            ready: list[float] = []
            pending = 0
            data_gap = 0
            matches = 0
            directional = 0
            for row in part:
                outcome = row.get("outcomes", {}).get(horizon, {})
                value = outcome.get("return_pct") if isinstance(outcome, dict) else None
                if outcome.get("status") != "ready" or not isinstance(value, (int, float)):
                    if outcome.get("status") == "data_gap":
                        data_gap += 1
                    else:
                        pending += 1
                    continue
                value = float(value)
                ready.append(value)
                predicted = _direction_sign(row.get("market_direction"))
                if predicted and value:
                    directional += 1
                    matches += int(predicted == (1 if value > 0 else -1))
            by_horizon[horizon] = {
                "sample_size": len(ready),
                "pending_count": pending,
                "data_gap_count": data_gap,
                "coverage_pct": round(len(ready) / len(part) * 100, 2) if part else None,
                "win_rate_pct": round(sum(value > 0 for value in ready) / len(ready) * 100, 2) if ready else None,
                "average_return_pct": round(sum(ready) / len(ready), 6) if ready else None,
                "directional_hit_rate_pct": round(matches / directional * 100, 2) if directional else None,
            }
        return {"event_count": len(part), "by_horizon": by_horizon}

    train = summarize(ordered[:split_at])
    test = summarize(ordered[split_at:])

    def gate(metrics: dict[str, Any]) -> dict[str, Any]:
        reasons: list[str] = []
        if metrics["sample_size"] < 100:
            reasons.append("insufficient_samples")
        if (metrics["coverage_pct"] or 0) < 80.0:
            reasons.append("insufficient_coverage")
        return {
            "status": "ready" if not reasons else "blocked",
            "sample_size": metrics["sample_size"],
            "coverage_pct": metrics["coverage_pct"],
            "reasons": reasons,
        }

    dataset_gate = {"min_samples": 100, "min_coverage_pct": 80.0}
    for horizon in HORIZON_HOURS:
        dataset_gate[f"train_{horizon}"] = gate(train["by_horizon"][horizon])
        dataset_gate[f"test_{horizon}"] = gate(test["by_horizon"][horizon])

    return {
        "read_only": True,
        "status": "exploratory",
        "train_fraction": train_fraction,
        "split_at": split_at,
        "train": train,
        "test": test,
        "dataset_gate": dataset_gate,
        "note": "Chronological descriptive evaluation only; no production promotion or weight changes.",
    }


def build_validation_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a read-only validation report from materialized forward outcomes."""
    by_horizon: dict[str, dict[str, Any]] = {}
    for horizon in HORIZON_HOURS:
        returns: list[float] = []
        pending_count = 0
        win_count = loss_count = flat_count = 0
        directional_matches = directional_total = 0
        for row in rows:
            outcome = row.get("outcomes", {}).get(horizon, {})
            value = outcome.get("return_pct") if isinstance(outcome, dict) else None
            if outcome.get("status") != "ready" or not isinstance(value, (int, float)):
                pending_count += 1
                continue
            value = float(value)
            returns.append(value)
            if value > 0:
                win_count += 1
            elif value < 0:
                loss_count += 1
            else:
                flat_count += 1
            direction = row.get("market_direction")
            if direction in {"рост", "снижение"} and value != 0:
                directional_total += 1
                directional_matches += int((direction == "рост") == (value > 0))
        sample_size = len(returns)
        by_horizon[horizon] = {
            "sample_size": sample_size,
            "pending_count": pending_count,
            "win_count": win_count,
            "loss_count": loss_count,
            "flat_count": flat_count,
            "win_rate_pct": round(win_count / sample_size * 100, 2) if sample_size else None,
            "average_return_pct": round(sum(returns) / sample_size, 6) if sample_size else None,
            "directional_hit_rate_pct": round(directional_matches / directional_total * 100, 2) if directional_total else None,
        }
    return {"read_only": True, "by_horizon": by_horizon}


def _validation_metrics(row: dict[str, Any]) -> dict[str, Any]:
    measurements = row.get("measurements") if isinstance(row.get("measurements"), dict) else {}
    aggregate = measurements.get("aggregate") if isinstance(measurements.get("aggregate"), dict) else {}
    def pick(key: str, default: Any = None) -> Any:
        return aggregate.get(key, measurements.get(key, row.get(key, default)))
    return {
        "signal_quality": pick("signal_quality"),
        "market_regime": pick("market_regime", "unknown"),
        "direction_score": pick("direction_score"),
        "timeframe": pick("timeframe", "unknown"),
        "confidence": row.get("confidence", pick("confidence")),
        "data_quality": pick("data_quality"),
        "direction": aggregate.get("market_direction", row.get("market_direction")),
    }


def _bucket_label(value: Any, thresholds: tuple[float, float], labels: tuple[str, str, str]) -> str:
    if not isinstance(value, (int, float)):
        return "unknown"
    return labels[0] if value >= thresholds[0] else labels[1] if value >= thresholds[1] else labels[2]


def build_validation_depth_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build read-only breakdowns and replay diagnostics from persisted review outcomes."""
    dimension_names = ("signal_quality", "market_regime", "direction_score", "timeframe", "confidence", "reliability")
    dimensions: dict[str, dict[str, dict[str, Any]]] = {name: {} for name in dimension_names}
    horizon_report: dict[str, dict[str, Any]] = {
        horizon: {"sample_size": 0, "pending_count": 0, "data_gap_count": 0, "average_return_pct": None, "directional_error_count": 0, "conflict_count": 0}
        for horizon in HORIZON_HOURS
    }
    replay_by_horizon: dict[str, dict[str, Any]] = {
        horizon: {"sample_size": 0, "pending_count": 0, "data_gap_count": 0, "average_return_pct": None}
        for horizon in HORIZON_HOURS
    }
    replay_returns: dict[str, list[float]] = {horizon: [] for horizon in HORIZON_HOURS}

    def add_dimension(name: str, label: str, row: dict[str, Any]) -> None:
        bucket = dimensions[name].setdefault(label, {"count": 0, "ready_count_1h": 0, "average_return_pct_1h": None, "directional_accuracy_pct_1h": None, "_returns": [], "_matches": 0, "_total": 0})
        bucket["count"] += 1
        outcome = row.get("outcomes", {}).get("1h", {})
        if outcome.get("status") == "ready" and isinstance(outcome.get("return_pct"), (int, float)):
            value = float(outcome["return_pct"])
            bucket["ready_count_1h"] += 1
            bucket["_returns"].append(value)
            direction = _direction_sign(_validation_metrics(row)["direction"])
            if direction and value:
                bucket["_total"] += 1
                bucket["_matches"] += int(direction == (1 if value > 0 else -1))

    for row in rows:
        metrics = _validation_metrics(row)
        add_dimension("signal_quality", _bucket_label(metrics["signal_quality"], (70, 40), ("high", "medium", "low")), row)
        add_dimension("market_regime", str(metrics["market_regime"]), row)
        score = metrics["direction_score"]
        score_label = "unknown" if not isinstance(score, (int, float)) else "positive_strong" if score >= 50 else "positive_weak" if score > 0 else "negative_strong" if score <= -50 else "negative_weak" if score < 0 else "neutral"
        add_dimension("direction_score", score_label, row)
        add_dimension("timeframe", str(metrics["timeframe"]), row)
        add_dimension("confidence", _bucket_label(metrics["confidence"], (0.75, 0.5), ("high", "medium", "low")), row)
        add_dimension("reliability", _bucket_label(metrics["data_quality"], (80, 60), ("high", "medium", "low")), row)
        predicted = _direction_sign(metrics["direction"])
        for horizon, diagnostic in horizon_report.items():
            outcome = row.get("outcomes", {}).get(horizon, {})
            value = outcome.get("return_pct") if isinstance(outcome, dict) else None
            if outcome.get("status") != "ready" or not isinstance(value, (int, float)):
                if outcome.get("status") == "data_gap":
                    diagnostic["data_gap_count"] += 1
                else:
                    diagnostic["pending_count"] += 1
                if outcome.get("status") == "data_gap":
                    replay_by_horizon[horizon]["data_gap_count"] += 1
                else:
                    replay_by_horizon[horizon]["pending_count"] += 1
                continue
            value = float(value)
            diagnostic["sample_size"] += 1
            replay_by_horizon[horizon]["sample_size"] += 1
            replay_returns[horizon].append(value)
            if predicted and value:
                diagnostic["directional_error_count"] += int(predicted != (1 if value > 0 else -1))
            aggregate_direction = _direction_sign(metrics["direction"])
            event_direction = _direction_sign(row.get("market_direction"))
            if aggregate_direction and event_direction and aggregate_direction != event_direction:
                diagnostic["conflict_count"] += 1
    for buckets in dimensions.values():
        for bucket in buckets.values():
            values = bucket.pop("_returns")
            bucket["average_return_pct_1h"] = round(sum(values) / len(values), 6) if values else None
            total = bucket.pop("_total")
            matches = bucket.pop("_matches")
            bucket["directional_accuracy_pct_1h"] = round(matches / total * 100, 2) if total else None
    for horizon, diagnostic in horizon_report.items():
        values = replay_returns[horizon]
        diagnostic["average_return_pct"] = round(sum(values) / len(values), 6) if values else None
        replay_by_horizon[horizon]["average_return_pct"] = diagnostic["average_return_pct"]
    return {
        "read_only": True,
        "historical_replay": {"event_count": len(rows), "by_horizon": replay_by_horizon},
        "by_dimension": dimensions,
        "by_horizon": horizon_report,
    }


def build_validation_policy_report(depth_report: dict[str, Any], minimum_sample_size: int = 5) -> dict[str, Any]:
    """Translate validation evidence into conservative, read-only analyst actions."""
    by_horizon = depth_report.get("by_horizon", {})
    one_hour = by_horizon.get("1h", {})
    ready_sample = int(one_hour.get("sample_size", 0) or 0)
    event_count = int(depth_report.get("historical_replay", {}).get("event_count", 0) or 0)
    dimension_actions: list[dict[str, Any]] = []
    for dimension, buckets in depth_report.get("by_dimension", {}).items():
        for bucket, values in buckets.items():
            count = int(values.get("count", 0) or 0)
            ready = int(values.get("ready_count_1h", 0) or 0)
            accuracy = values.get("directional_accuracy_pct_1h")
            average = values.get("average_return_pct_1h")
            if ready < minimum_sample_size:
                continue
            if bucket == "unknown" or (accuracy is None and average is None):
                dimension_actions.append({"dimension": dimension, "bucket": bucket, "count": count, "ready_count_1h": ready, "action": "Недостаточно данных dimension", "reason": "События не содержат dimension metadata; качество сигнала по этому срезу не оценивается."})
            elif (isinstance(accuracy, (int, float)) and accuracy < 50) or (isinstance(average, (int, float)) and average < 0):
                dimension_actions.append({"dimension": dimension, "bucket": bucket, "count": count, "ready_count_1h": ready, "action": "Обязательный manual review", "reason": "Наблюдаемая доходность или точность направления ниже порога."})
            else:
                dimension_actions.append({"dimension": dimension, "bucket": bucket, "count": count, "ready_count_1h": ready, "action": "Наблюдать", "reason": "Недостаточно оснований для автоматического изменения confidence."})
    if ready_sample == 0:
        status = "collecting"
        recommendation = "Накопить forward outcomes до оценки стратегии."
        actions = ["Не менять confidence автоматически", "Проверить готовность outcome worker"]
    elif ready_sample < minimum_sample_size:
        status = "insufficient_sample"
        recommendation = "Выборка ещё мала для изменения policy."
        actions = ["Продолжить сбор данных", "Не менять confidence автоматически"]
    elif any(item["action"] == "Обязательный manual review" for item in dimension_actions):
        status = "degraded"
        recommendation = "Есть dimension buckets с отрицательным или неточным поведением."
        actions = ["Усилить manual review для слабых buckets", "Сохранить остальные сигналы в режиме наблюдения"]
    else:
        status = "monitor"
        recommendation = "Выборка достаточна для наблюдения, но не для execution."
        actions = ["Продолжить мониторинг", "Не включать execution"]
    return {"read_only": True, "status": status, "recommendation": recommendation, "event_count": event_count, "ready_sample_size_1h": ready_sample, "minimum_sample_size": minimum_sample_size, "actions": actions, "dimension_actions": dimension_actions}
