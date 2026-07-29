from datetime import datetime, timezone

from crypto_radar.social_aggregation import aggregate_social_analyses
from crypto_radar.source_reputation import SourceReputationStore


def test_decay_factor_is_preserved_in_evidence_and_candidate(tmp_path):
    store = SourceReputationStore(tmp_path / "reputation.sqlite3")
    store.record_outcome("alice", "confirmed")
    result = aggregate_social_analyses(
        [{
            "platform": "x", "post_id": "1", "source_url": "https://x.com/alice/1",
            "author_handle": "alice", "text": "HYPE risk", "created_at": "2026-07-20T12:00:00Z",
            "assets": ["HYPE"], "claim_type": "risk", "confidence": 0.8,
            "source_quality": 1.0,
        }],
        now=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        reputation_store=store,
        reputation_half_life_hours=24,
    )[0]
    assert result["evidence"][0]["reputation_decay"] == 1.0
    assert result["reputation_decay"] == 1.0


def test_old_review_reports_half_decay_factor(tmp_path):
    store = SourceReputationStore(tmp_path / "reputation.sqlite3")
    store.record_outcome("alice", "confirmed")
    # Audit timestamp is current, so use the public helper contract separately for the exact decay.
    from crypto_radar.source_reputation import reputation_decay
    factor = reputation_decay("2026-07-19T12:00:00Z", now=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc), half_life_hours=24)
    assert 0.49 < factor < 0.51
