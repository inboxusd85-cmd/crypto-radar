import json

from crypto_radar.models import Signal
from crypto_radar.serialization import signal_to_dict, signals_to_json


def make_signal(severity="medium"):
    return Signal(
        asset="BTC", signal_type="test", fact="Observed fact", basis="Measured basis",
        source_urls=["https://example.com"], severity=severity, confidence=0.8,
        possible_explanations=["Alternative"], measurements={"z_score": 2.5},
    )


def test_signal_to_dict_preserves_explanation_contract():
    payload = signal_to_dict(make_signal())
    assert payload["asset"] == "BTC"
    assert payload["basis"] == "Measured basis"
    assert payload["auto_trade"] is False
    assert payload["measurements"]["z_score"] == 2.5


def test_signals_to_json_is_valid_json_array():
    payload = json.loads(signals_to_json([make_signal("low"), make_signal("high")]))
    assert [item["severity"] for item in payload] == ["low", "high"]
