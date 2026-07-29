from crypto_radar.deduplication import AlertDeduplicator
from crypto_radar.models import Signal


def signal(severity="high", basis="same basis", signal_type="composite_market_risk"):
    return Signal(
        asset="HYPE", signal_type=signal_type, fact="fact", basis=basis,
        source_urls=[], severity=severity, confidence=0.8,
        measurements={"factors": "funding_rate=low; turnover=high"},
    )


def test_first_signal_is_emitted_and_identical_signal_is_suppressed(tmp_path):
    dedup = AlertDeduplicator(tmp_path / "alerts.sqlite3", cooldown_seconds=3600)
    assert dedup.should_emit(signal(), now=1000) is True
    assert dedup.should_emit(signal(basis="same basis with new price 61.9"), now=1001) is False


def test_changed_severity_or_factor_set_is_emitted(tmp_path):
    dedup = AlertDeduplicator(tmp_path / "alerts.sqlite3", cooldown_seconds=3600)
    assert dedup.should_emit(signal(), now=1000) is True
    assert dedup.should_emit(signal("medium"), now=1001) is True
    assert dedup.should_emit(signal("medium", signal_type="different_composite"), now=1002) is True


def test_same_signal_is_emitted_after_cooldown(tmp_path):
    dedup = AlertDeduplicator(tmp_path / "alerts.sqlite3", cooldown_seconds=60)
    assert dedup.should_emit(signal(), now=1000) is True
    assert dedup.should_emit(signal(), now=1059) is False
    assert dedup.should_emit(signal(), now=1060) is True
