from crypto_radar.models import Signal
from crypto_radar.serialization import signal_to_dict


def test_signal_has_stable_id_and_observation_timestamp():
    first = Signal(
        asset="HYPE", signal_type="composite_market_risk", fact="fact", basis="basis",
        source_urls=[], observed_at="2026-07-20T12:00:00Z",
    )
    second = Signal(
        asset="HYPE", signal_type="composite_market_risk", fact="fact", basis="basis",
        source_urls=[], observed_at="2026-07-20T12:00:01Z",
    )
    assert first.observed_at == "2026-07-20T12:00:00Z"
    assert first.signal_id == second.signal_id
    payload = signal_to_dict(first)
    assert payload["observed_at"] == first.observed_at
    assert payload["signal_id"] == first.signal_id


def test_signal_id_changes_when_explanation_changes():
    base = dict(asset="HYPE", signal_type="composite_market_risk", fact="fact", source_urls=[])
    assert Signal(**base, basis="basis-a").signal_id != Signal(**base, basis="basis-b").signal_id


def test_composite_signal_id_ignores_live_numeric_basis_details():
    common = dict(
        asset="HYPE", signal_type="composite_market_risk", fact="fact", source_urls=[],
        measurements={"factor_signature": "funding_rate=low; turnover=high"},
    )
    first = Signal(**common, basis="mark price 61.88, turnover 0.18x", severity="high")
    second = Signal(**common, basis="mark price 61.91, turnover 0.19x", severity="high")
    assert first.signal_id == second.signal_id
