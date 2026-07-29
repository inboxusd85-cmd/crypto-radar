from crypto_radar.indicator_consensus import generate_indicator_consensus_signal


def observation(timeframe: str, direction: str = "лонг", *, agreement: bool = True, strength: str = "сильный", volume: str = "обычный") -> dict:
    return {
        "timeframe": timeframe,
        "demark_direction": direction,
        "aroon_direction": direction,
        "direction_agreement": agreement,
        "trend_strength": strength,
        "volume_regime": volume,
    }


def test_consensus_preserves_independent_td_scenario_qualification() -> None:
    first = observation("1h")
    first["td_scenario"] = {"scenario": "long", "qualified": True, "reason": "demark_td_buy_setup"}
    second = observation("6h")
    second["td_scenario"] = {"scenario": "none", "qualified": False, "reason": "conditions_not_confirmed"}

    signal = generate_indicator_consensus_signal("BTC", [first, second])

    assert signal is not None
    summary = signal.measurements["td_scenario_summary"]
    assert summary["qualified_timeframes"] == ["1h"]
    assert summary["qualified_scenarios"] == {"long": ["1h"], "short": []}
    assert summary["status"] == "partial"
    assert signal.measurements["indicator_scores"]
    assert "demark_context" in signal.measurements


def test_consensus_requires_agreement_and_two_strong_confirmations_for_medium() -> None:
    signal = generate_indicator_consensus_signal("BTC", [
        observation("1h", volume="повышенный"),
        observation("6h"),
        observation("1d", strength="умеренный"),
    ])

    assert signal is not None
    assert signal.signal_type == "multi_timeframe_consensus"
    assert signal.severity == "low"
    assert signal.confidence == 0.68
    assert signal.market_direction == "лонг"
    assert signal.measurements["signal_quality"] == 68
    assert signal.measurements["quality_label"] == "среднее"
    assert signal.measurements["elevated_volume_timeframes"] == ["1h"]


def test_consensus_stays_low_but_follows_higher_timeframe_when_timeframes_conflict() -> None:
    signal = generate_indicator_consensus_signal("BTC", [
        observation("1h", "лонг"),
        observation("6h", "шорт"),
    ])

    assert signal is not None
    assert signal.severity == "low"
    assert signal.confidence == 0.03
    assert signal.market_direction == "шорт"
    assert signal.measurements["signal_quality"] == 3
    assert signal.measurements["quality_components"]["conflict_penalty"] == -25


def test_consensus_is_absent_without_observations() -> None:
    assert generate_indicator_consensus_signal("BTC", []) is None
