from crypto_radar.social_signals import social_candidate_to_signal


def test_signal_contains_versioned_confidence_model_components():
    candidate = {
        "asset": "HYPE", "claim_type": "risk", "severity": "medium",
        "confidence": 0.7, "freshness": 0.8, "source_quality": 1.0,
        "reputation": 0.575, "reputation_decay": 0.25,
        "effective_quality": 0.7875, "freshness_weighted_confidence": 0.56,
        "quality_weighted_confidence": 0.5, "independent_authors": 1,
        "evidence_count": 1, "evidence": [],
    }
    signal = social_candidate_to_signal(candidate, observed_at="2026-07-20T12:00:00Z")
    measurements = signal.measurements
    assert measurements["confidence_model"] == "social-quality-v1"
    assert measurements["confidence_components"] == {
        "raw": 0.7,
        "freshness": 0.8,
        "freshness_weighted": 0.56,
        "source_quality": 1.0,
        "reputation": 0.575,
        "reputation_decay": 0.25,
        "effective_quality": 0.7875,
        "weighted": 0.5,
    }
