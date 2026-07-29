import pytest

from crypto_radar.indicators import calculate_indicator_snapshot, classify_demark_direction, classify_rei_direction


def test_demark_direction_uses_requested_neutral_band() -> None:
    assert classify_demark_direction(0.25) == "лонг"
    assert classify_demark_direction(0.75) == "шорт"
    assert classify_demark_direction(0.70) == "нейтральное"
    assert classify_demark_direction(0.30) == "нейтральное"


def test_rei_direction_uses_extreme_regimes_for_forecast() -> None:
    assert classify_rei_direction(-60.0) == "нейтральное"
    assert classify_rei_direction(-60.01) == "лонг"
    assert classify_rei_direction(60.0) == "нейтральное"
    assert classify_rei_direction(60.01) == "шорт"


def test_indicator_snapshot_returns_demark() -> None:
    closes = [100 + index * 0.8 + (index % 3) * 0.2 for index in range(40)]
    highs = [close + 1.0 + (index % 4) * 0.1 for index, close in enumerate(closes)]
    lows = [close - 1.0 - (index % 2) * 0.1 for index, close in enumerate(closes)]

    snapshot = calculate_indicator_snapshot(highs, lows, closes, period=14)

    assert 0.0 <= snapshot["demark"] <= 1.0
    assert snapshot["demark_direction"] in {"лонг", "шорт", "нейтральное"}
    assert snapshot["rei_direction"] in {"лонг", "шорт", "нейтральное"}
def test_indicator_snapshot_excludes_removed_aroon_and_adx() -> None:
    snapshot = calculate_indicator_snapshot(
        highs=[10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24],
        lows=[8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22],
        closes=[9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
    )
    assert not {"aroon_up", "aroon_down", "aroon_direction", "adx", "trend_strength"}.intersection(snapshot)


def test_indicator_snapshot_rejects_short_or_mismatched_ohlc() -> None:
    with pytest.raises(ValueError, match="at least 15"):
        calculate_indicator_snapshot([1] * 14, [0] * 14, [0.5] * 14, period=14)
    with pytest.raises(ValueError, match="same length"):
        calculate_indicator_snapshot([1] * 20, [0] * 19, [0.5] * 20, period=14)


def test_indicator_snapshot_includes_demark_exhaustion_zones_and_rei() -> None:
    closes = [100 + index * 0.8 for index in range(40)]
    highs = [close + 1.0 for close in closes]
    lows = [close - 1.0 for close in closes]

    snapshot = calculate_indicator_snapshot(highs, lows, closes)

    assert snapshot["demark_zone"] in {"oversold", "neutral", "overbought"}
    assert snapshot["demark_exhaustion"] in {"buy_setup", "sell_setup", "none"}
    assert -100.0 <= snapshot["rei"] <= 100.0
    assert snapshot["rei_regime"] in {"oversold", "neutral", "overbought"}


def test_demark_exhaustion_is_confirmed_only_on_return_through_threshold() -> None:
    assert classify_demark_direction(0.25) == "лонг"
    assert classify_demark_direction(0.75) == "шорт"


def test_indicator_snapshot_rejects_non_finite_ohlc() -> None:
    import math

    valid = [float(index) for index in range(15)]
    with pytest.raises(ValueError, match="finite"):
        calculate_indicator_snapshot([*valid[:-1], math.nan], [0.0] * 15, [1.0] * 15)
