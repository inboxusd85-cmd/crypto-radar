from crypto_radar.alerts import render_markdown
from crypto_radar.providers.hyperliquid import MarketSnapshot
from crypto_radar.signal_generation import generate_funding_signal


def test_markdown_alert_exposes_grade_basis_and_no_trading():
    signal = generate_funding_signal(MarketSnapshot("BTC", 65000, 64990, 0.00035, 40000, 2e9))
    text = render_markdown(signal)
    assert "MEDIUM" in text
    assert "Основание" in text
    assert "funding" in text.lower()
    assert "Автоторговля: нет" in text
    assert "Ручная проверка: да" in text
