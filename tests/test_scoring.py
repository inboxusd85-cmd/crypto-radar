from crypto_radar.scoring import score_anomaly

def test_normal_observation_does_not_alert():
    result = score_anomaly([100, 101, 99, 100, 100], 100)
    assert result.alert is False
    assert result.severity == "low"

def test_outlier_produces_high_alert():
    result = score_anomaly([100, 101, 99, 100, 100], 130)
    assert result.alert is True
    assert result.severity in {"medium", "high"}
    assert result.z_score > 3
