from crypto_radar.events import AlertEventJournal
from crypto_radar.models import Signal


def make_signal(observed_at):
    return Signal(
        asset="HYPE", signal_type="social_claim", fact="Risk claim", basis="raw=0.7; weighted=0.5",
        source_urls=["https://x.com/a/1"], severity="medium", confidence=0.5,
        measurements={"evidence_count": 1, "confidence_model": "social-quality-v1", "confidence_components": {"raw": 0.7}},
        observed_at=observed_at,
    )


def test_event_record_is_idempotent_for_signal_and_observed_at(tmp_path):
    journal = AlertEventJournal(tmp_path / "events.sqlite3")
    signal = make_signal("2026-07-20T12:00:00Z")
    assert journal.record(signal)
    assert not journal.record(signal)
    assert len(journal.list_events(limit=10)) == 1


def test_new_observation_is_recorded_as_new_event(tmp_path):
    journal = AlertEventJournal(tmp_path / "events.sqlite3")
    assert journal.record(make_signal("2026-07-20T12:00:00Z"))
    assert journal.record(make_signal("2026-07-20T13:00:00Z"))
    assert len(journal.list_events(limit=10)) == 2
