from pathlib import Path
import json
import sqlite3

import pytest

from fastapi.testclient import TestClient

from crypto_radar.candle_history import CandleHistory
from crypto_radar.providers.hyperliquid import Candle
from crypto_radar.outcome_worker import run_once
from crypto_radar.web.app import create_app
from crypto_radar.outcomes import OutcomeReviewStore, OutcomeStore, build_news_training_plan, calculate_forward_outcomes, calculate_news_outcomes, materialize_event_outcomes, prepare_news_training_dataset, split_news_dataset, summarize_news_event_types, summarize_news_training_readiness




def test_event_type_summary_preserves_count_and_horizon_denominators() -> None:
    records = [
        {"event_type": "general", "production_score": 4, "outcomes": {"outcomes": {"1h": {"status": "ready", "return_pct": 1.0}, "6h": {"status": "pending"}}}},
        {"event_type": "general", "production_score": -4, "outcomes": {"outcomes": {"1h": {"status": "data_gap"}, "6h": {"status": "ready", "return_pct": -1.0}}}},
        {"event_type": "regulatory", "production_score": 0, "outcomes": {"outcomes": {"1h": {"status": "pending"}, "6h": {"status": "pending"}}}},
    ]

    result = summarize_news_event_types(records)

    assert sum(bucket["count"] for bucket in result.values()) == len(records)
    assert sum(result["general"]["score_distribution"].values()) == result["general"]["count"]
    for bucket in result.values():
        for horizon in ("1h", "6h", "1d", "1w"):
            item = bucket["by_horizon"][horizon]
            assert item["ready_count"] + item["pending_count"] + item["data_gap_count"] == bucket["count"]
            if item["directional_sample_count"] is not None:
                assert item["directional_sample_count"] <= item["ready_count"]
    records = [
        {"event_type": "regulatory", "outcomes": {"outcomes": {"1h": {"status": "ready", "return_pct": 2.0}, "6h": {"status": "pending"}}}},
        {"event_type": "regulatory", "outcomes": {"outcomes": {"1h": {"status": "pending"}, "6h": {"status": "data_gap"}}}},
        {"event_type": "general", "outcomes": {"outcomes": {"1h": {"status": "ready", "return_pct": -1.0}}}},
    ]
    result = summarize_news_event_types(records)
    assert result["regulatory"]["count"] == 2
    assert result["regulatory"]["by_horizon"]["1h"] == {"ready_count": 1, "pending_count": 1, "data_gap_count": 0, "coverage_pct": 50.0, "average_return_pct": 2.0, "quality_status": "insufficient_sample", "positive_rate_pct": None, "negative_rate_pct": None, "flat_rate_pct": None, "directional_accuracy_pct": None, "directional_sample_count": None, "directional_accuracy_ci95_pct": None}
    assert result["regulatory"]["by_horizon"]["6h"]["pending_count"] == 1
    assert result["regulatory"]["by_horizon"]["6h"]["data_gap_count"] == 1
    assert result["regulatory"]["by_horizon"]["1h"]["quality_status"] == "insufficient_sample"
    assert result["regulatory"]["sample_status"] == "insufficient_sample"
    assert result["regulatory"]["score_distribution"] == {"positive": 0, "neutral": 2, "negative": 0}






def test_event_type_quality_contract_is_complete_for_every_horizon() -> None:
    records = [
        {"event_type": "general", "production_score": 4, "outcomes": {"outcomes": {horizon: {"status": "ready", "return_pct": 1.0} for horizon in ("1h", "6h", "1d", "1w")}}},
    ]
    result = summarize_news_event_types(records)
    required = {"ready_count", "pending_count", "data_gap_count", "coverage_pct", "average_return_pct", "quality_status", "positive_rate_pct", "negative_rate_pct", "flat_rate_pct", "directional_accuracy_pct", "directional_sample_count", "directional_accuracy_ci95_pct"}
    for bucket in result.values():
        for horizon in ("1h", "6h", "1d", "1w"):
            item = bucket["by_horizon"][horizon]
            assert required <= item.keys()
            assert item["quality_status"] == "insufficient_sample"
            assert item["directional_accuracy_pct"] is None
            assert item["directional_sample_count"] is None
            assert item["directional_accuracy_ci95_pct"] is None


def test_event_type_quality_metrics_are_null_below_ready_sample_gate() -> None:
    records = [{"event_type": "regulatory", "production_score": 4, "outcomes": {"outcomes": {"1h": {"status": "ready", "return_pct": 2.0}}}}]
    bucket = summarize_news_event_types(records)["regulatory"]["by_horizon"]["1h"]
    assert bucket["quality_status"] == "insufficient_sample"
    assert bucket["positive_rate_pct"] is None
    assert bucket["directional_accuracy_pct"] is None
    assert bucket["directional_sample_count"] is None
    assert bucket["directional_accuracy_ci95_pct"] is None


