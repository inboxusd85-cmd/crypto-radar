from pathlib import Path

from fastapi.testclient import TestClient

from crypto_radar.outcomes import build_time_split_report, build_validation_depth_report, build_validation_policy_report, build_validation_report, summarize_quality
from crypto_radar.web.app import create_app


def test_time_split_report_uses_chronological_train_test_and_keeps_pending_visible() -> None:
    rows = [
        {"observed_at": "2026-01-01T00:00:00Z", "market_direction": "рост", "outcomes": {"1h": {"status": "ready", "return_pct": 1.0}}},
        {"observed_at": "2026-01-02T00:00:00Z", "market_direction": "снижение", "outcomes": {"1h": {"status": "ready", "return_pct": -1.0}}},
        {"observed_at": "2026-01-03T00:00:00Z", "market_direction": "рост", "outcomes": {"1h": {"status": "pending"}}},
        {"observed_at": "2026-01-04T00:00:00Z", "market_direction": "рост", "outcomes": {"1h": {"status": "ready", "return_pct": 2.0}}},
        {"observed_at": "2026-01-05T00:00:00Z", "market_direction": "снижение", "outcomes": {"1h": {"status": "ready", "return_pct": -2.0}}},
    ]
    report = build_time_split_report(rows, train_fraction=0.6)
    assert report["read_only"] is True
    assert report["status"] == "exploratory"
    assert report["train"]["event_count"] == 3
    assert report["train"]["by_horizon"]["1h"]["sample_size"] == 2
    assert report["train"]["by_horizon"]["1h"]["pending_count"] == 1
    assert report["test"]["event_count"] == 2
    assert report["test"]["by_horizon"]["1h"]["sample_size"] == 2
    assert report["test"]["by_horizon"]["1h"]["average_return_pct"] == 0.0
    assert report["dataset_gate"] == {
        "min_samples": 100,
        "min_coverage_pct": 80.0,
        "train_1h": {"status": "blocked", "sample_size": 2, "coverage_pct": 66.67, "reasons": ["insufficient_samples", "insufficient_coverage"]},
        "test_1h": {"status": "blocked", "sample_size": 2, "coverage_pct": 100.0, "reasons": ["insufficient_samples"]},
        "train_6h": {"status": "blocked", "sample_size": 0, "coverage_pct": 0.0, "reasons": ["insufficient_samples", "insufficient_coverage"]},
        "test_6h": {"status": "blocked", "sample_size": 0, "coverage_pct": 0.0, "reasons": ["insufficient_samples", "insufficient_coverage"]},
        "train_1d": {"status": "blocked", "sample_size": 0, "coverage_pct": 0.0, "reasons": ["insufficient_samples", "insufficient_coverage"]},
        "test_1d": {"status": "blocked", "sample_size": 0, "coverage_pct": 0.0, "reasons": ["insufficient_samples", "insufficient_coverage"]},
        "train_1w": {"status": "blocked", "sample_size": 0, "coverage_pct": 0.0, "reasons": ["insufficient_samples", "insufficient_coverage"]},
        "test_1w": {"status": "blocked", "sample_size": 0, "coverage_pct": 0.0, "reasons": ["insufficient_samples", "insufficient_coverage"]},
    }



def test_time_split_report_summarizes_all_forward_horizons() -> None:
    rows = [
        {
            "observed_at": "2026-01-01T00:00:00Z",
            "market_direction": "рост",
            "outcomes": {
                "1h": {"status": "ready", "return_pct": 1.0},
                "6h": {"status": "ready", "return_pct": 2.0},
                "1d": {"status": "pending"},
                "1w": {"status": "data_gap"},
            },
        },
        {
            "observed_at": "2026-01-02T00:00:00Z",
            "market_direction": "снижение",
            "outcomes": {
                "1h": {"status": "ready", "return_pct": -1.0},
                "6h": {"status": "pending"},
                "1d": {"status": "ready", "return_pct": 3.0},
                "1w": {"status": "ready", "return_pct": -4.0},
            },
        },
    ]
    report = build_time_split_report(rows, train_fraction=0.5)
    for part in (report["train"], report["test"]):
        assert set(part["by_horizon"]) == {"1h", "6h", "1d", "1w"}
    assert report["train"]["by_horizon"]["6h"]["sample_size"] == 1
    assert report["test"]["by_horizon"]["6h"]["pending_count"] == 1
    assert report["train"]["by_horizon"]["1w"]["data_gap_count"] == 1
    assert set(report["dataset_gate"]) >= {"train_1h", "test_1h", "train_6h", "test_6h", "train_1d", "test_1d", "train_1w", "test_1w"}


