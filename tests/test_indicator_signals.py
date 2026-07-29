from crypto_radar.indicator_signals import generate_indicator_signal


def test_indicator_signal_contains_timeframe_and_explainable_measurements() -> None:
    closes = [100 + index * 0.8 + (index % 3) * 0.2 for index in range(40)]
    highs = [close + 1.0 + (index % 4) * 0.1 for index, close in enumerate(closes)]
    lows = [close - 1.0 - (index % 2) * 0.1 for index, close in enumerate(closes)]

    volumes = [100.0 + index for index in range(40)]
    signal = generate_indicator_signal("BTC", "1m", highs, lows, closes, volumes)

    assert signal.signal_type == "multi_timeframe_indicators"
    assert signal.market_direction in {"лонг", "шорт", "нейтральное"}
    assert signal.measurements["timeframe"] == "1m"
    assert signal.measurements["demark_direction"] in {"лонг", "шорт", "нейтральное"}
    assert signal.measurements["demark_zone"] in {"oversold", "neutral", "overbought"}
    assert signal.measurements["demark_exhaustion"] in {"buy_setup", "sell_setup", "none"}
    assert -100.0 <= signal.measurements["rei"] <= 100.0
    assert signal.measurements["rei_regime"] in {"oversold", "neutral", "overbought"}
    assert signal.measurements["rei_direction"] in {"лонг", "шорт", "нейтральное"}
    assert signal.measurements["td_structure"]["lookahead_safe"] is True
    assert "td_demand_line" in signal.measurements["td_structure"]
    assert "td_supply_line" in signal.measurements["td_structure"]
    assert signal.measurements["td_retracement"]["retracement_zone"] == "unavailable"
    assert signal.measurements["td_retracement"]["retracement_382"] is None
    assert signal.measurements["td_retracement"]["retracement_618"] is None
    assert signal.measurements["td_retracement"]["lookahead_safe"] is True
    assert signal.measurements["td_scenario"]["qualified"] is False
    assert signal.measurements["td_scenario"]["auto_trade"] is False
    assert 0.0 <= signal.measurements["demark"] <= 1.0
    assert not {"aroon_direction", "trend_strength", "aroon_up", "aroon_down", "adx"}.intersection(signal.measurements)
    assert signal.measurements["volume_regime"] in {"пониженный", "обычный", "повышенный"}
    assert signal.measurements["volume_ratio"] > 0
    assert "ADX" not in signal.basis
    assert signal.measurements["td_sequential"]["signal_state"] in {"setup", "countdown", "completed", "neutral"}
    assert "TD Sequential (книга DeMark, Setup→Intersection→Countdown)" in signal.basis
    assert signal.auto_trade is False
    assert signal.measurements["indicator_weights"] == {"demark": 2, "rei": 1, "volume": 1, "td_sequential": 2}