def test_event_type_quality_metrics_reach_review_candidate_at_100_ready_outcomes() -> None:
    records = []
    for index in range(100):
        score = 0 if index < 2 else 4
        return_pct = 0.0 if 2 <= index < 5 else (1.0 if index < 95 else -1.0)
        records.append({"event_type": "general", "production_score": score, "outcomes": {"outcomes": {"1h": {"status": "ready", "return_pct": return_pct}}}})

    bucket = summarize_news_event_types(records)["general"]["by_horizon"]["1h"]

    assert bucket["quality_status"] == "review_candidate"
    assert bucket["positive_rate_pct"] == 92.0
    assert bucket["negative_rate_pct"] == 5.0
    assert bucket["flat_rate_pct"] == 3.0
    assert bucket["directional_sample_count"] == 95
    assert bucket["directional_accuracy_pct"] == 94.74
    assert bucket["directional_accuracy_ci95_pct"] == [88.26, 97.73]




@pytest.mark.parametrize(("ready_count", "expected_status"), [(9, "insufficient_sample"), (10, "collecting"), (99, "collecting"), (100, "review_candidate")])
def test_event_type_quality_status_thresholds_are_exact(ready_count: int, expected_status: str) -> None:
    records = [
        {"event_type": "general", "production_score": 4, "outcomes": {"outcomes": {"1h": {"status": "ready", "return_pct": 1.0}}}}
        for _ in range(ready_count)
    ]

    bucket = summarize_news_event_types(records)["general"]["by_horizon"]["1h"]

    assert bucket["ready_count"] == ready_count
    assert bucket["quality_status"] == expected_status


def test_event_type_quality_metrics_calculate_once_ready_sample_is_collecting() -> None:
    records = [
        {"event_type": "regulatory", "production_score": 4 if index < 6 else -4, "outcomes": {"outcomes": {"1h": {"status": "ready", "return_pct": 2.0 if index < 8 else -1.0}}}}
        for index in range(10)
    ]
    bucket = summarize_news_event_types(records)["regulatory"]["by_horizon"]["1h"]
    assert bucket["quality_status"] == "collecting"
    assert bucket["positive_rate_pct"] == 80.0
    assert bucket["negative_rate_pct"] == 20.0
    assert bucket["flat_rate_pct"] == 0.0
    assert bucket["directional_accuracy_pct"] == 80.0
    assert bucket["directional_sample_count"] == 10
    assert bucket["directional_accuracy_ci95_pct"] == [49.02, 94.33]
    readiness = {"1h": {"ready_count": 99, "coverage_pct": 99.0}}
    result = build_news_training_plan(readiness, "1h")
    assert result == {"status": "blocked", "horizon": "1h", "ready_count": 99, "coverage_pct": 99.0, "reasons": ["insufficient_samples"]}
def test_prepare_news_training_dataset_blocks_or_returns_time_split() -> None:
    records = [
        {"article_id": "early", "published_at": "2026-01-01T00:00:00Z", "outcomes": {"1h": {"status": "ready", "return_pct": 1.0}}},
        {"article_id": "late", "published_at": "2026-01-02T00:00:00Z", "outcomes": {"1h": {"status": "ready", "return_pct": -1.0}}},
    ]

    blocked = prepare_news_training_dataset(records, "1h", min_samples=3)
    assert blocked["status"] == "blocked"
    assert blocked["reasons"] == ["insufficient_samples"]

    ready = prepare_news_training_dataset(records, "1h", min_samples=2, min_coverage_pct=100.0)
    assert ready["status"] == "ready"
    assert [row["article_id"] for row in ready["split"]["train"]] == ["early"]
    assert [row["article_id"] for row in ready["split"]["validation"]] == ["late"]


def test_news_dataset_split_is_time_ordered_and_excludes_unready_records() -> None:
    records = [
        {"article_id": "late", "published_at": "2026-01-05T00:00:00Z", "outcomes": {"1h": {"status": "ready", "return_pct": 1.0}}},
        {"article_id": "pending", "published_at": "2026-01-02T00:00:00Z", "outcomes": {"1h": {"status": "pending"}}},
        {"article_id": "early", "published_at": "2026-01-01T00:00:00Z", "outcomes": {"1h": {"status": "ready", "return_pct": -1.0}}},
        {"article_id": "mid", "published_at": "2026-01-03T00:00:00Z", "outcomes": {"1h": {"status": "ready", "return_pct": 0.5}}},
        {"article_id": "other", "published_at": "2026-01-04T00:00:00Z", "outcomes": {"6h": {"status": "ready", "return_pct": 2.0}}},
    ]

    result = split_news_dataset(records, "1h", validation_fraction=1 / 3)

    assert [row["article_id"] for row in result["train"]] == ["early", "mid"]
    assert [row["article_id"] for row in result["validation"]] == ["late"]
    assert result["eligible_count"] == 3


