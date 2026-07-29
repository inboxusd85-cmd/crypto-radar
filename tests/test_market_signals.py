from crypto_radar.providers.hyperliquid import MarketSnapshot
from crypto_radar.market_signals import generate_basis_signals


def make(mark=100.0, mid=99.99, oi=100.0, volume=1_000_000.0):
    return MarketSnapshot("BTC", mark, mid, 0.00001, oi, volume)


def test_mark_mid_spread_is_low_when_tight():
    signals = generate_basis_signals(make())
    spread = next(s for s in signals if s.signal_type == "mark_mid_spread")
    assert spread.severity == "low"
    assert "спред" in spread.basis.lower()


def test_mark_mid_spread_is_high_when_wide():
    signals = generate_basis_signals(make(mark=100.0, mid=99.5))
    spread = next(s for s in signals if s.signal_type == "mark_mid_spread")
    assert spread.severity == "high"
    assert spread.measurements["spread_bps"] > 40


def test_open_interest_turnover_signal_contains_basis():
    signals = generate_basis_signals(make(oi=30_000, volume=1_000_000))
    oi_signal = next(s for s in signals if s.signal_type == "open_interest_turnover")
    assert oi_signal.basis
    assert oi_signal.auto_trade is False
    assert oi_signal.measurements["open_interest_notional"] == 3_000_000


def test_component_signals_use_asset_specific_history():
    signals = generate_basis_signals(
        make(mark=100.0, mid=99.98, oi=100.0, volume=1_000_000.0),
        spread_history=[1.0, 1.1, 0.9, 1.0, 1.05],
        turnover_history=[2.0, 2.1, 1.9, 2.0, 2.05],
    )
    spread = next(s for s in signals if s.signal_type == "mark_mid_spread")
    turnover = next(s for s in signals if s.signal_type == "open_interest_turnover")
    assert "историческое среднее" in spread.basis.lower()
    assert "историческое среднее" in turnover.basis.lower()
    assert "z_score" in spread.measurements
    assert "z_score" in turnover.measurements
