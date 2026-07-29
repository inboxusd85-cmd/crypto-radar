from __future__ import annotations

from .baseline import grade_against_history
from .models import Signal
from .providers.hyperliquid import MarketSnapshot, SOURCE_URL


def generate_funding_signal(
    snapshot: MarketSnapshot,
    funding_history: list[float] | None = None,
) -> Signal:
    funding = snapshot.funding_rate
    absolute = abs(funding)
    baseline = grade_against_history(funding, funding_history) if funding_history is not None else None
    if baseline is not None and baseline.z_score is not None:
        severity = baseline.severity
        confidence = {"low": 0.65, "medium": 0.8, "high": 0.92}[severity]
        basis = f"Финансирование {'положительное' if funding > 0 else 'отрицательное' if funding < 0 else 'нейтральное'}: {funding:.8f} за интервал. {baseline.basis}"
        z_score = baseline.z_score
    else:
        if absolute >= 0.00075:
            severity = "high"
            confidence = 0.9
        elif absolute >= 0.00025:
            severity = "medium"
            confidence = 0.75
        else:
            severity = "low"
            confidence = 0.6
        direction = "положительное" if funding > 0 else "отрицательное" if funding < 0 else "нейтральное"
        basis = (
            f"Финансирование {direction}: {funding:.8f} за интервал; "
            f"абсолютное значение: {absolute:.8f}. "
            f"Порог оценки: low < 0.00025, medium < 0.00075, high >= 0.00075."
        )
        if baseline is not None:
            basis += f" {baseline.basis}"
        z_score = None
    measurements = {
        "mark_price": snapshot.mark_price,
        "funding_rate": funding,
        "open_interest": snapshot.open_interest,
        "day_notional_volume": snapshot.day_notional_volume,
    }
    if z_score is not None:
        measurements["z_score"] = z_score
    return Signal(
        asset=snapshot.asset,
        signal_type="funding_rate",
        fact=f"Ставка финансирования Hyperliquid для {snapshot.asset}: {funding:.8f} за интервал.",
        basis=basis,
        source_urls=[SOURCE_URL],
        severity=severity,
        confidence=confidence,
        possible_explanations=[
            "Дисбаланс позиций на рынке perpetual-контрактов",
            "Временный спрос на кредитное плечо",
            "Нормализация funding может произойти без движения цены",
        ],
        market_direction="снижение" if funding > 0 else "рост" if funding < 0 else "нейтральное",
        measurements=measurements,
    )
