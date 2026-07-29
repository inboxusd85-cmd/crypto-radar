from crypto_radar.models import Signal
from crypto_radar.quality_gate import passes_signal_quality_gate, validate_signal


def make_signal(**changes):
    payload = {
        "asset": "HYPE", "signal_type": "social_claim", "fact": "Risk claim",
        "basis": "raw=0.7; weighted=0.5", "source_urls": ["https://x.com/a/1"],
        "severity": "medium", "confidence": 0.5, "requires_manual_review": True,
        "auto_trade": False,
        "measurements": {
            "confidence_model": "social-quality-v1",
            "confidence_components": {"raw": 0.7},
            "evidence_count": 1,
        },
        "observed_at": "2026-07-20T12:00:00Z",
    }
    payload.update(changes)
    return Signal(**payload)


def test_quality_gate_accepts_explainable_social_signal():
    signal = make_signal()
    assert validate_signal(signal) == []
    assert passes_signal_quality_gate(signal)


def test_quality_gate_reports_missing_provenance_and_sources():
    signal = make_signal(source_urls=[], measurements={"evidence_count": 1})
    issues = validate_signal(signal)
    assert "source_urls are required" in issues
    assert "confidence_model is required" in issues
    assert "confidence_components are required" in issues


def test_quality_gate_does_not_reject_low_confidence_manual_review_signal():
    signal = make_signal(confidence=0.05)
    assert passes_signal_quality_gate(signal)
