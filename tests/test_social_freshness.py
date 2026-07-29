from datetime import datetime, timezone

from crypto_radar.social_aggregation import aggregate_social_analyses, freshness_weight


def analysis(post_id, author, created_at, confidence=0.8):
    return {
        "platform": "x", "post_id": post_id, "source_url": f"https://x.com/{author}/status/{post_id}",
        "author_handle": author, "text": "HYPE exploit risk", "created_at": created_at,
        "assets": ["HYPE"], "claim_type": "risk", "confidence": confidence, "requires_manual_review": True,
    }


def test_freshness_weight_is_one_now_and_decays_with_age():
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    assert freshness_weight("2026-07-20T12:00:00Z", now=now, half_life_hours=24) == 1.0
    old = freshness_weight("2026-07-18T12:00:00Z", now=now, half_life_hours=24)
    assert 0.24 < old < 0.26


def test_aggregation_exposes_freshness_and_uses_it_in_confidence():
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    result = aggregate_social_analyses(
        [analysis("1", "alice", "2026-07-20T12:00:00Z"), analysis("2", "bob", "2026-07-18T12:00:00Z")],
        now=now,
        half_life_hours=24,
    )[0]
    assert result["freshness"] < 1.0
    assert 0.62 < result["freshness"] < 0.63
    assert result["freshness_weighted_confidence"] < result["confidence"]
