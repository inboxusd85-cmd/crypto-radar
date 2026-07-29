from crypto_radar.source_reputation import SourceReputationStore


def test_outcome_is_persisted_with_audit_context(tmp_path):
    store = SourceReputationStore(tmp_path / "reputation.sqlite3")
    record = store.record_outcome(
        "Alice", "confirmed", reference="https://x.com/alice/status/1", note="Official update matched on-chain data"
    )
    assert record["score"] > 0.5
    outcomes = store.list_outcomes("alice")
    assert len(outcomes) == 1
    assert outcomes[0]["author_handle"] == "alice"
    assert outcomes[0]["outcome"] == "confirmed"
    assert outcomes[0]["reference"] == "https://x.com/alice/status/1"
    assert outcomes[0]["note"] == "Official update matched on-chain data"
    assert outcomes[0]["outcome_id"]


def test_uncertain_outcome_is_audited_without_score_change(tmp_path):
    store = SourceReputationStore(tmp_path / "reputation.sqlite3")
    before = store.get("alice")
    after = store.record_outcome("alice", "uncertain", note="Insufficient evidence")
    assert after["score"] == before["score"]
    assert after["uncertain"] == 1
    assert store.list_outcomes("alice")[0]["outcome"] == "uncertain"
