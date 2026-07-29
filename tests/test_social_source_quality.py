from datetime import datetime, timezone

from crypto_radar.social_aggregation import aggregate_social_analyses


def analysis(post_id, author, quality):
    return {
        "platform": "x", "post_id": post_id, "source_url": f"https://x.com/{author}/status/{post_id}",
        "author_handle": author, "text": "HYPE exploit risk", "created_at": "2026-07-20T12:00:00Z",
        "assets": ["HYPE"], "claim_type": "risk", "confidence": 0.8,
        "source_quality": quality, "requires_manual_review": True,
    }


def test_aggregation_preserves_source_quality_per_evidence():
    result = aggregate_social_analyses(
        [analysis("1", "official", 1.0), analysis("2", "unknown", 0.2)],
        now=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
    )[0]
    evidence = {item["author_handle"]: item for item in result["evidence"]}
    assert evidence["official"]["source_quality"] == 1.0
    assert evidence["unknown"]["source_quality"] == 0.2


def test_low_quality_evidence_reduces_quality_weighted_confidence():
    high = aggregate_social_analyses(
        [analysis("1", "official", 1.0), analysis("2", "analyst", 1.0)],
        now=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
    )[0]
    low = aggregate_social_analyses(
        [analysis("1", "official", 0.2), analysis("2", "analyst", 0.2)],
        now=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
    )[0]
    assert high["source_quality"] == 1.0
    assert low["source_quality"] == 0.2
    assert low["quality_weighted_confidence"] < high["quality_weighted_confidence"]
