from __future__ import annotations

from crypto_radar.td_scenarios import build_td_scenario


def test_long_scenario_requires_completed_book_sequential_signal() -> None:
    result = build_td_scenario(
        demark_exhaustion="buy_setup",
        demark_zone="neutral",
        td={"direction": "лонг", "signal_state": "setup", "buy_setup_count": 9, "buy_countdown": 0},
        structure={"td_demand_line": 96.0, "td_supply_line": 106.0},
        retracement={"retracement_382": 102.0, "retracement_618": 98.0},
        close=100.0,
    )

    assert result["scenario"] == "none"
    assert result["qualified"] is False
    assert result["reason"] == "sequential_not_completed"


def test_completed_book_signal_uses_book_stop_reference() -> None:
    result = build_td_scenario(
        demark_exhaustion="buy_setup",
        demark_zone="neutral",
        td={
            "direction": "лонг", "signal_state": "completed", "buy_setup_count": 9,
            "buy_countdown": 13, "buy_countdown_completed": True,
            "buy_stop_loss_true_range": 94.0, "entry_signal": "buy_countdown_close",
        },
        structure={"td_demand_line": 96.0, "td_supply_line": 106.0},
        retracement={"retracement_382": 102.0, "retracement_618": 98.0},
        close=100.0,
    )

    assert result["scenario"] == "long"
    assert result["qualified"] is True
    assert result["stop_reference"] == 94.0


def test_completed_buy_scenario_survives_aggregate_direction_conflict() -> None:
    result = build_td_scenario(
        demark_exhaustion="buy_setup",
        demark_zone="neutral",
        td={
            "direction": "конфликт", "buy_countdown_completed": True,
            "sell_countdown_completed": False, "buy_stop_loss_true_range": 94.0,
        },
        structure={"td_demand_line": 96.0, "td_supply_line": 106.0},
        retracement={"retracement_382": 102.0, "retracement_618": 98.0},
        close=100.0,
    )

    assert result["scenario"] == "long"
    assert result["qualified"] is True
    assert result["requires_manual_review"] is True


def test_simultaneous_completed_sides_are_explicitly_unqualified() -> None:
    result = build_td_scenario(
        demark_exhaustion="none",
        demark_zone="neutral",
        td={"buy_countdown_completed": True, "sell_countdown_completed": True},
        structure={"td_demand_line": 96.0, "td_supply_line": 106.0},
        retracement={"retracement_382": 102.0, "retracement_618": 98.0},
        close=100.0,
    )

    assert result["qualified"] is False
    assert result["reason"] == "conflicting_completed_sequential"
    assert result["requires_manual_review"] is True


def test_scenario_is_unqualified_when_required_structure_is_missing() -> None:
    result = build_td_scenario(
        demark_exhaustion="buy_setup",
        demark_zone="neutral",
        td={
            "direction": "лонг", "signal_state": "completed", "buy_setup_count": 9,
            "buy_countdown": 13, "buy_countdown_completed": True,
        },
        structure={"td_demand_line": None, "td_supply_line": 106.0},
        retracement={"retracement_382": None, "retracement_618": None},
        close=100.0,
    )

    assert result["scenario"] == "none"
    assert result["qualified"] is False
    assert result["reason"] == "insufficient_structure"
    assert result["stop_reference"] is None