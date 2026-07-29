from crypto_radar.events import AlertEventJournal
from crypto_radar.models import Signal


def signal(observed_at="2026-07-20T12:00:00Z"):
    return Signal(
        asset="HYPE", signal_type="social_claim", fact="Risk claim", basis="raw=0.7; weighted=0.5",
        source_urls=["https://x.com/a/1"], confidence=0.5,
        measurements={"evidence_count": 1, "confidence_model": "social-quality-v1", "confidence_components": {"raw": 0.7}},
        observed_at=observed_at,
    )


def test_record_many_reports_recorded_and_duplicates(tmp_path):
    journal = AlertEventJournal(tmp_path / "events.sqlite3")
    stats = journal.record_many([signal(), signal(), signal("2026-07-20T13:00:00Z")])
    assert stats == {"attempted": 3, "recorded": 2, "duplicates_skipped": 1}
