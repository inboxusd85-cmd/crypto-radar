from __future__ import annotations

from typing import Any


def _empty(reason: str) -> dict[str, Any]:
    return {
        "scenario": "none", "qualified": False, "reason": reason,
        "invalidation_level": None, "stop_reference": None,
        "target_reference": None, "requires_manual_review": True,
        "auto_trade": False,
    }


def build_td_scenario(
    *,
    demark_exhaustion: str,
    demark_zone: str,
    td: dict[str, Any],
    structure: dict[str, Any],
    retracement: dict[str, Any],
    close: float,
) -> dict[str, Any]:
    """Build a read-only scenario only from a completed book Sequential signal.

    DeMarker remains contextual confirmation; Setup 9 alone is explicitly not a
    trade-ready Sequential scenario. The published true-range stop is preferred
    when available, with structural TD lines retained as a fallback reference.
    """
    buy_completed = bool(td.get("buy_countdown_completed"))
    sell_completed = bool(td.get("sell_countdown_completed"))
    if buy_completed and sell_completed:
        return _empty("conflicting_completed_sequential")
    direction = "лонг" if buy_completed else "шорт" if sell_completed else None
    if direction is None:
        return _empty("sequential_not_completed")
    if demark_zone != "neutral":
        return _empty("demark_context_not_neutral")

    if direction == "лонг":
        demand = structure.get("td_demand_line")
        target = retracement.get("retracement_382")
        stop = td.get("buy_stop_loss_true_range") or demand
        if demand is None or target is None or demand >= close or stop is None:
            return _empty("insufficient_structure")
        return {
            "scenario": "long", "qualified": True,
            "reason": "book_sequential_buy_completed",
            "invalidation_level": stop, "stop_reference": stop,
            "target_reference": target, "requires_manual_review": True,
            "auto_trade": False,
        }
    if direction == "шорт":
        supply = structure.get("td_supply_line")
        target = retracement.get("retracement_618")
        stop = td.get("sell_stop_loss_true_range") or supply
        if supply is None or target is None or supply <= close or stop is None:
            return _empty("insufficient_structure")
        return {
            "scenario": "short", "qualified": True,
            "reason": "book_sequential_sell_completed",
            "invalidation_level": stop, "stop_reference": stop,
            "target_reference": target, "requires_manual_review": True,
            "auto_trade": False,
        }
    return _empty("conditions_not_confirmed")
