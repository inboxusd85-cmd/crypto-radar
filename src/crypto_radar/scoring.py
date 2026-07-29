from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True)
class AnomalyScore:
    z_score: float
    alert: bool
    severity: str
    reason: str


def score_anomaly(history: list[float], current: float) -> AnomalyScore:
    if len(history) < 2:
        raise ValueError("at least two historical observations are required")
    mean = sum(history) / len(history)
    variance = sum((value - mean) ** 2 for value in history) / len(history)
    stddev = sqrt(variance)
    if stddev == 0:
        z_score = 0.0 if current == mean else float("inf")
    else:
        z_score = abs(current - mean) / stddev
    if z_score >= 4:
        severity = "high"
    elif z_score >= 3:
        severity = "medium"
    else:
        severity = "low"
    return AnomalyScore(
        z_score=z_score,
        alert=severity != "low",
        severity=severity,
        reason=f"current={current:g}, mean={mean:g}, z_score={z_score:.2f}",
    )
