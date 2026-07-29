from crypto_radar.cli import format_events
from crypto_radar.events import AlertEventJournal
from crypto_radar.models import Signal
import json


def signal(asset="HYPE", severity="high"):
    return Signal(
        asset=asset, signal_type="composite_market_risk", fact="fact", basis="basis",
        source_urls=["https://example.com"], severity=severity, confidence=0.8,
        observed_at="2026-07-20T12:00:00Z",
        measurements={"factor_signature": "funding_rate=low"},
    )


def test_record_and_list_events_round_trip(tmp_path):
    journal = AlertEventJournal(tmp_path / "alerts.sqlite3")
    journal.record(signal(), recorded_at=1000)
    events = journal.list_events()
    assert len(events) == 1
    assert events[0]["asset"] == "HYPE"
    assert events[0]["signal_id"] == signal().signal_id
    assert events[0]["observed_at"] == "2026-07-20T12:00:00Z"
    assert events[0]["event_id"]


def test_same_signal_can_be_recorded_again_as_new_event(tmp_path):
    journal = AlertEventJournal(tmp_path / "alerts.sqlite3")
    assert journal.record(signal(), recorded_at=1000) is True
    assert journal.record(signal(), recorded_at=2000) is True
    events = journal.list_events()
    assert len(events) == 2
    assert events[0]["event_id"] != events[1]["event_id"]
    assert all(item["signal_id"] == signal().signal_id for item in events)


def test_list_events_filters_asset_and_limits(tmp_path):
    journal = AlertEventJournal(tmp_path / "alerts.sqlite3")
    journal.record(signal("HYPE"), recorded_at=1000)
    journal.record(signal("ZEC"), recorded_at=2000)
    assert [item["asset"] for item in journal.list_events(asset="ZEC")] == ["ZEC"]
    assert len(journal.list_events(limit=1)) == 1


def test_format_events_supports_json_and_markdown():
    event = {"asset": "HYPE", "severity": "high", "signal_id": "abc123", "event_id": "evt1", "observed_at": "2026-07-20T12:00:00Z"}
    assert json.loads(format_events([event], "json"))[0]["signal_id"] == "abc123"
    assert "HYPE HIGH abc123" in format_events([event], "markdown")
