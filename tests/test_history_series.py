from pathlib import Path

from crypto_radar.history import MetricHistory


def test_metric_history_returns_bounded_series_with_timestamps(tmp_path: Path) -> None:
    history = MetricHistory(tmp_path / "history.sqlite3", max_samples=3)
    for timestamp, value in [(1, 10), (2, 20), (3, 30), (4, 40)]:
        history.append("BTC", "mark_price", value, observed_at=timestamp)

    assert history.series("BTC", "mark_price", limit=2) == [
        {"observed_at": 3.0, "value": 30.0},
        {"observed_at": 4.0, "value": 40.0},
    ]

def test_metric_history_rejects_invalid_limit(tmp_path: Path) -> None:
    history = MetricHistory(tmp_path / "history.sqlite3")

    try:
        history.series("BTC", "mark_price", limit=0)
    except ValueError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("expected invalid limit to fail")
