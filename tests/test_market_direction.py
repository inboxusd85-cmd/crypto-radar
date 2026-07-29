from crypto_radar.aggregate import aggregate_signals
from crypto_radar.providers.hyperliquid import MarketSnapshot
from crypto_radar.price_signals import generate_price_change_signal
from crypto_radar.signal_generation import generate_funding_signal


def snapshot(funding_rate: float = 0.00035, mark_price: float = 105.0) -> MarketSnapshot:
    return MarketSnapshot("BTC", mark_price, mark_price, funding_rate, 100.0, 1_000_000.0)


def test_funding_signal_has_russian_description_and_direction() -> None:
    signal = generate_funding_signal(snapshot(0.00035))

    assert "Funding" not in signal.fact
    assert "финансирован" in signal.fact.lower()
    assert signal.market_direction == "снижение"


def test_price_signal_has_russian_direction_conclusion() -> None:
    signal = generate_price_change_signal(snapshot(mark_price=120.0), 100.0)

    assert "цена" in signal.fact.lower()
    assert signal.market_direction == "рост"


def test_composite_contains_market_direction_conclusion() -> None:
    funding = generate_funding_signal(snapshot(0.00035))
    price = generate_price_change_signal(snapshot(mark_price=120.0), 100.0)
    composite = aggregate_signals([funding, price], observed_at="2026-01-01T00:00:00Z")

    assert composite.market_direction == "нейтральное"
    assert "Направление рынка" in composite.basis
    assert "ручной проверки" in composite.basis.lower()


def test_composite_ignores_neutral_factors_when_direction_agrees() -> None:
    funding = generate_funding_signal(snapshot(0.00035))
    price = generate_price_change_signal(snapshot(mark_price=95.0), 100.0)
    composite = aggregate_signals([funding, price], observed_at="2026-01-01T00:00:00Z")

    assert composite.market_direction == "снижение"