def test_quality_summary_separates_pending_and_ready_outcomes() -> None:
    rows = [
        {
            "asset": "BTC",
            "severity": "high",
            "market_direction": "рост",
            "review": {"status": "confirmed"},
            "outcomes": {"1h": {"status": "ready", "return_pct": 2.0}},
        },
        {
            "asset": "ETH",
            "severity": "low",
            "market_direction": "снижение",
            "review": {"status": "refuted"},
            "outcomes": {"1h": {"status": "ready", "return_pct": 1.0}},
        },
        {
            "asset": "SOL",
            "severity": "medium",
            "market_direction": "рост",
            "review": {"status": "deferred"},
            "outcomes": {"1h": {"status": "pending"}},
        },
    ]

    assert summarize_quality(rows) == {
        "reviewed_count": 3,
        "ready_count_1h": 2,
        "coverage_pct_1h": 66.67,
        "average_return_pct_1h": 1.5,
        "directional_accuracy_pct_1h": 50.0,
        "by_severity": {
            "high": {"count": 1, "ready_count_1h": 1, "average_return_pct_1h": 2.0},
            "low": {"count": 1, "ready_count_1h": 1, "average_return_pct_1h": 1.0},
            "medium": {"count": 1, "ready_count_1h": 0, "average_return_pct_1h": None},
        },
        "by_status": {
            "confirmed": {"count": 1, "ready_count_1h": 1, "average_return_pct_1h": 2.0},
            "deferred": {"count": 1, "ready_count_1h": 0, "average_return_pct_1h": None},
            "refuted": {"count": 1, "ready_count_1h": 1, "average_return_pct_1h": 1.0},
        },
        "by_horizon": {
            "1h": {"ready_count": 2, "coverage_pct": 66.67, "average_return_pct": 1.5, "directional_accuracy_pct": 50.0},
            "6h": {"ready_count": 0, "coverage_pct": 0.0, "average_return_pct": None, "directional_accuracy_pct": None},
            "1d": {"ready_count": 0, "coverage_pct": 0.0, "average_return_pct": None, "directional_accuracy_pct": None},
            "1w": {"ready_count": 0, "coverage_pct": 0.0, "average_return_pct": None, "directional_accuracy_pct": None},
        },
    }



def test_fundamental_snapshot_keeps_news_and_github_provenance(tmp_path, monkeypatch) -> None:
    from crypto_radar.web.app import create_app
    from fastapi.testclient import TestClient
    import sqlite3
    import json

    db = tmp_path / "history.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE github_events (repo TEXT, kind TEXT, external_id TEXT PRIMARY KEY, occurred_at TEXT, title TEXT, url TEXT, value TEXT, recorded_at TEXT)")
        connection.execute("INSERT INTO github_events VALUES ('bitcoin/bitcoin','release','r1','2026-07-28T11:00:00Z','New release','https://github/r','{}','2026-07-28T11:01:00Z')")
    from crypto_radar.rss import RssArticle
    from crypto_radar.rss_store import RssArticleStore
    RssArticleStore(db).upsert(RssArticle(source_name="Feed", source_url="https://feed", article_id="a1", title="Bitcoin ETF inflows", url="https://example/a", published_at="2026-07-28T10:00:00Z", summary="institutional inflow", assets=("BTC",), source_tier="primary", fetched_at="2026-07-28T10:00:00Z", event_type="funding_institutional"))
    monkeypatch.setenv("GITHUB_WATCH_REPOS", "bitcoin/bitcoin")
    response = TestClient(create_app(history_path=db)).get("/api/v1/assets/BTC/fundamental")
    assert response.status_code == 200
    payload = response.json()
    assert payload["read_only"] is True
    assert payload["asset"] == "BTC"
    assert payload["news"]["count"] == 1
    assert payload["news"]["items"][0]["provenance"] == "rss"
    assert payload["github"]["mapped_repos"] == ["bitcoin/bitcoin"]
    assert payload["github"]["events"][0]["provenance"] == "github_watch"
    assert payload["production_impact"] == "none"
    assert payload["synthesis"]["status"] in {"confirmed", "emerging", "conflicting", "insufficient"}
    assert payload["synthesis"]["production_impact"] == "none"


def test_synthesize_fundamental_evidence_distinguishes_conflict_and_insufficient() -> None:
    from crypto_radar.fundamental import synthesize_fundamental_evidence

    conflicting = synthesize_fundamental_evidence(
        [
            {"event_type": "funding_institutional", "score": {"score": 4}, "title": "ETF inflows"},
            {"event_type": "security_incident", "score": {"score": -4}, "title": "Exploit"},
        ],
        [{"kind": "release", "title": "New release"}],
    )
    assert conflicting["status"] == "conflicting"
    assert conflicting["production_impact"] == "none"
    assert {item["source"] for item in conflicting["evidence"]} == {"news", "github"}

    insufficient = synthesize_fundamental_evidence([], [])
    assert insufficient["status"] == "insufficient"
    assert insufficient["evidence"] == []