def test_news_dataset_split_rejects_invalid_fraction_and_keeps_empty_sets_empty() -> None:
    assert split_news_dataset([], "1h") == {"train": [], "validation": [], "eligible_count": 0, "excluded_count": 0}
    with pytest.raises(ValueError, match="validation_fraction"):
        split_news_dataset([], "1h", validation_fraction=1.0)


def test_forward_outcomes_use_first_close_at_or_after_horizon(tmp_path: Path) -> None:
    history = CandleHistory(tmp_path / "history.sqlite3")
    candles = [
        Candle("BTC", "1h", 1_700_000_000_000, 100, 101, 99, 100, 10),
        Candle("BTC", "1h", 1_700_003_600_000, 100, 103, 99, 102, 10),
        Candle("BTC", "1h", 1_700_007_200_000, 102, 104, 100, 103, 10),
        Candle("BTC", "1h", 1_700_010_800_000, 103, 104, 100, 101, 10),
    ]
    history.upsert_many(candles)

    result = calculate_forward_outcomes(history, "BTC", "1h", 1_700_000_000_000, 100.0)

    assert result["1h"] == {"status": "ready", "close": 102.0, "return_pct": 2.0}
    assert result["6h"]["status"] == "pending"


def test_news_outcomes_use_publication_candle_as_entry(tmp_path: Path) -> None:
    history = CandleHistory(tmp_path / "history.sqlite3")
    history.upsert_many([
        Candle("BTC", "1h", 1_700_000_000_000, 100, 101, 99, 100, 10),
        Candle("BTC", "1h", 1_700_003_600_000, 100, 103, 99, 103, 10),
    ])

    result = calculate_news_outcomes(history, "BTC", "1h", "2023-11-14T22:13:20Z")

    assert result["entry"] == {"status": "ready", "price": 100.0, "open_time": 1_700_000_000_000}
    assert result["outcomes"]["1h"] == {"status": "ready", "close": 103.0, "return_pct": 3.0}
    assert result["outcomes"]["6h"]["status"] == "pending"


def test_forward_outcomes_mark_candle_far_past_target_as_data_gap(tmp_path: Path) -> None:
    history = CandleHistory(tmp_path / "history.sqlite3")
    history.upsert_many([Candle("BTC", "1h", 1_700_010_800_000, 100, 103, 99, 102, 10)])

    result = calculate_forward_outcomes(history, "BTC", "1h", 1_700_000_000_000, 100.0)

    assert result["1h"] == {"status": "pending", "reason": "data_gap"}


def test_outcome_store_materializes_and_does_not_overwrite_ready(tmp_path: Path) -> None:
    history = CandleHistory(tmp_path / "history.sqlite3")
    history.upsert_many([
        Candle("BTC", "1h", 1_700_000_000_000, 100, 101, 99, 100, 10),
        Candle("BTC", "1h", 1_700_003_600_000, 100, 103, 99, 102, 10),
    ])
    store = OutcomeStore(tmp_path / "history.sqlite3")
    event = {"event_id": "event-1", "asset": "BTC", "observed_at": "2023-11-14T22:13:20Z", "measurements": {"entry_price": 100.0}}

    first = materialize_event_outcomes(event, history, store)
    assert first["1h"] == {"status": "ready", "close": 102.0, "return_pct": 2.0}

    history.upsert_many([Candle("BTC", "1h", 1_700_003_600_000, 100, 103, 99, 110, 10)])
    second = materialize_event_outcomes(event, history, store)
    assert second["1h"] == first["1h"]


def test_materializer_uses_signal_timeframe_for_forward_outcomes(tmp_path: Path) -> None:
    history = CandleHistory(tmp_path / "history.sqlite3")
    history.upsert_many([
        Candle("BTC", "1h", 1_700_000_000_000, 100, 101, 99, 100, 10),
        Candle("BTC", "1h", 1_700_003_600_000, 100, 101, 99, 101, 10),
        Candle("BTC", "6h", 1_700_000_000_000, 100, 101, 99, 100, 10),
        Candle("BTC", "6h", 1_700_021_600_000, 100, 104, 99, 103, 10),
    ])
    store = OutcomeStore(tmp_path / "history.sqlite3")
    event = {
        "event_id": "event-6h",
        "asset": "BTC",
        "observed_at": "2023-11-14T22:13:20Z",
        "measurements": {"entry_price": 100.0, "timeframe": "6h"},
    }

    result = materialize_event_outcomes(event, history, store)

    assert result["1h"]["status"] == "pending"
    assert result["1h"]["reason"] == "data_gap"
    assert result["6h"] == {"status": "ready", "close": 103.0, "return_pct": 3.0}


