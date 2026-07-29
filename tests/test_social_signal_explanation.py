from crypto_radar.social_signals import social_candidate_to_signal


def test_signal_basis_explains_stale_reputation():
    candidate = {
        "asset": "HYPE", "claim_type": "risk", "severity": "medium", "confidence": 0.7,
        "freshness": 0.8, "source_quality": 1.0, "reputation": 0.575,
        "reputation_decay": 0.25, "effective_quality": 0.7875,
        "reputation_evidence_count": 1, "reputation_reviewed_authors": 1,
        "reputation_last_reviewed_at": "2026-07-18T12:00:00Z",
        "freshness_weighted_confidence": 0.56, "quality_weighted_confidence": 0.5,
        "independent_authors": 1, "evidence_count": 1, "evidence": [],
    }
    signal = social_candidate_to_signal(candidate, observed_at="2026-07-20T12:00:00Z")
    assert "raw=0.7" in signal.basis
    assert "freshness=0.8" in signal.basis
    assert "source_quality=1" in signal.basis
    assert "reputation=0.575" in signal.basis
    assert "weighted=0.5" in signal.basis
    assert "reputation_decay=0.25" in signal.basis
    assert "last_reviewed=2026-07-18T12:00:00Z" in signal.basis
