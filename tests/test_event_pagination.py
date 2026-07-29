from crypto_radar.events import AlertEventJournal
from crypto_radar.models import Signal


def signal(asset: str, severity: str, observed_at: str) -> Signal:
    return Signal(asset, "composite_market_risk", "fact", "basis", ["https://example.com"], severity=severity, observed_at=observed_at)


def test_event_page_filters_severity_and_uses_recorded_at_cursor(tmp_path):
    journal = AlertEventJournal(tmp_path / "events.sqlite3")
    journal.record(signal("BTC", "low", "2026-07-21T10:00:00Z"), recorded_at=10.0)
    journal.record(signal("BTC", "high", "2026-07-21T10:01:00Z"), recorded_at=20.0)
    journal.record(signal("ETH", "high", "2026-07-21T10:02:00Z"), recorded_at=30.0)

    page = journal.list_events_page(severity="high", limit=1)

    assert [event["asset"] for event in page["events"]] == ["ETH"]
    assert page["next_before"] == 30.0
    older = journal.list_events_page(severity="high", before=page["next_before"], limit=1)
    assert [event["asset"] for event in older["events"]] == ["BTC"]


def test_event_cursor_keeps_events_with_equal_recorded_at(tmp_path):
    journal = AlertEventJournal(tmp_path / "events.sqlite3")
    journal.record(signal("BTC", "high", "2026-07-21T10:00:00Z"), recorded_at=20.0)
    journal.record(signal("ETH", "high", "2026-07-21T10:01:00Z"), recorded_at=20.0)

    first = journal.list_events_page(severity="high", limit=1)
    second = journal.list_events_page(severity="high", cursor=first["next_cursor"], limit=1)

    assert len(first["events"]) == 1
    assert len(second["events"]) == 1
    assert second["events"][0]["event_id"] != first["events"][0]["event_id"]
