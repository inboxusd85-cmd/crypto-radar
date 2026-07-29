import math

import pytest

from crypto_radar.news_ranker import NewsFeatures, RuleBasedNewsRanker, XGBoostNewsRanker, extract_news_features, rank_news


class EmptyModel:
    def predict(self, values):
        return []


class NonFiniteModel:
    def __init__(self, value):
        self.value = value

    def predict(self, values):
        return [self.value]


def test_xgboost_adapter_rejects_empty_prediction() -> None:
    ranker = XGBoostNewsRanker(EmptyModel())
    with pytest.raises(ValueError, match="prediction count"):
        ranker.predict([NewsFeatures()])


def test_xgboost_adapter_rejects_non_finite_prediction() -> None:
    ranker = XGBoostNewsRanker(NonFiniteModel(float("nan")))
    with pytest.raises(ValueError, match="finite"):
        ranker.predict([NewsFeatures()])




class FakeModel:
    def predict(self, values):
        assert len(values) == 1
        return [-12.5]


def test_rule_ranker_preserves_neutral_baseline() -> None:
    assert rank_news("Routine update", "Stable", RuleBasedNewsRanker())["score"] == 0


def test_ranker_uses_same_clean_text_and_numeric_policy_as_baseline() -> None:
    features = extract_news_features(
        "Bitcoin update <img width=1672 height=941> published 2026 https://example.com/125",
        "Partnership growth; indicator 0.03; adoption increased 18%.",
    )

    assert features.positive_markers == 3.0
    assert features.negative_markers == 0.0


def test_xgboost_adapter_clamps_prediction_to_ten() -> None:
    ranker = XGBoostNewsRanker(FakeModel())
    assert ranker.predict([NewsFeatures()]) == [-10.0]
    assert rank_news("Any", ranker=ranker)["model"] == "xgboost-news-v1"
    assert rank_news("Any", ranker=ranker)["features"] == [0.0, 0.0, 0.5, 24.0, 1.0]



def test_rank_news_passes_content_features_to_xgboost_model() -> None:
    captured: list[list[float]] = []

    class CapturingModel:
        def predict(self, values):
            captured.extend(values)
            return [7.0]

    result = rank_news(
        "Bitcoin ETF outflows",
        "$125 million outflow, down 18%",
        XGBoostNewsRanker(CapturingModel()),
    )

    assert result["score"] == 7
    assert "Итоговая оценка: 7/10" in result["basis"]
    assert captured[0][0] == 0
    assert captured[0][1] > 0
    assert captured[0][2:] == [0.5, 24.0, 1.0]
