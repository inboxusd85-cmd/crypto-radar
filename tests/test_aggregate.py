from crypto_radar.aggregate import aggregate_signals
from crypto_radar.models import Signal
import pytest


def signal(severity="low", basis="basis", timeframe=None, signal_type="test"):
    measurements = {"timeframe": timeframe} if timeframe else {}
    return Signal(
        asset="BTC", signal_type=signal_type, fact="fact", basis=basis,
        source_urls=["https://example.com"], severity=severity, confidence=0.7,
        measurements=measurements,
    )


def test_aggregate_uses_highest_grade_and_lists_factors():
    result = aggregate_signals([signal("low", "funding is 0.00001"), signal("high", "spread is 50 bps"), signal("medium")])
    assert result.severity == "high"
    assert result.signal_type == "composite_market_risk"
    assert "3 факторов" in result.basis
    assert "spread is 50 bps" in result.basis
    assert result.auto_trade is False
    assert result.measurements["factor_signature"] == "test=low; test=high; test=medium"


def test_aggregate_exposes_prioritized_drivers_and_combines_multiple_material_factors():
    result = aggregate_signals([
        signal("medium", "funding"),
        signal("medium", "spread"),
        signal("low", "turnover"),
    ])

    assert result.severity == "high"
    assert [driver["basis"] for driver in result.measurements["drivers"]] == ["funding", "spread", "turnover"]
    assert result.measurements["drivers"][0]["priority"] == 1
    assert result.measurements["drivers"][0]["role"] == "ключевой драйвер"
    assert result.measurements["severity_counts"] == {"low": 1, "medium": 2, "high": 0}


def test_aggregate_uses_higher_timeframe_as_general_signal_priority():
    result = aggregate_signals([
        signal("medium", "1m factor", "1m"),
        signal("medium", "1d factor", "1d"),
        signal("low", "1w context", "1w"),
    ])

    drivers = result.measurements["drivers"]
    assert [driver["timeframe"] for driver in drivers] == ["1d", "1m", "1w"]
    assert [driver["priority_points"] for driver in drivers] == [50, 10, 60]
    assert result.measurements["timeframe_weights"] == {"1m": 10, "1d": 50, "1w": 60}


def test_aggregate_preserves_observation_timestamp():
    result = aggregate_signals([signal()], observed_at="2026-07-20T12:00:00Z")
    assert result.observed_at == "2026-07-20T12:00:00Z"


def test_aggregate_classifies_driver_evidence_sources():
    result = aggregate_signals([
        signal("medium", "funding", signal_type="funding_rate"),
        signal("low", "indicators", signal_type="multi_timeframe_consensus"),
        signal("low", "claim", signal_type="social_claim"),
    ])

    assert [driver["signal_class"] for driver in result.measurements["drivers"]] == ["market", "technical", "social"]


def test_aggregate_exposes_evidence_class_summary():
    result = aggregate_signals([
        signal("medium", "funding", "1h", signal_type="funding_rate"),
        signal("low", "indicators", "1d", signal_type="multi_timeframe_consensus"),
        signal("low", "claim", signal_type="social_claim"),
    ])

    assert result.measurements["evidence_class_summary"] == {
        "market": {"count": 1, "priority_points": 30},
        "technical": {"count": 1, "priority_points": 50},
        "social": {"count": 1, "priority_points": 0},
    }


def test_aggregate_preserves_technical_forecast_measurements() -> None:
    technical = signal("medium", "технический", "1h", signal_type="multi_timeframe_consensus")
    technical.signal_type = "multi_timeframe_consensus"
    technical.measurements.update({
        "indicator_scores": {"demark": {"лонг": 30, "шорт": 0}, "rei": {"лонг": 30, "шорт": 0}},
        "demark_context": {"oversold_timeframes": ["1h"], "overbought_timeframes": [], "exhaustion_events": {"buy_setup": ["1h"], "sell_setup": []}},
        "horizons": {"tactical": {"direction": "лонг"}},
    })
    result = aggregate_signals([technical])
    assert result.measurements["technical_forecast"]["indicator_scores"]["demark"]["лонг"] == 30
    assert result.measurements["technical_forecast"]["demark_context"]["oversold_timeframes"] == ["1h"]


def test_empty_aggregate_is_rejected():
    with pytest.raises(ValueError):
        aggregate_signals([])
