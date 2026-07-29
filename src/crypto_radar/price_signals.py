from __future__ import annotations

from .models import Signal
from .providers.hyperliquid import MarketSnapshot, SOURCE_URL


def generate_price_change_signal(snapshot: MarketSnapshot, previous_mark_price: float | None) -> Signal:
    if previous_mark_price is None or previous_mark_price <= 0:
        change_percent = 0.0
        severity = "low"
        confidence = 0.45
        basis = "Insufficient history: no previous mark price is available for comparison."
        direction = "unknown"
    else:
        change_percent = (snapshot.mark_price - previous_mark_price) / previous_mark_price * 100
        absolute_change = abs(change_percent)
        if absolute_change >= 10:
            severity, confidence = "high", 0.9
        elif absolute_change >= 5:
            severity, confidence = "medium", 0.75
        else:
            severity, confidence = "low", 0.6
        direction = "рост" if change_percent > 0 else "снижение" if change_percent < 0 else "боковое движение"
        basis = (
            f"Цена mark изменилась в направлении «{direction}» на {change_percent:+.2f}%: "
            f"{previous_mark_price:g} → {snapshot.mark_price:g}. Порог оценки: low < 5%, medium < 10%, high >= 10%."
        )
    return Signal(
        asset=snapshot.asset,
        signal_type="mark_price_change",
        fact=f"Цена mark: {direction} на {abs(change_percent):.2f}% относительно прошлого наблюдения.",
        basis=basis,
        source_urls=[SOURCE_URL],
        severity=severity,
        confidence=confidence,
        possible_explanations=["Поступление новой информации на рынок", "Ликвидации или ребалансировка позиций", "Краткосрочная волатильность"],
        market_direction=direction if direction in {"рост", "снижение"} else "нейтральное",
        measurements={"mark_price": snapshot.mark_price, "previous_mark_price": previous_mark_price, "change_percent": change_percent},
    )
