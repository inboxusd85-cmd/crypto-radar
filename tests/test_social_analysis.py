from crypto_radar.social import SocialPost
from crypto_radar.social_analysis import analyze_post, extract_assets


def post(text: str) -> SocialPost:
    return SocialPost(
        platform="x", post_id="1", author_id="42", author_handle="project",
        text=text, created_at="2026-07-20T12:00:00Z", url="https://x.com/project/status/1",
        query="crypto", engagement=100, source_quality=0.5,
    )


def test_extract_assets_finds_tickers_and_project_names():
    assert extract_assets("HYPE and ZEC are moving after Hyperliquid update") == ["HYPE", "ZEC"]


def test_extract_assets_ignores_common_uppercase_words():
    assert extract_assets("BREAKING UPDATE: ETF NEWS for BTC") == ["BTC"]


def test_analyze_post_classifies_risk_claim_and_preserves_source():
    result = analyze_post(post("HYPE exploit risk: withdrawals paused after attack"))
    assert result["assets"] == ["HYPE"]
    assert result["claim_type"] == "risk"
    assert result["requires_manual_review"] is True
    assert result["source_url"] == "https://x.com/project/status/1"
    assert 0.0 <= result["confidence"] <= 1.0


def test_analyze_post_classifies_announcement():
    result = analyze_post(post("HYPE mainnet launch announcement and new listing"))
    assert result["claim_type"] == "announcement"
