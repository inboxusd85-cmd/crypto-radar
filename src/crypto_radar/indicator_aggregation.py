from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from .providers.hyperliquid import SUPPORTED_CANDLE_INTERVALS

TIMEFRAME_ORDER = {"1m": 0, "10m": 1, "1h": 2, "6h": 3, "1d": 4, "1w": 5}
TIMEFRAME_WEIGHTS = {timeframe: (order + 1) * 10 for timeframe, order in TIMEFRAME_ORDER.items()}
INDICATOR_WEIGHTS = {"demark": 1, "rei": 1, "volume": 1, "td_sequential": 1}
_HORIZONS = {
    "local": ("1m", "10m"),
    "tactical": ("1h", "6h"),
    "strategic": ("1d", "1w"),
}


def _horizon_summary(signals: Sequence[dict], timeframes: tuple[str, ...]) -> dict[str, object]:
    included = [item for item in signals if str(item.get("timeframe")) in timeframes]
    available = [str(item.get("timeframe")) for item in included]
    directions = [str(item.get("demark_direction", "нейтральное")) for item in included]
    directional = [direction for direction in directions if direction != "нейтральное"]
    unique = set(directional)
    if not directional:
        direction, status = "нейтральное", "нейтрально"
    elif len(unique) == 1 and len(directional) == len(directions):
        direction, status = directional[0], "согласован"
    elif len(unique) == 1:
        direction, status = directional[0], "частично"
    else:
        weighted = {
            direction: sum(TIMEFRAME_WEIGHTS.get(str(item.get("timeframe")), 0) for item in included if item.get("demark_direction") == direction)
            for direction in ("лонг", "шорт")
        }
        direction = max(weighted, key=weighted.get) if weighted["лонг"] != weighted["шорт"] else "нейтральное"
        status = "конфликт"
    return {"direction": direction, "timeframes": available, "status": status}


def _market_regime(direction: str, agreement: bool, horizons: dict[str, dict[str, object]]) -> str:
    if any(not item["timeframes"] for item in horizons.values()):
        return "недостаточно данных"
    horizon_directions = {str(item["direction"]) for item in horizons.values()}
    if direction == "нейтральное":
        return "диапазон"
    if len(horizon_directions) > 1:
        return "переходный"
    return "направленный"


def _demark_context(signals: Sequence[dict]) -> dict[str, object]:
    oversold: list[str] = []
    overbought: list[str] = []
    exhaustion = {"buy_setup": [], "sell_setup": []}
    for item in signals:
        timeframe = str(item.get("timeframe"))
        zone = item.get("demark_zone")
        event = item.get("demark_exhaustion")
        if zone == "oversold":
            oversold.append(timeframe)
        elif zone == "overbought":
            overbought.append(timeframe)
        if event in exhaustion:
            exhaustion[event].append(timeframe)
    context_direction = "лонг" if exhaustion["buy_setup"] and not exhaustion["sell_setup"] else "шорт" if exhaustion["sell_setup"] and not exhaustion["buy_setup"] else "нейтральное"
    return {
        "oversold_timeframes": oversold,
        "overbought_timeframes": overbought,
        "exhaustion_events": exhaustion,
        "context_direction": context_direction,
        "has_conflict": bool(exhaustion["buy_setup"] and exhaustion["sell_setup"]),
    }


def _td_scenario_summary(signals: Sequence[dict]) -> dict[str, object]:
    qualified: dict[str, list[str]] = {"long": [], "short": []}
    frames: list[str] = []
    for item in signals:
        timeframe = str(item.get("timeframe"))
        scenario = item.get("td_scenario")
        if not isinstance(scenario, dict):
            continue
        frames.append(timeframe)
        if scenario.get("qualified") is True and scenario.get("scenario") in qualified:
            qualified[str(scenario["scenario"])].append(timeframe)
    qualified_frames = qualified["long"] + qualified["short"]
    if not frames:
        status = "unavailable"
    elif not qualified_frames:
        status = "none"
    elif qualified["long"] and qualified["short"]:
        status = "conflict"
    elif len(qualified_frames) < len(frames):
        status = "partial"
    else:
        status = "confirmed"
    return {"qualified_timeframes": qualified_frames, "qualified_scenarios": qualified, "observed_timeframes": frames, "status": status}


