from __future__ import annotations

from .indicator_aggregation import TIMEFRAME_WEIGHTS
from .models import Signal

_ORDER = {"low": 0, "medium": 1, "high": 2}


def aggregate_signals(signals: list[Signal], observed_at: str | None = None) -> Signal:
    if not signals:
        raise ValueError("at least one signal is required")
    def timeframe_weight(signal: Signal) -> int:
        timeframe = str(signal.measurements.get("timeframe", ""))
        return TIMEFRAME_WEIGHTS.get(timeframe, 0)

    ordered = sorted(
        signals,
        key=lambda signal: (_ORDER[signal.severity], timeframe_weight(signal), signal.confidence),
        reverse=True,
    )
    strongest = ordered[0]
    severity_counts = {severity: sum(signal.severity == severity for signal in signals) for severity in _ORDER}
    severity = "high" if severity_counts["high"] or severity_counts["medium"] >= 2 else "medium" if severity_counts["medium"] else "low"
    directions = {
        signal.market_direction
        for signal in signals
        if signal.market_direction in {"рост", "снижение"}
    }
    market_direction = directions.pop() if len(directions) == 1 else "нейтральное" if directions else "неопределённое"
    factor_signature = "; ".join(f"{signal.signal_type}={signal.severity}" for signal in signals)
    drivers = [
        {
            "priority": index,
            "timeframe": signal.measurements.get("timeframe"),
            "priority_points": timeframe_weight(signal),
            "role": "ключевой драйвер" if index == 1 else "подтверждающий фактор" if signal.severity != "low" else "контекстный фактор",
            "signal_type": signal.signal_type,
            "signal_class": signal.signal_class,
            "severity": signal.severity,
            "confidence": signal.confidence,
            "market_direction": signal.market_direction,
            "fact": signal.fact,
            "basis": signal.basis,
        }
        for index, signal in enumerate(ordered, start=1)
    ]
    factor_summary = ", ".join(f"{driver['signal_type']}={driver['severity']}" for driver in drivers)
    driver_basis = "; ".join(f"{driver['signal_type']}={driver['severity']}: {driver['basis']}" for driver in drivers)
    evidence_class_summary: dict[str, dict[str, int]] = {}
    for driver in drivers:
        bucket = evidence_class_summary.setdefault(driver["signal_class"], {"count": 0, "priority_points": 0})
        bucket["count"] += 1
        bucket["priority_points"] += int(driver["priority_points"])
    technical = next((signal for signal in signals if signal.signal_type == "multi_timeframe_consensus"), None)
    technical_forecast = dict(technical.measurements) if technical is not None else None
    return Signal(
        asset=strongest.asset,
        signal_type="composite_market_risk",
        fact=f"Для {strongest.asset} оценены {len(signals)} рыночных факторов: {factor_summary}.",
        basis=(
            f"Оценены {len(signals)} факторов. Итоговая оценка: {severity}. Расчёт: high при хотя бы одном high-факторе или двух и более medium-факторах; "
            f"medium при одном medium-факторе; иначе low. Направление рынка: {market_direction}. "
            f"Приоритетные драйверы: {driver_basis}. Направление является оценкой по доступным данным и требует ручной проверки."
        ),
        source_urls=sorted({url for signal in signals for url in signal.source_urls}),
        severity=severity,
        confidence=max(signal.confidence for signal in ordered),
        possible_explanations=sorted({item for signal in signals for item in signal.possible_explanations}),
        measurements={
            "factor_count": len(signals),
            "factor_signature": factor_signature,
            "severity_counts": severity_counts,
            "timeframe_weights": {
                str(signal.measurements["timeframe"]): timeframe_weight(signal)
                for signal in signals
                if signal.measurements.get("timeframe") in TIMEFRAME_WEIGHTS
            },
            "drivers": drivers,
            "evidence_class_summary": evidence_class_summary,
            "technical_forecast": technical_forecast,
        },
        market_direction=market_direction,
        **({"observed_at": observed_at} if observed_at is not None else {}),
    )
