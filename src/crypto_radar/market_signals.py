from __future__ import annotations

from .baseline import grade_against_history
from .models import Signal
from .providers.hyperliquid import MarketSnapshot, SOURCE_URL

MARK_MID_MEDIUM_BPS = 20.0
MARK_MID_HIGH_BPS = 40.0
OI_TURNOVER_MEDIUM = 1.0
OI_TURNOVER_HIGH = 0.5


def generate_basis_signals(
    snapshot: MarketSnapshot,
    spread_history: list[float] | None = None,
    turnover_history: list[float] | None = None,
) -> list[Signal]:
    if snapshot.mid_price is None or snapshot.mark_price <= 0:
        spread_bps = 0.0
    else:
        spread_bps = abs(snapshot.mark_price - snapshot.mid_price) / snapshot.mark_price * 10_000
    spread_baseline = grade_against_history(spread_bps, spread_history) if spread_history is not None else None
    if spread_baseline is not None and spread_baseline.z_score is not None:
        spread_severity = spread_baseline.severity
        spread_confidence = {"low": 0.65, "medium": 0.8, "high": 0.92}[spread_severity]
        spread_basis = f"Спред mark/mid: {spread_baseline.basis}"
    else:
        if spread_bps >= MARK_MID_HIGH_BPS:
            spread_severity, spread_confidence = "high", 0.9
        elif spread_bps >= MARK_MID_MEDIUM_BPS:
            spread_severity, spread_confidence = "medium", 0.75
        else:
            spread_severity, spread_confidence = "low", 0.6
        spread_basis = (
            f"Спред mark/mid: абсолютная разница между mark price ({snapshot.mark_price:g}) и mid price "
            f"({snapshot.mid_price:g}) составляет {spread_bps:.2f} bps. "
            f"Порог оценки: low < {MARK_MID_MEDIUM_BPS:g}, medium < {MARK_MID_HIGH_BPS:g}, high >= {MARK_MID_HIGH_BPS:g} bps."
        )
        if spread_baseline is not None:
            spread_basis += f" {spread_baseline.basis}"
    spread_measurements = {"spread_bps": spread_bps, "mark_price": snapshot.mark_price, "mid_price": snapshot.mid_price}
    if spread_baseline is not None and spread_baseline.z_score is not None:
        spread_measurements["z_score"] = spread_baseline.z_score
    spread_signal = Signal(
        asset=snapshot.asset, signal_type="mark_mid_spread",
        fact=f"Спред mark/mid для {snapshot.asset}: {spread_bps:.2f} bps.",
        basis=spread_basis, source_urls=[SOURCE_URL], severity=spread_severity, confidence=spread_confidence,
        possible_explanations=["Дисбаланс книги заявок", "Временный дефицит ликвидности", "Корректировка индекса или mark price"],
        measurements=spread_measurements,
        market_direction="нейтральное",
    )

    open_interest_notional = snapshot.open_interest * snapshot.mark_price
    turnover_ratio = snapshot.day_notional_volume / open_interest_notional if open_interest_notional > 0 else 0.0
    turnover_baseline = grade_against_history(turnover_ratio, turnover_history) if turnover_history is not None else None
    if turnover_baseline is not None and turnover_baseline.z_score is not None:
        oi_severity = turnover_baseline.severity
        oi_confidence = {"low": 0.65, "medium": 0.8, "high": 0.92}[oi_severity]
        oi_basis = f"Базовый уровень оборота: {turnover_baseline.basis}"
    else:
        if turnover_ratio <= OI_TURNOVER_HIGH:
            oi_severity, oi_confidence = "high", 0.85
        elif turnover_ratio <= OI_TURNOVER_MEDIUM:
            oi_severity, oi_confidence = "medium", 0.7
        else:
            oi_severity, oi_confidence = "low", 0.6
        oi_basis = (
            f"Объём за 24 часа ({snapshot.day_notional_volume:g}), делённый на номинальный open interest "
            f"({open_interest_notional:g}), равен {turnover_ratio:.4f}x. Низкий оборот означает менее частое "
            f"перераспределение позиций. Порог оценки: high <= {OI_TURNOVER_HIGH:.2f}x, "
            f"medium <= {OI_TURNOVER_MEDIUM:.2f}x, low > {OI_TURNOVER_MEDIUM:.2f}x."
        )
        if turnover_baseline is not None:
            oi_basis += f" {turnover_baseline.basis}"
    oi_measurements = {"open_interest": snapshot.open_interest, "open_interest_notional": open_interest_notional, "day_notional_volume": snapshot.day_notional_volume, "turnover_ratio": turnover_ratio}
    if turnover_baseline is not None and turnover_baseline.z_score is not None:
        oi_measurements["z_score"] = turnover_baseline.z_score
    oi_signal = Signal(
        asset=snapshot.asset, signal_type="open_interest_turnover",
        fact=f"Оборот объёма за 24 часа к номинальному open interest для {snapshot.asset}: {turnover_ratio:.4f}x.",
        basis=oi_basis, source_urls=[SOURCE_URL], severity=oi_severity, confidence=oi_confidence,
        possible_explanations=["Устойчивое позиционирование с кредитным плечом", "Низкий оборот относительно открытых позиций", "Смена рыночного режима"],
        measurements=oi_measurements,
        market_direction="нейтральное",
    )
    return [spread_signal, oi_signal]
