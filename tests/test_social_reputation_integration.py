from datetime import datetime, timezone

from crypto_radar.social_aggregation import aggregate_social_analyses
from crypto_radar.source_reputation import SourceReputationStore


def analysis(post_id, author, quality=1.0):
    return {
        "platform": "x", "post_id": post_id, "source_url": f"https://x.com/{author}/status/{post_id}",
        "author_handle": author, "text": "HYPE exploit risk", "created_at": "2026-07-20T12:00:00Z",
        "assets": ["HYPE"], "claim_type": "risk", "confidence": 0.8,
        "source_quality": quality, "requires_manual_review": True,
    }


def test_reputation_score_is_combined_with_ingestion_quality(tmp_path):
    store = SourceReputationStore(tmp_path / "reputation.sqlite3")
    store.record_outcome("trusted", "confirmed")
    store.record_outcome("noisy", "refuted")
    result = aggregate_social_analyses(
        [analysis("1", "trusted"), analysis("2", "noisy")],
        now=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        reputation_store=store,
    )[0]
    evidence = {item["author_handle"]: item for item in result["evidence"]}
    assert evidence["trusted"]["reputation_score"] > 0.5
    assert evidence["noisy"]["reputation_score"] < 0.5
    assert result["reputation"] == 0.5
    assert result["effective_quality"] == 0.75
    assert result["quality_weighted_confidence"] < result["freshness_weighted_confidence"]
