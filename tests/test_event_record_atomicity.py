import sqlite3

import pytest

from crypto_radar.events import AlertEventJournal
from crypto_radar.models import Signal


def signal(observed_at):
    return Signal(
        asset="HYPE", signal_type="social_claim", fact="Risk claim", basis=f"obs={observed_at}",
        source_urls=["https://x.com/a/1"], confidence=0.5,
        measurements={"evidence_count": 1, "confidence_model": "social-quality-v1", "confidence_components": {"raw": 0.7}},
        observed_at=observed_at,
    )


def test_record_many_rolls_back_entire_batch_on_unexpected_failure(tmp_path):
    path = tmp_path / "events.sqlite3"
    journal = AlertEventJournal(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TRIGGER fail_second_social_insert "
            "BEFORE INSERT ON alert_events WHEN NEW.observed_at = '2026-07-20T13:00:00Z' "
            "BEGIN SELECT RAISE(ABORT, 'synthetic batch failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="synthetic batch failure"):
        journal.record_many([signal("2026-07-20T12:00:00Z"), signal("2026-07-20T13:00:00Z")])
    assert journal.list_events(limit=10) == []
