import json

from crypto_radar.db import SignalStore
from crypto_radar.models import Signal


def test_signal_store_round_trips_and_deduplicates(tmp_path):
    store = SignalStore(tmp_path / "radar.sqlite3")
    signal = Signal(
        asset="BTC",
        signal_type="volume_anomaly",
        fact="Volume is elevated",
        basis="Volume is 4.2 standard deviations above the baseline.",
        source_urls=["https://example.com/source"],
        confidence=0.8,
        measurements={"z_score": 4.2},
    )

    first = store.save(signal)
    second = store.save(signal)

    assert first.inserted is True
    assert second.inserted is False
    loaded = store.get(first.signal_id)
    assert loaded["asset"] == "BTC"
    assert loaded["measurements"] == {"z_score": 4.2}


def test_raw_payload_is_stored_exactly_once(tmp_path):
    store = SignalStore(tmp_path / "radar.sqlite3")
    payload = {"symbol": "BTCUSDT", "volume": 123.45}
    first = store.save_raw(payload)
    second = store.save_raw(payload)

    assert first.inserted is True
    assert second.inserted is False
    assert json.loads(store.get_raw(first.payload_id)["payload"]) == payload
