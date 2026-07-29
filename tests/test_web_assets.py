from pathlib import Path

from fastapi.testclient import TestClient

from crypto_radar.events import AlertEventJournal
from crypto_radar.models import Signal
from crypto_radar.providers.hyperliquid import MarketSnapshot
from crypto_radar.rss import RssArticle
from crypto_radar.rss_store import RssArticleStore
from crypto_radar.web.app import create_app


class FakeProvider:
    def fetch(self, assets: set[str]) -> list[MarketSnapshot]:
        return [
            MarketSnapshot("BTC", 65_000.0, 64_990.0, 0.00035, 40_000.0, 2_000_000_000.0)
            for asset in assets
            if asset == "BTC"
        ]


def test_asset_endpoint_returns_current_metrics_signals_and_events(tmp_path: Path) -> None:
    history_path = tmp_path / "history.sqlite3"
    AlertEventJournal(history_path).record(
        Signal("BTC", "composite_market_risk", "fact", "basis", ["https://example.com"], observed_at="2026-07-21T10:00:00Z"),
        recorded_at=10.0,
    )
    client = TestClient(create_app(history_path=history_path, provider=FakeProvider()))

    response = client.get("/api/v1/assets/btc")

    assert response.status_code == 200
    payload = response.json()
    assert payload["asset"]["asset"] == "BTC"
    assert payload["signals"][0]["asset"] == "BTC"
    assert payload["events"][0]["asset"] == "BTC"


def test_asset_endpoint_returns_404_for_unavailable_asset(tmp_path: Path) -> None:
    client = TestClient(create_app(history_path=tmp_path / "history.sqlite3", provider=FakeProvider()))

    response = client.get("/api/v1/assets/NOPE")

    assert response.status_code == 404
    assert response.json() == {"detail": "Asset not found"}


def test_asset_news_returns_latest_three_with_explainable_score(tmp_path: Path) -> None:
    history_path = tmp_path / "history.sqlite3"
    store = RssArticleStore(history_path)
    for index in range(4):
        store.upsert(RssArticle(
            source_name="Test Feed", source_url="https://example.com/feed", article_id=f"id-{index}",
            title=f"BTC update {index}", url=f"https://example.com/{index}",
            published_at=f"2026-07-2{index}T10:00:00+00:00", summary="The market is under pressure as investors reduce risk and liquidity falls.", assets=("BTC",),
            source_tier="secondary", fetched_at="2026-07-23T10:00:00+00:00", ranking_features=(9.0, 8.0, 0.2, 3.0, 0.7),
        ))
    client = TestClient(create_app(history_path=history_path, provider=FakeProvider()))

    response = client.get("/api/v1/assets/btc/news")

    assert response.status_code == 200
    payload = response.json()
    assert payload["asset"] == "BTC"
    assert payload["count"] == 3
    assert payload["news"][0]["score"] == {"score": -2, "label": "негативно", "basis": "негативная оценка: найдено маркеров 2; позитивных маркеров: 0. Итоговая оценка: -2/10. Числовые данные: 3."}
    assert "The market is under pressure" not in payload["news"][0]["summary_ru"]
    assert "рынок" in payload["news"][0]["summary_ru"].lower()
    assert "ликвидност" in payload["news"][0]["summary_ru"].lower()
    assert payload["news"][0]["ranking"] == {
        "production_model": "rules-v1",
        "shadow_model": "xgboost-news-v1",
        "features": [9.0, 8.0, 0.2, 3.0, 0.7],
    }


def test_asset_news_dataset_preserves_signed_score_boundaries(tmp_path: Path) -> None:
    history_path = tmp_path / "history.sqlite3"
    store = RssArticleStore(history_path)
    for index, summary in enumerate(("Hack exploit outage lawsuit bankruptcy attack risk fraud", "Routine update", "Partnership adoption growth success record inflow launch approval funding integration surge breakout rally")):
        store.upsert(RssArticle(
            source_name="Test Feed", source_url="https://example.com/feed", article_id=f"boundary-{index}",
            title=f"BTC boundary {index}", url=f"https://example.com/boundary-{index}",
            published_at=f"2026-07-2{index}T10:00:00+00:00", summary=summary, assets=("BTC",),
            source_tier="primary", fetched_at="2026-07-23T10:00:00+00:00", ranking_features=(float(index), 0.0, 1.0, 1.0, 1.0),
        ))
    client = TestClient(create_app(history_path=history_path, provider=FakeProvider()))

    response = client.get("/api/v1/assets/btc/news/dataset?limit=3")

    assert response.status_code == 200
    assert sorted(record["production_score"] for record in response.json()["records"]) == [-10, 0, 10]


