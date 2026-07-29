from __future__ import annotations

from crypto_radar.td_sequential import _stop_levels, calculate_td_sequential


def test_buy_setup_reaches_nine_and_creates_tdst() -> None:
    closes = [100, 110, 100, 110, 100, 90, 89, 88, 87, 86, 85, 84, 83, 82]
    highs = [value + 2 for value in closes]
    lows = [value - 2 for value in closes]

    result = calculate_td_sequential(highs, lows, closes, use_countdown=False)

    assert result["buy_setup_count"] == 9
    assert result["buy_setup_event"] is True
    assert result["buy_tdst"] == 92
    assert result["direction"] == "лонг"


def test_sell_setup_reaches_nine_and_creates_tdst() -> None:
    closes = [100, 90, 100, 90, 100, 110, 111, 112, 113, 114, 115, 116, 117, 118]
    highs = [value + 2 for value in closes]
    lows = [value - 2 for value in closes]

    result = calculate_td_sequential(highs, lows, closes, use_countdown=False)

    assert result["sell_setup_count"] == 9
    assert result["sell_setup_event"] is True
    assert result["sell_tdst"] == 108
    assert result["direction"] == "шорт"


def test_td_sequential_reports_countdown_progress_and_trap_events() -> None:
    closes = [100, 110, 100, 110, 100] + list(range(90, 57, -1))
    highs = [value + 1 for value in closes]
    lows = [value for value in closes]
    highs[12] = 100  # intersection on the eighth Setup day
    result = calculate_td_sequential(highs, lows, closes)

    assert result["buy_setup_count"] >= 1
    assert result["buy_countdown"] >= 1
    assert result["signal_state"] in {"setup", "intersection", "countdown", "completed", "neutral"}

    trap = calculate_td_sequential([10, 10, 10, 10, 12], [8, 8, 8, 8, 6], [9, 9, 9, 9, 11], use_countdown=False)
    assert trap["buy_trap_1"] is True
    assert trap["sell_trap_1"] is False


def test_countdown_starts_after_setup_bar_nine() -> None:
    closes = [100, 110, 100, 110, 100, 90, 89, 88, 87, 86, 85, 84, 83, 82]
    result = calculate_td_sequential([value + 2 for value in closes], [value - 2 for value in closes], closes)
    assert result["buy_setup_event"] is True
    assert result["buy_countdown"] == 0


def test_td_conflict_is_not_reported_as_long() -> None:
    closes = [100]
    for index in range(100):
        closes.append(closes[-1] + (3 if (index % 4) < 2 else -3))
    result = calculate_td_sequential([value + 1 for value in closes], [value - 1 for value in closes], closes)
    if result["buy_countdown"] and result["sell_countdown"]:
        assert result["direction"] == "конфликт"
        assert result["signal_state"] == "conflict"


def test_legacy_combo_flag_does_not_change_book_sequential_rules() -> None:
    closes = [100, 110, 100, 110, 100] + list(range(90, 57, -1))
    highs = [value + 1 for value in closes]
    lows = [value for value in closes]
    highs[12] = 100
    enabled = calculate_td_sequential(highs, lows, closes, use_combo=True)
    disabled = calculate_td_sequential(highs, lows, closes, use_combo=False)
    assert enabled["buy_countdown"] >= 1
    assert disabled["buy_countdown"] == enabled["buy_countdown"]


def test_delayed_perfection_is_applied_within_configured_window() -> None:
    closes = [100, 110, 100, 110, 100, 90, 89, 88, 87, 86, 85, 84, 83, 82, 81]
    highs = [value + 2 for value in closes]
    lows = [value - 2 for value in closes]
    lows[13] = lows[8]
    result = calculate_td_sequential(highs, lows, closes, use_countdown=False, delayed_perfection_bars=2)
    assert result["buy_setup_event"] is False
    assert result["buy_perfected"] is True


def test_countdown_requires_confirmed_intersection_and_uses_low_two_bars_ago() -> None:
    closes = [100, 110, 100, 110, 100, 90, 89, 88, 87, 86, 85, 84, 83, 82, 82]
    highs = [value + 2 for value in closes]
    lows = [value - 2 for value in closes]
    # Buy setup's 8th day overlaps an earlier setup low, confirming intersection.
    highs[12] = 100
    # Last close is <= close two bars ago (83), but not < low two bars ago (81).
    result = calculate_td_sequential(highs, lows, closes)

    assert result["buy_intersection_confirmed"] is True
    assert result["buy_countdown"] == 0
    assert result["buy_countdown_started"] is True


def test_buy_countdown_rejects_close_equal_to_low_two_bars_ago() -> None:
    closes = [100, 110, 100, 110, 100, 90, 89, 88, 87, 86, 85, 84, 83, 82, 81]
    highs = [value + 2 for value in closes]
    lows = [value - 2 for value in closes]
    highs[12] = 100
    result = calculate_td_sequential(highs, lows, closes)

    assert result["buy_intersection_confirmed"] is True
    assert result["buy_countdown"] == 0


def test_delayed_intersection_after_setup_nine_starts_countdown_only_when_confirmed() -> None:
    closes = [100, 110, 100, 110, 100, 90, 89, 88, 87, 86, 85, 84, 83, 82, 81]
    highs = [value + 2 for value in closes]
    lows = [value - 2 for value in closes]
    highs[12] = 50  # Setup bar 8: no intersection.
    highs[13] = 50  # Setup bar 9: no intersection.
    highs[14] = 90  # Later bar crosses the low range at least three bars back.
    result = calculate_td_sequential(highs, lows, closes)

    assert result["buy_intersection_confirmed"] is True
    assert result["buy_countdown_started"] is True
    assert result["buy_countdown"] == 0


