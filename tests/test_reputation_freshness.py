from datetime import datetime, timezone

from crypto_radar.source_reputation import reputation_decay, decayed_reputation


def test_reputation_decay_is_one_at_review_time_and_halves_after_half_life():
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    assert reputation_decay("2026-07-20T12:00:00Z", now=now, half_life_hours=24) == 1.0
    value = reputation_decay("2026-07-19T12:00:00Z", now=now, half_life_hours=24)
    assert 0.49 < value < 0.51


def test_decayed_reputation_returns_to_neutral_prior():
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    fresh = decayed_reputation(0.8, "2026-07-20T12:00:00Z", now=now, half_life_hours=24)
    old = decayed_reputation(0.8, "2026-07-18T12:00:00Z", now=now, half_life_hours=24)
    assert fresh == 0.8
    assert 0.57 < old < 0.58
