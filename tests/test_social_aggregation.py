from crypto_radar.social_aggregation import aggregate_social_analyses


def analysis(post_id, author, asset="HYPE", claim_type="risk", confidence=0.7, url=None):
    return {
        "platform": "x", "post_id": post_id, "source_url": url or f"https://x.com/{author}/status/{post_id}",
        "author_handle": author, "text": f"{asset} {claim_type}", "created_at": "2026-07-20T12:00:00Z",
        "assets": [asset], "claim_type": claim_type, "confidence": confidence, "requires_manual_review": True,
    }


def test_aggregator_counts_independent_authors_not_reposts():
    result = aggregate_social_analyses([
        analysis("1", "alice"), analysis("2", "bob"), analysis("3", "alice"),
    ])
    assert len(result) == 1
    assert result[0]["asset"] == "HYPE"
    assert result[0]["independent_authors"] == 2
    assert result[0]["evidence_count"] == 3
    assert result[0]["severity"] == "medium"


def test_aggregator_deduplicates_same_url_and_separates_claims():
    result = aggregate_social_analyses([
        analysis("1", "alice", url="https://same"),
        analysis("2", "bob", url="https://same"),
        analysis("3", "carol", claim_type="announcement"),
    ])
    assert len(result) == 2
    risk = next(item for item in result if item["claim_type"] == "risk")
    assert risk["evidence_count"] == 1
    assert risk["independent_authors"] == 1


def test_aggregator_preserves_evidence_links_and_review_flag():
    result = aggregate_social_analyses([analysis("1", "alice"), analysis("2", "bob")])
    assert len(result[0]["evidence"]) == 2
    assert all(item["url"].startswith("https://") for item in result[0]["evidence"])
    assert result[0]["requires_manual_review"] is True