def _observed_at_ms(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        return round(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def _timeframe_reliability(signals: Sequence[dict]) -> tuple[int, dict[str, dict[str, int]]]:
    reliability: dict[str, dict[str, int]] = {}
    weighted_quality = 0
    total_weight = 0
    for item in signals:
        timeframe = str(item.get("timeframe"))
        weight = TIMEFRAME_WEIGHTS.get(timeframe, 0)
        interval_ms = SUPPORTED_CANDLE_INTERVALS.get(timeframe)
        observed_at_ms = _observed_at_ms(item.get("observed_at"))
        candle_open_time = item.get("candle_open_time")
        if interval_ms is None or observed_at_ms is None or not isinstance(candle_open_time, int):
            freshness = 100
        else:
            age_intervals = max(0.0, (observed_at_ms - (candle_open_time + interval_ms)) / interval_ms)
            freshness = round(max(0.0, 100 * (1 - age_intervals / 2)))
        count = item.get("closed_candle_count")
        completeness = min(100, round(100 * count / 30)) if isinstance(count, int) and count >= 0 else 100
        score = round(freshness * completeness / 100)
        reliability[timeframe] = {"freshness": freshness, "completeness": completeness, "score": score}
        weighted_quality += weight * score
        total_weight += weight
    data_quality = round(weighted_quality / total_weight) if total_weight else 0
    return data_quality, reliability


def _signal_quality(
    signals: Sequence[dict],
    timeframe_weights: dict[str, int],
    directional_scores: dict[str, int],
    horizons: dict[str, dict[str, object]],
) -> tuple[int, str, dict[str, int]]:
    max_weight = sum(TIMEFRAME_WEIGHTS.values())
    available_weight = sum(timeframe_weights.values())
    directional_weight = directional_scores["лонг"] + directional_scores["шорт"]
    direction_score = round(
        (directional_scores["лонг"] - directional_scores["шорт"]) / directional_weight * 100
    ) if directional_weight else 0
    weighted = lambda predicate: sum(
        timeframe_weights[str(item.get("timeframe"))] for item in signals if predicate(item)
    )
    coverage = round(20 * available_weight / max_weight) if max_weight else 0
    directional_alignment = round(40 * abs(direction_score) / 100)
    indicator_agreement = round(15 * weighted(lambda item: item.get("direction_agreement") is True) / available_weight) if available_weight else 0
    volume_confirmation = round(10 * weighted(lambda item: item.get("volume_regime") == "повышенный") / available_weight) if available_weight else 0
    conflict_penalty = -25 if directional_scores["лонг"] and directional_scores["шорт"] else 0
    if any(item["status"] == "конфликт" for item in horizons.values()):
        conflict_penalty = min(conflict_penalty, -25)
    components = {
        "coverage": coverage,
        "directional_alignment": directional_alignment,
        "indicator_agreement": indicator_agreement,
        "volume_confirmation": volume_confirmation,
        "conflict_penalty": conflict_penalty,
    }
    quality = max(0, min(100, sum(components.values())))
    label = "высокое" if quality >= 75 else "среднее" if quality >= 50 else "низкое"
    return quality, label, components


def aggregate_indicator_signals(signals: Sequence[dict]) -> dict[str, object]:
    timeframes = [str(item.get("timeframe")) for item in signals]
    if len(timeframes) != len(set(timeframes)):
        raise ValueError("duplicate timeframe observations are not allowed")
    if not signals:
        return {
            "market_direction": "нейтральное",
            "market_regime": "диапазон",
            "horizons": {name: {"direction": "нейтральное", "timeframes": [], "status": "нет данных"} for name in _HORIZONS},
            "direction_score": 0,
            "signal_quality": 0,
            "data_quality": 0,
            "timeframe_reliability": {},
            "quality_label": "низкое",
            "quality_components": {"coverage": 0, "directional_alignment": 0, "indicator_agreement": 0, "volume_confirmation": 0, "conflict_penalty": 0},
            "direction_agreement": False,
            "confirmed_timeframes": [],
            "timeframe_weights": {},
            "directional_scores": {"лонг": 0, "шорт": 0},
            "indicator_weights": INDICATOR_WEIGHTS,
            "indicator_scores": {name: {"лонг": 0, "шорт": 0} for name in INDICATOR_WEIGHTS},
            "td_scenario_summary": _td_scenario_summary(signals),
            "demark_context": _demark_context(signals),
            "basis": "Нет доступных индикаторных таймфреймов для агрегирования.",
        }
    ordered = sorted(signals, key=lambda item: TIMEFRAME_ORDER.get(str(item.get("timeframe")), 99))
    directions = [str(item.get("demark_direction", "нейтральное")) for item in ordered]
    directional = [direction for direction in directions if direction != "нейтральное"]
    unique = set(directional)
    timeframe_weights = {str(item.get("timeframe")): TIMEFRAME_WEIGHTS.get(str(item.get("timeframe")), 0) for item in ordered}
    def vote(item: dict, indicator: str) -> str:
        if indicator == "volume":
            return str(item.get("demark_direction")) if item.get("volume_regime") == "повышенный" and item.get("direction_agreement") is True else "нейтральное"
        if indicator == "demark":
            return str(item.get("demark_direction", item.get("td_sequential", {}).get("direction", "нейтральное")))
        if indicator == "rei":
            return str(item.get("rei_direction", "нейтральное"))
        if indicator == "td_sequential":
            return str(item.get("td_sequential", {}).get("direction", item.get("demark_direction", "нейтральное")))
        return str(item.get(f"{indicator}_direction", "нейтральное"))

    indicator_scores = {
        indicator: {
            direction: sum(
                timeframe_weights[str(item.get("timeframe"))] * INDICATOR_WEIGHTS[indicator]
                for item in ordered if vote(item, indicator) == direction
            )
            for direction in ("лонг", "шорт")
        }
        for indicator in INDICATOR_WEIGHTS
    }
    directional_scores = {
        direction: sum(scores[direction] for scores in indicator_scores.values())
        for direction in ("лонг", "шорт")
    }
    indicator_directions = [vote(item, indicator) for item in ordered for indicator in INDICATOR_WEIGHTS]
    indicator_directional = [direction for direction in indicator_directions if direction != "нейтральное"]
    agreement = bool(indicator_directional) and len(set(indicator_directional)) == 1
    top_direction = max(directional_scores, key=directional_scores.get)
    # Indicator votes (volume/TD) may agree while all DeMark observations are
    # neutral. Do not index the empty DeMark list in that partial-data state.
    direction = directional[0] if agreement and directional else top_direction if directional_scores[top_direction] > directional_scores["шорт" if top_direction == "лонг" else "лонг"] else "нейтральное"
    timeframe_names = [str(item.get("timeframe")) for item in ordered]
    if agreement:
        basis = f"Направление «{direction}» подтверждено независимыми голосами DeMarker, объёма и TD Sequential на таймфреймах: {', '.join(timeframe_names)}."
    elif unique:
        votes = ", ".join(f"{item.get('timeframe')}={item.get('demark_direction')} ({timeframe_weights[str(item.get('timeframe'))]} п.)" for item in ordered)
        score_text = f"лонг={directional_scores['лонг']} п., шорт={directional_scores['шорт']} п."
        outcome = f"Преимущество старших таймфреймов даёт направление «{direction}»." if direction != "нейтральное" else "Итоговое направление нейтральное: взвешенные голоса равны."
        basis = f"Конфликт направлений DeMarker между таймфреймами: {votes}. Взвешенные голоса: {score_text}. {outcome}"
    else:
        basis = f"DeMarker находится в нейтральной зоне на таймфреймах: {', '.join(timeframe_names)}. Независимые голоса объёма и TD Sequential не дают направленного подтверждения."
    horizons = {name: _horizon_summary(ordered, timeframes) for name, timeframes in _HORIZONS.items()}
    demark_context = _demark_context(ordered)
    basis += f" DeMarker context: oversold={demark_context['oversold_timeframes']}, overbought={demark_context['overbought_timeframes']}, exhaustion={demark_context['exhaustion_events']}."
    signal_quality, quality_label, quality_components = _signal_quality(ordered, timeframe_weights, directional_scores, horizons)
    data_quality, timeframe_reliability = _timeframe_reliability(ordered)
    signal_quality = round(signal_quality * data_quality / 100)
    quality_label = "высокое" if signal_quality >= 75 else "среднее" if signal_quality >= 50 else "низкое"
    directional_weight = directional_scores["лонг"] + directional_scores["шорт"]
    direction_score = round((directional_scores["лонг"] - directional_scores["шорт"]) / directional_weight * 100) if directional_weight else 0
    return {
        "market_direction": direction,
        "market_regime": _market_regime(direction, agreement, horizons),
        "horizons": horizons,
        "direction_score": direction_score,
        "signal_quality": signal_quality,
        "data_quality": data_quality,
        "timeframe_reliability": timeframe_reliability,
        "quality_label": quality_label,
        "quality_components": quality_components,
        "direction_agreement": agreement,

        "confirmed_timeframes": timeframe_names if agreement else [],
        "timeframe_weights": timeframe_weights,
        "directional_scores": directional_scores,
        "indicator_weights": INDICATOR_WEIGHTS,
        "indicator_scores": indicator_scores,
        "td_scenario_summary": _td_scenario_summary(ordered),
        "demark_context": demark_context,
        "basis": basis,
    }