def test_setup_is_cancelled_when_close_crosses_its_full_setup_extreme() -> None:
    closes = [100, 110, 100, 110, 100, 90, 89, 88, 87, 86, 85, 84, 83, 82, 151]
    highs = [value + 2 for value in closes]
    lows = [value - 2 for value in closes]
    result = calculate_td_sequential(highs, lows, closes)

    assert result["buy_setup_cancelled"] is True
    assert result["buy_setup_active"] is False
    assert result["buy_countdown"] == 0


def test_same_direction_setup_recycles_active_countdown() -> None:
    first_setup = [100, 110, 100, 110, 100, 90, 89, 88, 87, 86, 85, 84, 83, 82]
    closes = first_setup + [83, 84, 85, 86, 87] + list(range(70, 61, -1))
    highs = [value + 2 for value in closes]
    lows = [value - 2 for value in closes]
    highs[12] = 100
    result = calculate_td_sequential(highs, lows, closes)

    assert result["buy_recycled"] is True
    assert result["buy_countdown"] <= 1
    assert result["buy_setup_count"] == 9


def test_completed_countdown_exposes_book_entry_and_stop_loss_levels() -> None:
    closes = [100, 110, 100, 110, 100] + list(range(90, 60, -1))
    highs = [value + 2 for value in closes]
    lows = [value for value in closes]
    highs[12] = 100
    result = calculate_td_sequential(highs, lows, closes)

    assert result["buy_countdown_completed"] is True
    assert result["buy_entry_at_countdown_close"] is not None
    assert result["buy_stop_loss_true_range"] is not None
    assert result["buy_stop_loss_conservative"] is not None
    assert result["entry_signal"] in {"buy_countdown_close", "buy_price_flip", "buy_two_day_confirmation"}


def test_two_day_confirmation_exposes_actual_entry_price() -> None:
    closes = [100, 110, 100, 110, 100] + list(range(90, 68, -1)) + [75]
    highs = [value + 2 for value in closes]
    lows = list(closes)
    highs[12] = 100
    result = calculate_td_sequential(highs, lows, closes)

    assert result["entry_signal"] == "buy_two_day_confirmation"
    assert result["buy_entry_at_countdown_close"] == 69
    assert result["buy_entry_price"] == 75


def test_book_stop_loss_formulas_use_extreme_bar_and_prior_close() -> None:
    state = {"active_setup_start": 1}
    highs = [110.0, 108.0, 107.0, 109.0]
    lows = [100.0, 95.0, 90.0, 96.0]
    closes = [105.0, 100.0, 94.0, 104.0]

    buy_true_range, buy_conservative = _stop_levels("buy", state, highs, lows, closes, 3)
    sell_true_range, sell_conservative = _stop_levels("sell", state, highs, lows, closes, 3)

    assert (buy_true_range, buy_conservative) == (73.0, 86.0)
    assert (sell_true_range, sell_conservative) == (124.0, 114.0)


def test_completed_buy_countdown_emits_exit_when_later_close_crosses_true_range_stop() -> None:
    closes = [100, 110, 100, 110, 100] + list(range(90, 60, -1)) + [66]
    highs = [value + 2 for value in closes]
    lows = list(closes)
    highs[12] = 100
    result = calculate_td_sequential(highs, lows, closes)

    assert result["buy_stop_loss_true_range"] == 67
    assert result["buy_exit_signal"] == "buy_exit_stop_loss"
    assert result["exit_signal"] == "buy_exit_stop_loss"


def test_completed_sell_countdown_emits_exit_when_later_close_crosses_true_range_stop() -> None:
    closes = [100, 90, 100, 90, 100] + list(range(110, 141))
    highs = list(closes)
    lows = [value - 2 for value in closes]
    lows[12] = 90
    result = calculate_td_sequential(highs, lows, closes)

    assert result["sell_stop_loss_true_range"] == 133
    assert result["sell_exit_signal"] == "sell_exit_stop_loss"
    assert result["exit_signal"] == "sell_exit_stop_loss"


def test_stop_exit_prevents_later_entry_confirmation() -> None:
    closes = [100, 110, 100, 110, 100] + list(range(90, 60, -1)) + [66, 75]
    highs = [value + 2 for value in closes]
    lows = list(closes)
    highs[12] = 100
    result = calculate_td_sequential(highs, lows, closes)

    assert result["buy_exit_signal"] == "buy_exit_stop_loss"
    assert result["exit_signal"] == "buy_exit_stop_loss"
    assert result["entry_signal"] == "buy_countdown_close"


def test_completed_countdown_emits_advisory_exit_before_opposite_setup_cancellation() -> None:
    buy_sequence = [100, 110, 100, 110, 100] + list(range(90, 57, -1))
    closes = buy_sequence + [58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70]
    highs = [value + 2 for value in closes]
    lows = [value for value in closes]
    highs[12] = 100
    result = calculate_td_sequential(highs, lows, closes)

    assert result["buy_setup_active"] is False
    assert result["exit_signal"] == "buy_exit_failed_opposite_setup"


def test_opposite_setup_crossing_inactive_extreme_does_not_emit_opposite_setup_exit() -> None:
    buy_sequence = [100, 110, 100, 110, 100] + list(range(90, 57, -1))
    closes = buy_sequence + list(range(70, 83))
    highs = [value + 2 for value in closes]
    lows = list(closes)
    highs[12] = 100
    for index in range(len(buy_sequence), len(highs)):
        highs[index] = 120  # Every bar of the opposite Setup crosses the inactive Buy extreme.
    result = calculate_td_sequential(highs, lows, closes)

    assert result["buy_countdown_completed"] is False
    assert result["buy_exit_signal"] != "buy_exit_opposite_setup_reversal"
    assert result["exit_signal"] != "buy_exit_opposite_setup_reversal"
