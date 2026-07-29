from __future__ import annotations

from collections.abc import Sequence
import math
from typing import Any


def _empty_result() -> dict[str, object]:
    return {
        "buy_setup_count": 0, "sell_setup_count": 0,
        "buy_countdown": 0, "sell_countdown": 0,
        "buy_tdst": None, "sell_tdst": None,
        "buy_setup9_low": None, "sell_setup9_high": None,
        "buy_perfected": False, "sell_perfected": False,
        "buy_setup_event": False, "sell_setup_event": False,
        "buy_countdown_event": False, "sell_countdown_event": False,
        "buy_countdown_completed": False, "sell_countdown_completed": False,
        "buy_trap_1": False, "sell_trap_1": False,
        "buy_intersection_confirmed": False, "sell_intersection_confirmed": False,
        "buy_countdown_started": False, "sell_countdown_started": False,
        "buy_setup_active": False, "sell_setup_active": False,
        "buy_setup_cancelled": False, "sell_setup_cancelled": False,
        "buy_recycled": False, "sell_recycled": False,
        "buy_entry_at_countdown_close": None, "sell_entry_at_countdown_close": None,
        "buy_entry_price": None, "sell_entry_price": None,
        "buy_stop_loss_true_range": None, "sell_stop_loss_true_range": None,
        "buy_stop_loss_conservative": None, "sell_stop_loss_conservative": None,
        "buy_exit_signal": None, "sell_exit_signal": None,
        "entry_signal": None, "exit_signal": None,
        "direction": "нейтральное", "signal_state": "neutral",
    }


def _new_state() -> dict[str, Any]:
    return {
        "setup_count": 0,
        "setup_run_length": 0,
        "setup_start": None,
        "active_setup_start": None,
        "setup_complete": False,
        "setup_high": None,
        "setup_low": None,
        "tdst": None,
        "setup9_extreme": None,
        "perfected": False,
        "perfection_deadline": None,
        "intersection": False,
        "countdown": 0,
        "countdown_started": False,
        "completed": False,
        "completion_index": None,
        "entry_at_countdown_close": None,
        "entry_price": None,
        "stop_true_range": None,
        "stop_conservative": None,
        "entry_signal": None,
        "exit_signal": None,
        "inactive_extreme": None,
    }


def _intersection(side: str, index: int, state: dict[str, Any], highs: Sequence[float], lows: Sequence[float]) -> bool:
    start = state["active_setup_start"]
    if start is None or index < start + 7:
        return False
    # Chapter VII: Setup bars 8 and 9 each compare to bars 3–7 earlier.
    # If neither crosses, any later bar may confirm the delayed intersection.
    candidates = (start + 7, start + 8) if index == start + 8 else (index,)
    for candidate in candidates:
        comparison = slice(candidate - 7, candidate - 2)
        if side == "buy" and highs[candidate] >= min(lows[comparison]):
            return True
        if side == "sell" and lows[candidate] <= max(highs[comparison]):
            return True
    return False


def _stop_levels(side: str, state: dict[str, Any], highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], completion_index: int) -> tuple[float, float]:
    start = int(state["active_setup_start"])
    window = range(start, completion_index + 1)
    if side == "buy":
        extreme_index = min(window, key=lambda item: lows[item])
        extreme = lows[extreme_index]
        previous_close = closes[extreme_index - 1] if extreme_index else closes[extreme_index]
        true_range = max(highs[extreme_index], previous_close) - extreme
        conservative = closes[extreme_index] - extreme
        return extreme - true_range, extreme - conservative
    extreme_index = max(window, key=lambda item: highs[item])
    extreme = highs[extreme_index]
    previous_close = closes[extreme_index - 1] if extreme_index else closes[extreme_index]
    true_range = extreme - min(lows[extreme_index], previous_close)
    conservative = extreme - closes[extreme_index]
    return extreme + true_range, extreme + conservative