def test_materializer_explains_missing_entry_price(tmp_path: Path) -> None:
    history = CandleHistory(tmp_path / "history.sqlite3")
    store = OutcomeStore(tmp_path / "history.sqlite3")
    event = {"event_id": "event-2", "asset": "BTC", "observed_at": "2023-11-14T22:13:20Z", "measurements": {}}

    result = materialize_event_outcomes(event, history, store)

    assert result["1h"] == {"status": "pending", "reason": "missing_entry_price"}


def test_outcome_worker_materializes_batch_and_records_last_run(tmp_path: Path) -> None:
    db = tmp_path / "history.sqlite3"
    stats = run_once(db, events=[{"event_id": "worker-event", "asset": "BTC", "observed_at": "2023-11-14T22:13:20Z", "measurements": {}}])

    assert stats["attempted"] == 1
    assert stats["pending"] == 4
    assert stats["errors"] == 0

    second = run_once(db, events=[])
    assert second["attempted"] == 0


def test_review_store_is_idempotent_and_preserves_note(tmp_path: Path) -> None:
    store = OutcomeReviewStore(tmp_path / "history.sqlite3")

    first = store.review("event-1", "confirmed", "Подтверждено ценой", reviewed_at=1_700_000_000.0)
    second = store.review("event-1", "refuted", "Изменился контекст", reviewed_at=1_700_001_000.0)

    assert first["status"] == "confirmed"
    assert second == {"event_id": "event-1", "status": "refuted", "note": "Изменился контекст", "reviewed_at": 1_700_001_000.0}


def test_health_exposes_outcome_worker_state(tmp_path: Path) -> None:
    app = create_app(history_path=tmp_path / "history.sqlite3")
    client = TestClient(app)

    assert client.get("/api/v1/health").json()["outcomes"]["worker"] is None
    run_once(tmp_path / "history.sqlite3", events=[])
    state = client.get("/api/v1/health").json()["outcomes"]["worker"]
    assert state["attempted"] == 0
    assert "completed_at" in state
    assert state["status"] == "ok"


def test_health_exposes_social_pipeline_boundary(tmp_path: Path) -> None:
    social = TestClient(create_app(history_path=tmp_path / "history.sqlite3")).get("/api/v1/health").json()["social"]

    assert social == {
        "enabled": False,
        "status": "available_on_demand",
        "mode": "separate_pipeline",
        "entrypoint": "social-run",
        "included_in_market_composite": False,
        "requires_manual_review": True,
    }


def test_health_normalizes_legacy_worker_state_without_status(tmp_path: Path) -> None:
    db = tmp_path / "history.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE outcome_worker_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO outcome_worker_state(key, value) VALUES ('last_run', ?)",
            (json.dumps({"attempted": 1, "ready": 0, "pending": 0, "errors": 2, "completed_at": 1_700_000_000.0}),),
        )

    state = TestClient(create_app(history_path=db)).get("/api/v1/health").json()["outcomes"]["worker"]

    assert state["status"] == "error"
    assert state["errors"] == 2


def test_health_marks_old_worker_state_as_stale(tmp_path: Path) -> None:
    db = tmp_path / "history.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE outcome_worker_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO outcome_worker_state(key, value) VALUES ('last_run', ?)",
            (json.dumps({"attempted": 1, "ready": 1, "pending": 0, "errors": 0, "completed_at": 1_700_000_000.0}),),
        )

    state = TestClient(create_app(history_path=db)).get("/api/v1/health").json()["outcomes"]["worker"]

    assert state["status"] == "stale"
    assert state["stale"] is True
    assert state["age_seconds"] > 900


def test_review_api_lists_queue_and_updates_status(tmp_path: Path) -> None:
    app = create_app(history_path=tmp_path / "history.sqlite3")
    client = TestClient(app)

    response = client.get("/api/v1/reviews?status=pending")

    assert response.status_code == 200
    assert response.json() == {"reviews": [], "count": 0}

    response = client.put("/api/v1/reviews/event-1", json={"status": "confirmed", "note": "Проверено"})

    assert response.status_code == 404
