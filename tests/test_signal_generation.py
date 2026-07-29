from crypto_radar.providers.hyperliquid import MarketSnapshot
from crypto_radar.signal_generation import generate_funding_signal


def snapshot(funding_rate: float) -> MarketSnapshot:
    return MarketSnapshot(
        asset="BTC",
        mark_price=65000.0,
        mid_price=64990.0,
        funding_rate=funding_rate,
        open_interest=40000.0,
        day_notional_volume=2_000_000_000.0,
    )


def test_normal_funding_is_low_with_explicit_basis():
    signal = generate_funding_signal(snapshot(0.00001))
    assert signal.severity == "low"
    assert signal.auto_trade is False
    assert "финансирован" in signal.basis.lower()


def test_elevated_funding_is_medium():
    signal = generate_funding_signal(snapshot(0.00035))
    assert signal.severity == "medium"
    assert signal.confidence >= 0.7
    assert signal.requires_manual_review is True


def test_extreme_funding_is_high():
    signal = generate_funding_signal(snapshot(-0.001))
    assert signal.severity == "high"
    assert "отрицатель" in signal.basis.lower()


def test_funding_uses_history_when_provided():
    signal = generate_funding_signal(
        snapshot(0.0002),
        funding_history=[0.00001, 0.000011, 0.000009, 0.00001, 0.000012],
    )
    assert signal.severity == "high"
    assert "историческое среднее" in signal.basis.lower()
    assert "z_score" in signal.measurements
