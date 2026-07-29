from crypto_radar.events import AlertEventJournal
from crypto_radar.models import Signal


def signal(observed_at):
    return Signal(
        asset="HYPE", signal_type="social_claim", fact="Risk claim", basis=f"obs={observed_at}",
        source_urls=["https://x.com/a/1"], confidence=0.5,
        measurements={"evidence_count": 1, "confidence_model": "social-quality-v1", "confidence_components": {"raw": 0.7}},
        observed_at=observed_at,
    )


def test_record_many_accepts_deterministic_recorded_at(tmp_path):
    journal = AlertEventJournal(tmp_path / "events.sqlite3")
    journal.record_many([signal("2026-07-20T12:00:00Z")], recorded_at=1234.5)
    event = journal.list_events(limit=1)[0]
    assert event["recorded_at"] == 1234.5
