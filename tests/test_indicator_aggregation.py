from crypto_radar.indicator_aggregation import aggregate_indicator_signals


def signal(timeframe: str, direction: str, strength: str = "сильный") -> dict:
    return {
        "timeframe": timeframe,
        "demark_direction": direction,
        "aroon_direction": direction,
        "trend_strength": strength,
        "adx": 30.0 if strength == "сильный" else 15.0,
        "direction_agreement": direction != "нейтральное",
        "rei_direction": "нейтральное",
        "demark_zone": "neutral",
        "demark_exhaustion": "none",
    }


def test_aggregate_returns_long_when_all_timeframes_confirm_long() -> None:
    result = aggregate_indicator_signals([signal("1m", "лонг"), signal("1h", "лонг"), signal("1d", "лонг")])

    assert result["market_direction"] == "лонг"
    assert result["direction_agreement"] is True
    assert "trend_strength" not in result
    assert result["confirmed_timeframes"] == ["1m", "1h", "1d"]


def test_aggregate_returns_neutral_when_weighted_votes_tie() -> None:
    result = aggregate_indicator_signals([signal("1m", "лонг"), signal("10m", "лонг"), signal("1h", "шорт")])

    assert result["market_direction"] == "нейтральное"
    assert result["direction_agreement"] is False
    assert "конфликт" in result["basis"].lower()


def test_aggregate_gives_each_higher_timeframe_ten_more_points() -> None:
    result = aggregate_indicator_signals([
        signal("1m", "лонг"),
        signal("10m", "лонг"),
        signal("1h", "лонг"),
        signal("1d", "шорт"),
        signal("1w", "шорт"),
    ])

    assert result["market_direction"] == "шорт"
    assert result["direction_agreement"] is False
    assert result["timeframe_weights"] == {"1m": 10, "10m": 20, "1h": 30, "1d": 50, "1w": 60}
    assert result["directional_scores"] == {"лонг": 120, "шорт": 220}
    assert result["indicator_weights"] == {"demark": 1, "rei": 1, "volume": 1, "td_sequential": 1}
    assert result["indicator_scores"]["demark"] == {"лонг": 60, "шорт": 110}


def test_aggregate_has_no_removed_trend_strength_field() -> None:
    result = aggregate_indicator_signals([signal("1m", "нейтральное"), signal("1h", "нейтральное")])

    assert result["market_direction"] == "нейтральное"
    assert "trend_strength" not in result


def test_aggregate_does_not_index_empty_demark_votes_when_other_indicators_agree() -> None:
    observations = [
        {**signal(timeframe, "нейтральное"), "volume_regime": "повышенный", "direction_agreement": True, "td_sequential": {"direction": "лонг"}}
        for timeframe in ("1m", "1h")
    ]
    result = aggregate_indicator_signals(observations)
    assert result["market_direction"] in {"лонг", "нейтральное"}


def test_rei_direction_participates_in_forecast_when_demark_is_neutral() -> None:
    result = aggregate_indicator_signals([
        {**signal("1h", "нейтральное"), "rei_direction": "лонг"},
        {**signal("1d", "нейтральное"), "rei_direction": "лонг"},
    ])
    assert result["market_direction"] == "лонг"
    assert result["indicator_scores"]["rei"] == {"лонг": 80, "шорт": 0}


def test_demark_zone_and_exhaustion_are_forecast_context() -> None:
    result = aggregate_indicator_signals([
        {**signal("1h", "лонг"), "demark_zone": "oversold", "demark_exhaustion": "buy_setup"},
        {**signal("1d", "шорт"), "demark_zone": "overbought", "demark_exhaustion": "sell_setup"},
    ])
    assert result["demark_context"]["oversold_timeframes"] == ["1h"]
    assert result["demark_context"]["overbought_timeframes"] == ["1d"]
    assert result["demark_context"]["exhaustion_events"] == {"buy_setup": ["1h"], "sell_setup": ["1d"]}
    assert "DeMarker context" in result["basis"]


def test_aggregate_rejects_duplicate_timeframes() -> None:
    import pytest

    with pytest.raises(ValueError, match="duplicate timeframe"):
        aggregate_indicator_signals([signal("1h", "лонг"), signal("1h", "шорт")])


def test_aggregate_separates_market_regime_and_directional_horizons() -> None:
    result = aggregate_indicator_signals([
        signal("1m", "шорт"),
        signal("10m", "шорт"),
        signal("1h", "лонг"),
        signal("6h", "лонг"),
        signal("1d", "лонг"),
        signal("1w", "нейтральное"),
    ])

    assert result["market_direction"] == "лонг"
    assert result["market_regime"] == "переходный"
    assert result["horizons"] == {
        "local": {"direction": "шорт", "timeframes": ["1m", "10m"], "status": "согласован"},
        "tactical": {"direction": "лонг", "timeframes": ["1h", "6h"], "status": "согласован"},
        "strategic": {"direction": "лонг", "timeframes": ["1d", "1w"], "status": "частично"},
    }


def test_aggregate_uses_directional_regime_when_demark_agrees() -> None:
    result = aggregate_indicator_signals([
        signal("1m", "лонг", "слабый"),
        signal("10m", "лонг", "слабый"),
        signal("1h", "лонг", "слабый"),
        signal("6h", "лонг", "слабый"),
        signal("1d", "лонг", "слабый"),
        signal("1w", "лонг", "слабый"),
    ])

    assert result["market_direction"] == "лонг"
    assert result["market_regime"] == "направленный"


def test_aggregate_reports_insufficient_data_when_horizons_are_missing() -> None:
    result = aggregate_indicator_signals([signal("1d", "лонг")])

    assert result["market_direction"] == "лонг"
    assert result["market_regime"] == "недостаточно данных"


def test_aggregate_reduces_quality_when_closed_candles_are_stale() -> None:
    observed_at = "2026-07-22T12:00:00Z"
    stale = [
        {
            **signal(timeframe, "лонг"),
            "candle_open_time": 1_782_302_400_000,
            "closed_candle_count": 80,
            "observed_at": observed_at,
        }
        for timeframe in ("1m", "10m", "1h", "6h", "1d", "1w")
    ]

    result = aggregate_indicator_signals(stale)

    assert result["data_quality"] == 0
    assert result["signal_quality"] == 0
    assert result["timeframe_reliability"]["1h"]["freshness"] == 0


def test_aggregate_scores_quality_from_weighted_agreement_and_evidence() -> None:
    result = aggregate_indicator_signals([
        signal("1m", "лонг"),
        signal("10m", "лонг"),
        signal("1h", "лонг"),
        signal("6h", "лонг"),
        signal("1d", "лонг"),
        signal("1w", "лонг"),
    ])

    assert result["direction_score"] == 100
    assert result["signal_quality"] == 75
    assert result["quality_label"] == "высокое"
    assert result["quality_components"] == {
        "coverage": 20,
        "directional_alignment": 40,
        "indicator_agreement": 15,
        "volume_confirmation": 0,
        "conflict_penalty": 0,
    }


def test_aggregate_penalizes_conflict_in_higher_weighted_timeframes() -> None:
    result = aggregate_indicator_signals([
        signal("1m", "лонг"),
        signal("10m", "лонг"),
        signal("1h", "лонг"),
        signal("6h", "шорт"),
        signal("1d", "шорт"),
        signal("1w", "шорт"),
    ])

    assert result["market_direction"] == "шорт"
    assert result["direction_score"] == -43
    assert result["signal_quality"] == 27
    assert result["quality_label"] == "низкое"
    assert result["quality_components"]["conflict_penalty"] == -25
