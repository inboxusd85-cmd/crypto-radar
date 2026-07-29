from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineGrade:
    severity: str
    z_score: float | None
    mean: float | None
    standard_deviation: float | None
    basis: str


def grade_against_history(value: float, history: list[float], minimum_samples: int = 3) -> BaselineGrade:
    values = [float(item) for item in history]
    if not math.isfinite(value) or any(not math.isfinite(item) for item in values):
        raise ValueError("all baseline values must be finite")
    if len(values) < minimum_samples:
        return BaselineGrade(
            severity="low",
            z_score=None,
            mean=None,
            standard_deviation=None,
            basis=f"Недостаточно истории: доступно {len(values)} наблюдений, требуется {minimum_samples}.",
        )
    mean = sum(values) / len(values)
    variance = sum((item - mean) ** 2 for item in values) / len(values)
    standard_deviation = math.sqrt(variance)
    if standard_deviation == 0:
        z_score = 0.0 if value == mean else float("inf")
    else:
        z_score = abs(value - mean) / standard_deviation
    if z_score >= 3:
        severity = "high"
    elif z_score >= 2:
        severity = "medium"
    else:
        severity = "low"
    basis = (
        f"Текущее значение {value:g}; историческое среднее {mean:.6g}; стандартное отклонение "
        f"{standard_deviation:.6g}; отклонение составляет {z_score:.2f} стандартного отклонения."
    )
    return BaselineGrade(severity, z_score, mean, standard_deviation, basis)
