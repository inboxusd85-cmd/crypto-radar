from datetime import datetime, timezone

from crypto_radar.social_aggregation import aggregate_social_analyses
from crypto_radar.social_signals import social_candidate_to_signal
from crypto_radar.source_reputation import SourceReputationStore


def test_signal_preserves_reputation_provenance(tmp_path):
    store = SourceReputationStore(tmp_path / "reputation.sqlite3")
    store.record_outcome("alice", "confirmed", reference="https://claim/1", note="matched")
    candidate = aggregate_social_analyses(
        [{
            "platform": "x", "post_id": "1", "source_url": "https://x.com/alice/1",
            "author_handle": "alice", "text": "HYPE risk", "created_at": "2026-07-20T12:00:00Z",
            "assets": ["HYPE"], "claim_type": "risk", "confidence": 0.8,
            "source_quality": 1.0,
        }],
        now=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        reputation_store=store,
    )[0]
    signal = social_candidate_to_signal(candidate, observed_at="2026-07-20T12:01:00Z")
    assert signal.measurements["reputation"] == candidate["reputation"]
    assert signal.measurements["effective_quality"] == candidate["effective_quality"]
    assert signal.measurements["reputation_evidence_count"] == 1
    assert signal.measurements["reputation_reviewed_authors"] == 1