def calculate_td_sequential(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    use_countdown: bool = True,
    use_combo: bool = True,
    delayed_perfection_bars: int = 3,
) -> dict[str, object]:
    """Calculate book-based DeMark Sequential (Setup → Intersection → Countdown).

    This implements chapter VII of *Technical Analysis — The New Science*:
    price-flip Setup 9, intersection confirmation, non-consecutive Countdown
    13 using close versus low/high two bars earlier, cancellation, recycling,
    three book entry confirmations, exits and both published stop-loss levels.
    ``use_combo`` remains accepted only for backward API compatibility; TD Combo
    is not described by the supplied book and does not alter Sequential rules.
    """
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("highs, lows and closes must have equal lengths")
    if not closes:
        return _empty_result()
    if any(not math.isfinite(float(value)) for series in (highs, lows, closes) for value in series):
        raise ValueError("OHLC values must be finite")

    states = {"buy": _new_state(), "sell": _new_state()}
    events: dict[str, Any] = {
        "buy_setup_event": False, "sell_setup_event": False,
        "buy_countdown_event": False, "sell_countdown_event": False,
        "buy_countdown_completed": False, "sell_countdown_completed": False,
        "buy_setup_cancelled": False, "sell_setup_cancelled": False,
        "buy_recycled": False, "sell_recycled": False,
        "entry_signal": None, "exit_signal": None,
    }
    trap = {"buy": False, "sell": False}

    for index in range(len(closes)):
        events = {key: False if key != "entry_signal" and key != "exit_signal" else None for key in events}
        if index >= 1:
            trap["buy"] = lows[index] < lows[index - 1] and closes[index] > highs[index - 1]
            trap["sell"] = highs[index] > highs[index - 1] and closes[index] < lows[index - 1]
        else:
            trap = {"buy": False, "sell": False}
        if index < 4:
            continue

        conditions = {"buy": closes[index] < closes[index - 4], "sell": closes[index] > closes[index - 4]}
        setup_events: set[str] = set()
        for side in ("buy", "sell"):
            state = states[side]
            condition = conditions[side]
            price_flip = index >= 5 and (
                closes[index - 1] >= closes[index - 5] if side == "buy" else closes[index - 1] <= closes[index - 5]
            )
            previous_count = state["setup_count"]
            previous_run_length = state["setup_run_length"]
            if condition:
                if previous_run_length == 0:
                    if price_flip:
                        state["setup_run_length"] = 1
                        state["setup_count"] = 1
                        state["setup_start"] = index
                    # Otherwise this bar cannot start a book Setup.
                else:
                    state["setup_run_length"] += 1
                    state["setup_count"] = min(9, state["setup_run_length"])
            else:
                state["setup_count"] = 0
                state["setup_run_length"] = 0
                state["setup_start"] = None

            if state["setup_run_length"] == 9 and previous_run_length != 9:
                setup_events.add(side)
                events[f"{side}_setup_event"] = True
                start = int(state["setup_start"])
                state["active_setup_start"] = start
                state["setup_complete"] = True
                state["setup_high"] = max(highs[start:index + 1])
                state["setup_low"] = min(lows[start:index + 1])
                state["tdst"] = max(highs[start:start + 4]) if side == "buy" else min(lows[start:start + 4])
                state["setup9_extreme"] = lows[index] if side == "buy" else highs[index]
                if side == "buy":
                    state["perfected"] = min(lows[start + 7:start + 9]) <= min(lows[start + 5:start + 7])
                else:
                    state["perfected"] = max(highs[start + 7:start + 9]) >= max(highs[start + 5:start + 7])
                state["perfection_deadline"] = None if state["perfected"] else index + max(0, delayed_perfection_bars)

                # A newly completed same-direction Setup replaces the old one:
                # book recycling resets its Countdown and makes it active.
                if state["countdown"] or state["countdown_started"] or state["completed"]:
                    events[f"{side}_recycled"] = True
                state["countdown"] = 0
                state["countdown_started"] = False
                state["completed"] = False
                state["completion_index"] = None
                state["entry_at_countdown_close"] = None
                state["entry_price"] = None
                state["stop_true_range"] = None
                state["stop_conservative"] = None
                state["entry_signal"] = None
                state["exit_signal"] = None
                state["intersection"] = _intersection(side, index, state, highs, lows)

        # Opposite completed Setup invalidates the original active Setup/Countdown.
        # Capture the book exit advisory before clearing the completed lifecycle.
        for side in setup_events:
            other = "sell" if side == "buy" else "buy"
            previous = states[other]
            current = states[side]
            if previous["completed"]:
                inactive_extreme = previous["setup_high"] if other == "buy" else previous["setup_low"]
                current_extreme = current["setup_high"] if other == "buy" else current["setup_low"]
                failed_cross = current_extreme <= inactive_extreme if other == "buy" else current_extreme >= inactive_extreme
                if failed_cross:
                    previous["exit_signal"] = f"{other}_exit_failed_opposite_setup"
                    events["exit_signal"] = previous["exit_signal"]
            if previous["setup_complete"]:
                previous["setup_complete"] = False
                previous["intersection"] = False
                previous["countdown"] = 0
                previous["countdown_started"] = False
                previous["completed"] = False
                events[f"{other}_setup_cancelled"] = True

        for side in ("buy", "sell"):
            state = states[side]
            if not state["setup_complete"]:
                continue
            # A close beyond the full completed Setup range cancels the Setup.
            invalidated = closes[index] > state["setup_high"] if side == "buy" else closes[index] < state["setup_low"]
            active_setup_start = state["active_setup_start"]
            if index not in {active_setup_start + 8 if active_setup_start is not None else -1} and invalidated:
                state["setup_complete"] = False
                state["intersection"] = False
                state["countdown"] = 0
                state["countdown_started"] = False
                state["completed"] = False
                events[f"{side}_setup_cancelled"] = True
                continue

            deadline = state["perfection_deadline"]
            if deadline is not None and index <= deadline:
                if side == "buy":
                    state["perfected"] = state["perfected"] or lows[index] <= min(lows[max(0, index - 3):index])
                else:
                    state["perfected"] = state["perfected"] or highs[index] >= max(highs[max(0, index - 3):index])
                if state["perfected"] or index == deadline:
                    state["perfection_deadline"] = None

            if not state["intersection"] and _intersection(side, index, state, highs, lows):
                state["intersection"] = True

            if use_countdown and side not in setup_events and state["intersection"] and index >= 2:
                state["countdown_started"] = True
                qualifies = closes[index] < lows[index - 2] if side == "buy" else closes[index] > highs[index - 2]
                if qualifies and not state["completed"]:
                    state["countdown"] = min(13, state["countdown"] + 1)
                    if state["countdown"] == 13:
                        state["completed"] = True
                        state["completion_index"] = index
                        state["entry_at_countdown_close"] = closes[index]
                        state["entry_price"] = closes[index]
                        state["stop_true_range"], state["stop_conservative"] = _stop_levels(side, state, highs, lows, closes, index)
                        state["entry_signal"] = f"{side}_countdown_close"
                        events[f"{side}_countdown_event"] = True
                        events[f"{side}_countdown_completed"] = True
                        events["entry_signal"] = state["entry_signal"]

            # A later close through the Chapter VII true-range stop is an
            # advisory exit. It never creates an order or disables human review.
            if state["completed"] and state["completion_index"] is not None and index > state["completion_index"]:
                stop = state["stop_true_range"]
                stop_crossed = (
                    closes[index] < stop if side == "buy" else closes[index] > stop
                ) if stop is not None else False
                if stop_crossed:
                    state["exit_signal"] = f"{side}_exit_stop_loss"
                    events["exit_signal"] = state["exit_signal"]

            # Book methods 2 and 3: a later four-day price flip or two-day confirmation.
            # A stop-loss advisory closes this completed lifecycle; no later entry confirmation is valid.
            if (
                state["completed"]
                and state["completion_index"] is not None
                and index > state["completion_index"]
                and state["exit_signal"] is None
            ):
                price_flip_confirmed = closes[index] > closes[index - 4] if side == "buy" else closes[index] < closes[index - 4]
                two_day_confirmed = closes[index] > highs[index - 2] if side == "buy" else closes[index] < lows[index - 2]
                if two_day_confirmed:
                    state["entry_signal"] = f"{side}_two_day_confirmation"
                    state["entry_price"] = closes[index]
                    events["entry_signal"] = state["entry_signal"]
                elif price_flip_confirmed:
                    state["entry_signal"] = f"{side}_price_flip"
                    state["entry_price"] = closes[index]
                    events["entry_signal"] = state["entry_signal"]

    buy, sell = states["buy"], states["sell"]
    buy_active = bool(buy["setup_count"] or buy["setup_complete"] or buy["countdown"] or buy["completed"])
    sell_active = bool(sell["setup_count"] or sell["setup_complete"] or sell["countdown"] or sell["completed"])
    conflict = buy_active and sell_active
    direction = "конфликт" if conflict else "лонг" if buy_active else "шорт" if sell_active else "нейтральное"
    signal_state = "conflict" if conflict else "completed" if buy["completed"] or sell["completed"] else "countdown" if buy["countdown"] or sell["countdown"] else "intersection" if buy["intersection"] or sell["intersection"] else "setup" if buy_active or sell_active else "neutral"

    return {
        "buy_setup_count": buy["setup_count"], "sell_setup_count": sell["setup_count"],
        "buy_countdown": buy["countdown"], "sell_countdown": sell["countdown"],
        "buy_tdst": buy["tdst"], "sell_tdst": sell["tdst"],
        "buy_setup9_low": buy["setup9_extreme"], "sell_setup9_high": sell["setup9_extreme"],
        "buy_perfected": buy["perfected"], "sell_perfected": sell["perfected"],
        "buy_setup_event": events["buy_setup_event"], "sell_setup_event": events["sell_setup_event"],
        "buy_countdown_event": events["buy_countdown_event"], "sell_countdown_event": events["sell_countdown_event"],
        "buy_countdown_completed": events["buy_countdown_completed"] or buy["completed"],
        "sell_countdown_completed": events["sell_countdown_completed"] or sell["completed"],
        "buy_trap_1": trap["buy"], "sell_trap_1": trap["sell"],
        "buy_intersection_confirmed": buy["intersection"], "sell_intersection_confirmed": sell["intersection"],
        "buy_countdown_started": buy["countdown_started"], "sell_countdown_started": sell["countdown_started"],
        "buy_setup_active": buy["setup_complete"], "sell_setup_active": sell["setup_complete"],
        "buy_setup_cancelled": events["buy_setup_cancelled"], "sell_setup_cancelled": events["sell_setup_cancelled"],
        "buy_recycled": events["buy_recycled"], "sell_recycled": events["sell_recycled"],
        "buy_entry_at_countdown_close": buy["entry_at_countdown_close"], "sell_entry_at_countdown_close": sell["entry_at_countdown_close"],
        "buy_entry_price": buy["entry_price"], "sell_entry_price": sell["entry_price"],
        "buy_stop_loss_true_range": buy["stop_true_range"], "sell_stop_loss_true_range": sell["stop_true_range"],
        "buy_stop_loss_conservative": buy["stop_conservative"], "sell_stop_loss_conservative": sell["stop_conservative"],
        "buy_exit_signal": buy["exit_signal"], "sell_exit_signal": sell["exit_signal"],
        "entry_signal": events["entry_signal"] or buy["entry_signal"] or sell["entry_signal"],
        "exit_signal": events["exit_signal"] or buy["exit_signal"] or sell["exit_signal"],
        "direction": direction, "signal_state": signal_state,
    }
