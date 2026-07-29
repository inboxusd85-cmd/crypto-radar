from crypto_radar.social_signals import social_candidate_to_signal


def candidate():
    return {
        "asset": "HYPE",
        "claim_type": "risk",
        "severity": "medium",
        "confidence": 0.72,
        "freshness": 0.625,
        "freshness_weighted_confidence": 0.57,
        "source_quality": 0.2,
        "quality_weighted_confidence": 0.513,
        "independent_authors": 2,
        "evidence_count": 2,
        "evidence": [
            {"url": "https://x.com/a/1", "author_handle": "alice", "text": "HYPE risk", "created_at": "2026-07-20T12:00:00Z"},
            {"url": "https://x.com/b/2", "author_handle": "bob", "text": "HYPE risk", "created_at": "2026-07-20T12:01:00Z"},
        ],
        "requires_manual_review": True,
    }


def test_social_candidate_converts_to_standard_signal():
    signal = social_candidate_to_signal(candidate(), observed_at="2026-07-20T12:02:00Z")
    assert signal.asset == "HYPE"
    assert signal.signal_type == "social_claim"
    assert signal.signal_class == "social"
    assert signal.severity == "medium"
    assert signal.confidence == 0.513
    assert signal.source_urls == ["https://x.com/a/1", "https://x.com/b/2"]
    assert signal.requires_manual_review is True
    assert signal.auto_trade is False
    assert signal.measurements["factor_signature"] == "risk"
    assert signal.measurements["raw_confidence"] == 0.72
    assert signal.measurements["freshness"] == 0.625


def test_social_signal_id_is_stable_when_evidence_grows():
    first = social_candidate_to_signal(candidate(), observed_at="2026-07-20T12:00:00Z")
    expanded = candidate()
    expanded["evidence"].append({"url": "https://x.com/c/3", "author_handle": "carol", "text": "HYPE risk", "created_at": "2026-07-20T12:03:00Z"})
    expanded["evidence_count"] = 3
    expanded["independent_authors"] = 3
    expanded["severity"] = "high"
    second = social_candidate_to_signal(expanded, observed_at="2026-07-20T12:04:00Z")
    assert first.signal_id != second.signal_id
    assert first.observed_at != second.observed_at
