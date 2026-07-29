import pytest
from crypto_radar.models import Signal


def test_signal_defaults_to_manual_review_and_no_auto_trade():
    signal = Signal(
        asset="BTC",
        signal_type="volume_anomaly",
        fact="Volume is elevated",
        basis="Volume is 4.2 standard deviations above the baseline.",
        source_urls=["https://example.com/source"],
    )
    assert signal.requires_manual_review is True
    assert signal.auto_trade is False
    assert signal.basis.startswith("Volume is")


def test_signal_requires_basis():
    with pytest.raises(ValueError, match="basis"):
        Signal(
            asset="BTC",
            signal_type="volume_anomaly",
            fact="Volume is elevated",
            basis="",
            source_urls=[],
        )


def test_signal_cannot_enable_auto_trade():
    with pytest.raises(ValueError, match="auto_trade"):
        Signal(
            asset="ETH",
            signal_type="price_anomaly",
            fact="x",
            basis="Price is outside the historical range.",
            source_urls=[],
            auto_trade=True,
        )


def test_social_claim_id_ignores_dynamic_confidence_details():
    base = dict(
        asset="HYPE",
        signal_type="social_claim",
        fact="Social evidence indicates exploit claim for HYPE",
        source_urls=["https://example.com/source"],
        severity="medium",
        measurements={"factor_signature": "exploit"},
    )
    first = Signal(**base, basis="weighted=0.4; freshness=1.0")
    second = Signal(**base, basis="weighted=0.8; freshness=0.5")

    assert first.signal_id == second.signal_id


def test_social_claim_id_changes_for_different_claim_types():
    common = dict(
        asset="HYPE",
        signal_type="social_claim",
        fact="Social evidence",
        basis="same dynamic details",
        source_urls=["https://example.com/source"],
    )

    assert Signal(**common, measurements={"factor_signature": "exploit"}).signal_id != Signal(
        **common, measurements={"factor_signature": "listing"}
    ).signal_id


def test_signal_class_and_evidence_metadata_are_normalized():
    market = Signal(
        asset="BTC",
        signal_type="funding_rate",
        fact="Funding is elevated",
        basis="Funding exceeded its baseline.",
        source_urls=["https://example.com/source"],
        confidence=0.8,
    )
    social = Signal(
        asset="BTC",
        signal_type="social_claim",
        fact="A social claim was observed",
        basis="Claim requires verification.",
        source_urls=["https://example.com/post"],
        confidence=0.5,
    )

    assert market.signal_class == "market"
    assert social.signal_class == "social"
    assert market.evidence_metadata == {
        "source_count": 1,
        "has_sources": True,
        "confidence": 0.8,
        "requires_manual_review": True,
    }