def test_asset_news_dataset_export_is_read_only_and_unlabeled(tmp_path: Path) -> None:
    history_path = tmp_path / "history.sqlite3"
    store = RssArticleStore(history_path)
    store.upsert(RssArticle(
        source_name="Test Feed", source_url="https://example.com/feed", article_id="id-1",
        title="BTC adoption growth", url="https://example.com/1",
        published_at="2026-07-23T10:00:00+00:00", summary="Partnership growth", assets=("BTC",),
        source_tier="primary", fetched_at="2026-07-23T10:00:00+00:00",
        ranking_features=(2.0, 0.0, 0.9, 1.0, 1.0),
        event_type="partnership_adoption",
        ))
    client = TestClient(create_app(history_path=history_path, provider=FakeProvider()))

    response = client.get("/api/v1/assets/btc/news/dataset")

    assert response.status_code == 200
    assert response.json() == {
        "asset": "BTC",
        "count": 1,
        "label_status": "unlabeled",
        "read_only": True,
        "readiness": {
            "1h": {"ready_count": 0, "pending_count": 1, "data_gap_count": 0, "coverage_pct": 0.0},
            "6h": {"ready_count": 0, "pending_count": 1, "data_gap_count": 0, "coverage_pct": 0.0},
            "1d": {"ready_count": 0, "pending_count": 1, "data_gap_count": 0, "coverage_pct": 0.0},
            "1w": {"ready_count": 0, "pending_count": 1, "data_gap_count": 0, "coverage_pct": 0.0},
        },
        "event_type_breakdown": {
            "partnership_adoption": {
                "count": 1,
                "sample_status": "insufficient_sample",
                "score_distribution": {"positive": 1, "neutral": 0, "negative": 0},
                "by_horizon": {
                    horizon: {"ready_count": 0, "pending_count": 1, "data_gap_count": 0, "coverage_pct": 0.0, "average_return_pct": None, "quality_status": "insufficient_sample", "positive_rate_pct": None, "negative_rate_pct": None, "flat_rate_pct": None, "directional_accuracy_pct": None, "directional_sample_count": None, "directional_accuracy_ci95_pct": None}
                    for horizon in ("1h", "6h", "1d", "1w")
                },
            },
        },
        "training_readiness": {
            "min_samples": 100,
            "min_coverage_pct": 80.0,
            "horizons": {
                "1h": {"status": "blocked", "ready_count": 0, "coverage_pct": 0.0, "reasons": ["insufficient_samples", "insufficient_coverage"]},
                "6h": {"status": "blocked", "ready_count": 0, "coverage_pct": 0.0, "reasons": ["insufficient_samples", "insufficient_coverage"]},
                "1d": {"status": "blocked", "ready_count": 0, "coverage_pct": 0.0, "reasons": ["insufficient_samples", "insufficient_coverage"]},
                "1w": {"status": "blocked", "ready_count": 0, "coverage_pct": 0.0, "reasons": ["insufficient_samples", "insufficient_coverage"]},
            },
        },
        "training_preparation": {
            "1h": {"status": "blocked", "horizon": "1h", "ready_count": 0, "coverage_pct": 0.0, "reasons": ["insufficient_samples", "insufficient_coverage"]},
            "6h": {"status": "blocked", "horizon": "6h", "ready_count": 0, "coverage_pct": 0.0, "reasons": ["insufficient_samples", "insufficient_coverage"]},
            "1d": {"status": "blocked", "horizon": "1d", "ready_count": 0, "coverage_pct": 0.0, "reasons": ["insufficient_samples", "insufficient_coverage"]},
            "1w": {"status": "blocked", "horizon": "1w", "ready_count": 0, "coverage_pct": 0.0, "reasons": ["insufficient_samples", "insufficient_coverage"]},
        },
        "records": [{
            "article_id": "id-1",
            "published_at": "2026-07-23T10:00:00+00:00",
            "features": [2.0, 0.0, 0.9, 1.0, 1.0],
            "event_type": "partnership_adoption",
            "production_model": "rules-v1",
            "production_score": 4,
            "shadow_model": "xgboost-news-v1",
            "label": None,
            "outcomes": {
                "entry": {"status": "pending", "reason": "missing_entry_candle"},
                "outcomes": {
                    "1h": {"status": "pending", "reason": "missing_entry_candle"},
                    "6h": {"status": "pending", "reason": "missing_entry_candle"},
                    "1d": {"status": "pending", "reason": "missing_entry_candle"},
                    "1w": {"status": "pending", "reason": "missing_entry_candle"},
                },
            },
        }],
    }
