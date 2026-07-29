from crypto_radar.source_reputation import SourceReputationStore


def test_new_author_starts_with_neutral_reputation(tmp_path):
    store = SourceReputationStore(tmp_path / "reputation.sqlite3")
    record = store.get("alice")
    assert record["author_handle"] == "alice"
    assert record["score"] == 0.5
    assert record["confirmed"] == 0
    assert record["refuted"] == 0


def test_confirmed_and_refuted_outcomes_update_persisted_score(tmp_path):
    path = tmp_path / "reputation.sqlite3"
    store = SourceReputationStore(path)
    confirmed = store.record_outcome("alice", "confirmed")
    assert confirmed["score"] > 0.5
    assert confirmed["confirmed"] == 1
    refuted = store.record_outcome("alice", "refuted")
    assert refuted["score"] < confirmed["score"]
    assert refuted["refuted"] == 1
    reopened = SourceReputationStore(path)
    assert reopened.get("alice") == refuted


def test_uncertain_does_not_change_score_and_score_is_bounded(tmp_path):
    store = SourceReputationStore(tmp_path / "reputation.sqlite3")
    initial = store.get("alice")
    unchanged = store.record_outcome("alice", "uncertain")
    assert unchanged["score"] == initial["score"]
    with_error = None
    try:
        store.record_outcome("alice", "invalid")
    except ValueError as error:
        with_error = error
    assert with_error is not None
    for _ in range(30):
        store.record_outcome("alice", "confirmed")
    assert 0.0 <= store.get("alice")["score"] <= 1.0