def test_validation_time_split_endpoint_is_read_only(tmp_path: Path) -> None:
    response = TestClient(create_app(history_path=tmp_path / "history.sqlite3")).get("/api/v1/reviews/validation/time-split")
    assert response.status_code == 200
    payload = response.json()
    assert payload["read_only"] is True
    assert payload["status"] == "exploratory"
    assert payload["train"]["event_count"] == 0
    assert payload["test"]["event_count"] == 0

def test_review_summary_endpoint_returns_observable_quality_contract(tmp_path: Path) -> None:
    app = create_app(history_path=tmp_path / "history.sqlite3")

    response = TestClient(app).get("/api/v1/reviews/summary")

    assert response.status_code == 200
    assert response.json() == {
        "reviewed_count": 0,
        "ready_count_1h": 0,
        "coverage_pct_1h": None,
        "average_return_pct_1h": None,
        "directional_accuracy_pct_1h": None,
        "by_severity": {},
        "by_status": {},
        "by_horizon": {
            "1h": {"ready_count": 0, "coverage_pct": None, "average_return_pct": None, "directional_accuracy_pct": None},
            "6h": {"ready_count": 0, "coverage_pct": None, "average_return_pct": None, "directional_accuracy_pct": None},
            "1d": {"ready_count": 0, "coverage_pct": None, "average_return_pct": None, "directional_accuracy_pct": None},
            "1w": {"ready_count": 0, "coverage_pct": None, "average_return_pct": None, "directional_accuracy_pct": None},
        },
    }


def test_validation_report_is_read_only_and_separates_wins_losses_and_pending() -> None:
    rows = [
        {"market_direction": "рост", "outcomes": {"1h": {"status": "ready", "return_pct": 2.0}}},
        {"market_direction": "снижение", "outcomes": {"1h": {"status": "ready", "return_pct": -1.0}}},
        {"market_direction": "рост", "outcomes": {"1h": {"status": "ready", "return_pct": -0.5}}},
        {"market_direction": "лонг", "outcomes": {"1h": {"status": "pending"}}},
    ]
    report = build_validation_report(rows)
    assert report["read_only"] is True
    assert report["by_horizon"]["1h"] == {"sample_size": 3, "pending_count": 1, "win_count": 1, "loss_count": 2, "flat_count": 0, "win_rate_pct": 33.33, "average_return_pct": 0.166667, "directional_hit_rate_pct": 66.67}
    for horizon in ("6h", "1d", "1w"):
        assert report["by_horizon"][horizon] == {"sample_size": 0, "pending_count": 4, "win_count": 0, "loss_count": 0, "flat_count": 0, "win_rate_pct": None, "average_return_pct": None, "directional_hit_rate_pct": None}


def test_validation_endpoint_exposes_read_only_report(tmp_path: Path) -> None:
    response = TestClient(create_app(history_path=tmp_path / "history.sqlite3")).get("/api/v1/reviews/validation")

    assert response.status_code == 200
    assert response.json()["read_only"] is True
    assert set(response.json()["by_horizon"]) == {"1h", "6h", "1d", "1w"}
    assert response.json()["collection"]["read_only"] is True
    assert set(response.json()["collection"]["by_horizon"]) == {"1h", "6h", "1d", "1w"}


def test_validation_depth_endpoint_exposes_breakdowns(tmp_path: Path) -> None:
    response = TestClient(create_app(history_path=tmp_path / "history.sqlite3")).get("/api/v1/reviews/validation/depth")

    assert response.status_code == 200
    payload = response.json()
    assert payload["read_only"] is True
    assert set(payload["by_dimension"]) == {"signal_quality", "market_regime", "direction_score", "timeframe", "confidence", "reliability"}
    assert set(payload["by_horizon"]) == {"1h", "6h", "1d", "1w"}


def test_validation_policy_endpoint_exposes_conservative_status(tmp_path: Path) -> None:
    response = TestClient(create_app(history_path=tmp_path / "history.sqlite3")).get("/api/v1/reviews/validation/policy")
    assert response.status_code == 200
    payload = response.json()
    assert payload["read_only"] is True
    assert payload["status"] == "collecting"
    assert payload["ready_sample_size_1h"] == 0


