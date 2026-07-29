from crypto_radar.price_signals import generate_price_change_signal
from crypto_radar.providers.hyperliquid import MarketSnapshot


def snapshot(price):
    return MarketSnapshot("BTC", price, price, 0.00001, 100.0, 1_000_000.0)


def test_price_change_is_low_without_previous_value():
    signal = generate_price_change_signal(snapshot(105.0), None)
    assert signal.severity == "low"
    assert "insufficient" in signal.basis.lower()


def test_large_price_change_is_high():
    signal = generate_price_change_signal(snapshot(120.0), 100.0)
    assert signal.severity == "high"
    assert signal.measurements["change_percent"] == 20.0
    assert "рост" in signal.fact.lower()
