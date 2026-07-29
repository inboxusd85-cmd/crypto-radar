from __future__ import annotations

from collections.abc import Sequence

from .indicator_aggregation import aggregate_indicator_signals
from .models import Signal
from .providers.hyperliquid import CANDLE_SOURCE_URL


def generate_indicator_consensus_signal(asset: str, observations: Sequence[dict]) -> Signal | None:
    if not observations:
        return None
    aggregate = aggregate_indicator_signals(observations)

    elevated_volume_frames = [
        str(item.get("timeframe"))
        for item in observations
        if item.get("volume_regime") == "повышенный"
    ]
    signal_quality = int(aggregate["signal_quality"])
    severity = "medium" if signal_quality >= 75 else "low"
    confidence = signal_quality / 100
    confirmed = aggregate["confirmed_timeframes"]
    volume_context = ", ".join(elevated_volume_frames) if elevated_volume_frames else "нет"
    return Signal(
        asset=asset,
        signal_type="multi_timeframe_consensus",
        fact=(
            f"Сводка индикаторов {asset}: направление «{aggregate['market_direction']}», "
            f"подтверждённые таймфреймы: "
            f"{', '.join(confirmed) if confirmed else 'нет'}; повышенный объём: {volume_context}."
        ),
        basis=(
            f"{aggregate['basis']} Независимые веса индикаторов: {aggregate['indicator_weights']}; "
            f"оценки по индикаторам: {aggregate['indicator_scores']}. Качество сигнала: {signal_quality}/100 ({aggregate['quality_label']}); "
            f"компоненты: {aggregate['quality_components']}. "
            f"Повышенный объём отмечен на: {volume_context}. Medium назначается только при качестве не ниже 75/100; "
            f"иначе low."
        ),
        source_urls=[CANDLE_SOURCE_URL],
        severity=severity,
        confidence=confidence,
        possible_explanations=[
            "Конфликт между таймфреймами снижает достоверность направленного вывода",
            "Повышенный объём подтверждает активность, но не направление движения",
            "Индикаторы рассчитываются по закрытым свечам и могут запаздывать",
        ],
        measurements={
            "timeframe_count": len(observations),
            "confirmed_timeframes": confirmed,
            "direction_agreement": aggregate["direction_agreement"],
            "timeframe_weights": aggregate["timeframe_weights"],
            "directional_scores": aggregate["directional_scores"],
            "indicator_weights": aggregate["indicator_weights"],
            "indicator_scores": aggregate["indicator_scores"],
            "horizons": aggregate["horizons"],
            "market_regime": aggregate["market_regime"],
            "data_quality": aggregate["data_quality"],
            "timeframe_reliability": aggregate["timeframe_reliability"],
            "td_scenario_summary": aggregate["td_scenario_summary"],
            "demark_context": aggregate["demark_context"],
            "direction_score": aggregate["direction_score"],
            "signal_quality": signal_quality,
            "quality_label": aggregate["quality_label"],
            "quality_components": aggregate["quality_components"],

            "elevated_volume_timeframes": elevated_volume_frames,
        },
        market_direction=str(aggregate["market_direction"]),
    )