def test_quality_summary_accepts_aggregate_long_short_direction_vocabulary() -> None:
    rows = [
        {
            "market_direction": "лонг",
            "measurements": {"aggregate": {"market_direction": "лонг", "direction_score": 80}},
            "outcomes": {"1h": {"status": "ready", "return_pct": 2.0}, "6h": {"status": "ready", "return_pct": -1.0}},
        },
        {
            "market_direction": "шорт",
            "measurements": {"aggregate": {"market_direction": "шорт", "direction_score": -70}},
            "outcomes": {"1h": {"status": "ready", "return_pct": -2.0}, "6h": {"status": "ready", "return_pct": -3.0}},
        },
    ]

    summary = summarize_quality(rows)

    assert summary["by_horizon"]["1h"]["directional_accuracy_pct"] == 100.0
    assert summary["by_horizon"]["6h"]["directional_accuracy_pct"] == 50.0


def test_validation_depth_report_breaks_down_quality_and_replay_diagnostics() -> None:
    rows = [
        {
            "event_id": "btc-1", "market_direction": "лонг", "confidence": 0.86,
            "measurements": {"timeframe": "1h", "aggregate": {"signal_quality": 82, "market_regime": "направленный", "direction_score": 75, "data_quality": 91, "market_direction": "лонг"}},
            "outcomes": {"1h": {"status": "ready", "return_pct": 2.0}},
        },
        {
            "event_id": "eth-1", "market_direction": "шорт", "confidence": 0.54,
            "measurements": {"timeframe": "6h", "aggregate": {"signal_quality": 41, "market_regime": "переходный", "direction_score": -35, "data_quality": 62, "market_direction": "шорт"}},
            "outcomes": {"1h": {"status": "ready", "return_pct": 1.0}},
        },
    ]

    report = build_validation_depth_report(rows)

    assert report["read_only"] is True
    assert report["historical_replay"]["event_count"] == 2
    assert report["by_dimension"]["market_regime"]["направленный"]["count"] == 1
    assert report["by_dimension"]["timeframe"]["6h"]["count"] == 1
    assert report["by_dimension"]["confidence"]["high"]["count"] == 1
    assert report["by_dimension"]["direction_score"]["positive_strong"]["count"] == 1
    assert report["by_horizon"]["1h"]["directional_error_count"] == 1
    assert report["by_horizon"]["1h"]["conflict_count"] == 0


def test_validation_depth_report_separates_data_gap_from_pending() -> None:
    report = build_validation_depth_report([
        {"event_id": "gap", "outcomes": {"1h": {"status": "data_gap", "reason": "missing_candle"}}},
        {"event_id": "pending", "outcomes": {"1h": {"status": "pending", "reason": "awaiting_horizon"}}},
    ])

    assert report["by_horizon"]["1h"]["pending_count"] == 1
    assert report["by_horizon"]["1h"]["data_gap_count"] == 1
    assert report["historical_replay"]["by_horizon"]["1h"]["pending_count"] == 1
    assert report["historical_replay"]["by_horizon"]["1h"]["data_gap_count"] == 1


def test_validation_policy_is_collecting_when_no_forward_outcomes_are_ready() -> None:
    report = build_validation_policy_report(build_validation_depth_report([{"event_id": "e1", "outcomes": {"1h": {"status": "pending"}}}]))
    assert report["status"] == "collecting"
    assert report["recommendation"] == "Накопить forward outcomes до оценки стратегии."
    assert report["minimum_sample_size"] == 5


def test_validation_policy_marks_small_sample_as_insufficient() -> None:
    rows = [{"event_id": str(i), "market_direction": "лонг", "outcomes": {"1h": {"status": "ready", "return_pct": 1.0}}} for i in range(3)]
    report = build_validation_policy_report(build_validation_depth_report(rows))
    assert report["status"] == "insufficient_sample"
    assert report["ready_sample_size_1h"] == 3
    assert report["actions"] == ["Продолжить сбор данных", "Не менять confidence автоматически"]


def test_validation_policy_flags_degraded_dimension_after_minimum_sample() -> None:
    rows = [{"event_id": str(i), "confidence": 0.9, "market_direction": "лонг", "measurements": {"aggregate": {"signal_quality": 80}}, "outcomes": {"1h": {"status": "ready", "return_pct": -1.0}}} for i in range(6)]
    report = build_validation_policy_report(build_validation_depth_report(rows))
    assert report["status"] == "degraded"
    assert any(item["dimension"] == "signal_quality" and item["action"] == "Обязательный manual review" for item in report["dimension_actions"])


def test_validation_policy_does_not_treat_unknown_dimension_as_degraded_quality() -> None:
    rows = [{"event_id": str(i), "market_direction": "нейтральное", "outcomes": {"1h": {"status": "ready", "return_pct": 1.0}}} for i in range(6)]
    report = build_validation_policy_report(build_validation_depth_report(rows))
    assert report["status"] == "monitor"
    assert all(item["action"] != "Обязательный manual review" for item in report["dimension_actions"])
    assert all(item["action"] == "Недостаточно данных dimension" for item in report["dimension_actions"])
