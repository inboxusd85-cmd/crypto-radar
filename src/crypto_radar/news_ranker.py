from __future__ import annotations

import math

from dataclasses import dataclass
from typing import Protocol, Sequence

from .news_scoring import _extract_evidence, score_news


@dataclass(frozen=True)
class NewsFeatures:
    positive_markers: float = 0.0
    negative_markers: float = 0.0
    source_reliability: float = 0.5
    freshness_hours: float = 24.0
    asset_match: float = 1.0

    def vector(self) -> list[float]:
        return [self.positive_markers, self.negative_markers, self.source_reliability, self.freshness_hours, self.asset_match]


def extract_news_features(title: str, summary: str = "") -> NewsFeatures:
    positive, negative, _ = _extract_evidence(title, summary)
    return NewsFeatures(
        positive_markers=float(positive),
        negative_markers=float(negative),
    )


class NewsRanker(Protocol):
    model_name: str

    def predict(self, features: Sequence[NewsFeatures]) -> list[float]: ...


class RuleBasedNewsRanker:
    model_name = "rules-v1"

    def predict(self, features: Sequence[NewsFeatures]) -> list[float]:
        return [
            max(-10.0, min(10.0, item.positive_markers - item.negative_markers))
            for item in features
        ]


class XGBoostNewsRanker:
    model_name = "xgboost-news-v1"

    def __init__(self, model: object):
        if not hasattr(model, "predict"):
            raise TypeError("model must provide predict")
        self.model = model

    def predict(self, features: Sequence[NewsFeatures]) -> list[float]:
        values = [item.vector() for item in features]
        raw = self.model.predict(values)
        if len(raw) != len(values):
            raise ValueError("prediction count must match feature count")
        predictions = [float(value) for value in raw]
        if not all(math.isfinite(value) for value in predictions):
            raise ValueError("predictions must be finite")
        return [max(-10.0, min(10.0, value)) for value in predictions]


def rank_news(title: str, summary: str = "", ranker: NewsRanker | None = None) -> dict[str, object]:
    baseline = score_news(title, summary)
    if ranker is None:
        return {**baseline, "model": RuleBasedNewsRanker.model_name, "confidence": None}
    positive, negative, numbers = _extract_evidence(title, summary)
    features = NewsFeatures(float(positive), float(negative))
    prediction = ranker.predict([features])[0]
    score = int(round(prediction))
    label = "нейтрально" if score == 0 else "позитивно" if score > 0 else "негативно"
    return {
        "score": score,
        "label": label,
        "basis": f"Оценка модели {ranker.model_name}; Итоговая оценка: {score}/10; baseline: {baseline['score']}/10; features: positive={positive}, negative={negative}, numeric={', '.join(numbers[:4]) if numbers else 'нет'}.",
        "model": ranker.model_name,
        "confidence": None,
        "features": features.vector(),
    }