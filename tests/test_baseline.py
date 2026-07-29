import pytest

from crypto_radar.baseline import grade_against_history


def test_value_near_history_is_low():
    result = grade_against_history(10.2, [9.8, 10.0, 10.1, 10.3, 10.2])
    assert result.severity == "low"
    assert result.z_score < 2
    assert "среднее" in result.basis.lower()


def test_value_far_from_history_is_high():
    result = grade_against_history(20.0, [9.8, 10.0, 10.1, 10.3, 10.2])
    assert result.severity == "high"
    assert result.z_score > 3
    assert "стандартного отклонения" in result.basis.lower()


def test_short_history_is_explicitly_unavailable():
    result = grade_against_history(10.0, [9.9])
    assert result.severity == "low"
    assert result.z_score is None
    assert "недостаточно истории" in result.basis.lower()


def test_invalid_history_is_rejected():
    with pytest.raises(ValueError, match="finite"):
        grade_against_history(10.0, [10.0, float("nan")])
