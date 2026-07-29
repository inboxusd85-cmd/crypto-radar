from crypto_radar.history import MetricHistory


def test_metric_history_round_trips_and_limits_window(tmp_path):
    history = MetricHistory(tmp_path / "history.sqlite3", max_samples=3)
    for value in [1.0, 2.0, 3.0, 4.0]:
        history.append("BTC", "funding_rate", value)
    assert history.values("BTC", "funding_rate") == [2.0, 3.0, 4.0]


def test_metrics_are_isolated_by_asset_and_name(tmp_path):
    history = MetricHistory(tmp_path / "history.sqlite3")
    history.append("BTC", "funding_rate", 1.0)
    history.append("ETH", "funding_rate", 2.0)
    history.append("BTC", "open_interest", 3.0)
    assert history.values("BTC", "funding_rate") == [1.0]
    assert history.values("ETH", "funding_rate") == [2.0]
    assert history.values("BTC", "open_interest") == [3.0]


def test_metric_history_retention_counts_duplicate_timestamps(tmp_path):
    history = MetricHistory(tmp_path / "history.sqlite3", max_samples=2)
    history.append("BTC", "mark_price", 101, observed_at=1)
    history.append("BTC", "mark_price", 102, observed_at=1)
    history.append("BTC", "mark_price", 103, observed_at=1)

    assert history.values("BTC", "mark_price") == [102.0, 103.0]
