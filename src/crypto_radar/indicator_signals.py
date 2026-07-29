from __future__ import annotations

from collections.abc import Sequence
from statistics import median

from .indicators import calculate_indicator_snapshot
from .models import Signal
from .providers.hyperliquid import CANDLE_SOURCE_URL
from .td_sequential import calculate_td_sequential
from .td_retracement import calculate_td_retracement
from .td_scenarios import build_td_scenario
from .td_structure import calculate_td_structure


def generate_indicator_signal(
    asset: str,
    timeframe: str,
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float] | None = None,
    *,
    period: int = 14,
    observed_at: str | None = None,
) -> Signal:
    values = calculate_indicator_snapshot(highs, lows, closes, period=period)
    td = calculate_td_sequential(highs, lows, closes)
    td_structure = calculate_td_structure(highs, lows, closes)
    td_retracement = calculate_td_retracement(highs, lows, closes)
    td_scenario = build_td_scenario(
        demark_exhaustion=str(values["demark_exhaustion"]),
        demark_zone=str(values["demark_zone"]),
        td=td,
        structure=td_structure,
        retracement=td_retracement,
        close=float(closes[-1]),
    )
    demark_direction = str(values["demark_direction"])
    rei_direction = str(values["rei_direction"])
    td_direction = str(td["direction"])
    directions = [demark_direction, rei_direction, td_direction]
    directional_votes = [item for item in directions if item not in {"нейтральное", "конфликт"}]
    unique_votes = set(directional_votes)
    agreement = bool(directional_votes) and len(unique_votes) == 1
    direction = next((item for item in (demark_direction, rei_direction, td_direction) if item not in {"нейтральное", "конфликт"}), "нейтральное") if len(unique_votes) <= 1 else "нейтральное"
    indicator_weights = {"demark": 2, "rei": 1, "volume": 1, "td_sequential": 2}
    recent_volumes = list(volumes or [])[-21:]
    volume_baseline = median(recent_volumes[:-1]) if len(recent_volumes) >= 2 else 0.0
    volume_ratio = recent_volumes[-1] / volume_baseline if volume_baseline > 0 else 1.0
    volume_regime = "повышенный" if volume_ratio >= 1.5 else "пониженный" if volume_ratio <= 0.67 else "обычный"
    severity = "medium" if agreement else "low"
    confidence = 0.72 if agreement else 0.55
    basis = (
        f"Таймфрейм {timeframe}, период {period}: DeMarker={float(values['demark']):.3f} "
        f"→ зона «{values['demark_zone']}», направление «{demark_direction}», истощение «{values['demark_exhaustion']}»; "
        f"REI(8)={float(values['rei']):.1f} → зона «{values['rei_regime']}»; "
        f"Объём последней свечи: {volume_ratio:.2f}× к медиане предыдущих {max(len(recent_volumes) - 1, 0)} свечей → «{volume_regime}». "
        f"Направление DeMarker: {'подтверждено' if agreement else 'нейтрально'}. "
        f"REI направление «{rei_direction}». "
        f"TD Sequential (книга DeMark, Setup→Intersection→Countdown): {td['signal_state']}, направление «{td['direction']}», "
        f"Buy Setup {td['buy_setup_count']}/9, Sell Setup {td['sell_setup_count']}/9, "
        f"Buy Intersection={td['buy_intersection_confirmed']}, Sell Intersection={td['sell_intersection_confirmed']}, "
        f"Buy Countdown {td['buy_countdown']}/13, Sell Countdown {td['sell_countdown']}/13, "
        f"entry={td['entry_signal']}, exit={td['exit_signal']}, "
        f"buy-stop(TR)={td['buy_stop_loss_true_range']}, sell-stop(TR)={td['sell_stop_loss_true_range']}. "
        f"TD Lines: demand={td_structure['td_demand_line']}, supply={td_structure['td_supply_line']}, "
        f"breakouts demand={td_structure['demand_breakout']}, supply={td_structure['supply_breakout']}. "
        f"TD Retracement: 38.2%={td_retracement['retracement_382']}, "
        f"61.8%={td_retracement['retracement_618']}, zone={td_retracement['retracement_zone']}. "
        f"Scenario={td_scenario['scenario']}, qualified={td_scenario['qualified']}, "
        f"reason={td_scenario['reason']}, stop-reference={td_scenario['stop_reference']}."
    )
    return Signal(
        asset=asset,
        signal_type="multi_timeframe_indicators",
        fact=f"Индикаторы {asset} на {timeframe}: DeMarker — «{demark_direction}», общий вывод — «{direction}», объём — «{volume_regime}».",
        basis=basis,
        source_urls=[CANDLE_SOURCE_URL],
        severity=severity,
        confidence=confidence,
        possible_explanations=[
            "Индикаторы отражают прошлое движение цены и могут запаздывать",
            "Нейтральный или несогласованный набор индикаторов не подтверждает направление",
            "Повышенный объём подтверждает активность, но не направление движения",
        ],
        measurements={
            "timeframe": timeframe,
            "period": period,
            "demark": values["demark"],
            "demark_direction": demark_direction,
            "demark_zone": values["demark_zone"],
            "demark_exhaustion": values["demark_exhaustion"],
            "rei": values["rei"],
            "rei_period": values["rei_period"],
            "rei_regime": values["rei_regime"],
            "rei_direction": rei_direction,

            "volume_ratio": volume_ratio,
            "volume_regime": volume_regime,
            "direction_agreement": agreement,
            "direction_votes": directions,
            "td_sequential": td,
            "td_structure": td_structure,
            "td_retracement": td_retracement,
            "td_scenario": td_scenario,
            "indicator_weights": indicator_weights,
        },
        market_direction=direction,
        **({"observed_at": observed_at} if observed_at is not None else {}),
    )
