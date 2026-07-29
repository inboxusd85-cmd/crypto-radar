from pathlib import Path

from crypto_radar.rss import RssArticle, classify_event_type, extract_assets, parse_feed
from crypto_radar.rss_store import RssArticleStore
from crypto_radar.rss_collector import DEFAULT_RSS_SOURCES, RssSource, collect_rss, load_rss_sources


FEED = """<?xml version="1.0"?><rss><channel><title>Example</title><item><title>Ethereum protocol update</title><link>https://example.test/eth</link><guid>eth-1</guid><pubDate>Wed, 22 Jul 2026 10:00:00 GMT</pubDate><description><![CDATA[ETH staking and EVM changes.]]></description></item><item><title>Duplicate</title><link>https://example.test/eth</link><guid>eth-1</guid></item></channel></rss>"""


def test_parse_feed_normalizes_and_deduplicates_by_guid():
    articles = parse_feed(FEED, feed_url="https://example.test/feed.xml", source_name="Example")

    assert len(articles) == 1
    assert articles[0].title == "Ethereum protocol update"
    assert articles[0].url == "https://example.test/eth"
    assert articles[0].source_name == "Example"
    assert articles[0].published_at == "2026-07-22T10:00:00+00:00"
    assert articles[0].ranking_features == (0.0, 0.0, 0.5, 24.0, 1.0)
    assert articles[0].event_type == "protocol_upgrade"


def test_event_taxonomy_prioritizes_specific_fundamental_categories():
    assert classify_event_type("Protocol exploit after upgrade", "Security breach reported") == "security_incident"
    assert classify_event_type("ETF approval and institutional inflows") == "regulatory"
    assert classify_event_type("Weekly ecosystem metrics", "Protocol metrics remain stable") == "general"


def test_extract_assets_uses_aliases_and_avoids_common_words():
    assert extract_assets("Ethereum and ETH, SOL validators, and HYPE governance") == ["ETH", "SOL", "HYPE"]


def test_store_is_idempotent(tmp_path: Path):
    article = RssArticle(
        source_name="Example", source_url="https://example.test/feed.xml", article_id="eth-1",
        title="Ethereum protocol update", url="https://example.test/eth",
        published_at="2026-07-22T10:00:00+00:00", summary="ETH update",
        assets=("ETH",), source_tier="primary", fetched_at="2026-07-22T10:01:00+00:00",
    )
    store = RssArticleStore(tmp_path / "radar.sqlite3")

    assert store.upsert(article) is True
    assert store.upsert(article) is False
    assert store.list_articles(limit=10) == [article]


def test_store_round_trips_ranking_features(tmp_path: Path):
    article = RssArticle(
        source_name="Example", source_url="https://example.test/feed.xml", article_id="eth-2",
        title="Ethereum adoption growth", url="https://example.test/eth-2",
        published_at="2026-07-22T10:00:00+00:00", summary="Partnership growth",
        assets=("ETH",), source_tier="primary", fetched_at="2026-07-22T10:01:00+00:00",
        ranking_features=(2.0, 0.0, 0.9, 1.5, 1.0),
    )
    store = RssArticleStore(tmp_path / "radar.sqlite3")

    assert store.upsert(article) is True
    assert store.list_articles(limit=10) == [article]


def test_default_sources_include_asset_specific_and_cross_asset_reddit_feeds():
    reddit = {source.name: source for source in DEFAULT_RSS_SOURCES if "Reddit" in source.name}

    assert reddit["Reddit r/Bitcoin"].feed_url == "https://www.reddit.com/r/Bitcoin/.rss"
    assert reddit["Reddit r/ethereum"].assets == ("ETH",)
    assert reddit["Reddit r/Hyperliquid"].assets == ("HYPE",)
    assert reddit["Reddit r/CryptoCurrency"].assets == ("BTC", "ETH", "SOL", "HYPE", "ZEC")
    assert len(reddit) >= 10


def test_collect_rss_can_run_reddit_only_and_reports_tiers(tmp_path: Path, monkeypatch):
    sources = (
        RssSource("Primary", "https://example.test/primary", "primary", ("BTC",)),
        RssSource("Reddit r/Bitcoin", "https://example.test/reddit", "discovery", ("BTC",)),
    )

    monkeypatch.setattr(
        "crypto_radar.rss_collector.fetch_feed",
        lambda source, timeout: [] if source.tier == "discovery" else [
            RssArticle("Primary", source.feed_url, "one", "BTC update", "https://example.test/one", "", "", ("BTC",), "primary", "2026-07-22T00:00:00+00:00")
        ],
    )
    report = collect_rss(RssArticleStore(tmp_path / "rss.sqlite3"), sources, reddit_only=True)

    assert report["sources"] == 1
    assert report["by_tier"] == {"discovery": {"sources": 1, "failed": 0, "rate_limited": 0, "retry_after_seconds": 0, "articles_seen": 0, "new_articles": 0}}


def test_collect_rss_classifies_rate_limited_sources(tmp_path: Path, monkeypatch):
    from urllib.error import HTTPError

    source = RssSource("Reddit r/Bitcoin", "https://example.test/reddit", "discovery", ("BTC",))
    monkeypatch.setattr(
        "crypto_radar.rss_collector.fetch_feed",
        lambda source, timeout: (_ for _ in ()).throw(HTTPError(source.feed_url, 429, "Too Many Requests", {}, None)),
    )

    report = collect_rss(RssArticleStore(tmp_path / "rss.sqlite3"), (source,), reddit_only=True)

    assert report["failed"] == 1
    assert report["rate_limited"] == 1
    assert report["by_tier"]["discovery"]["rate_limited"] == 1


def test_collect_rss_exposes_retry_after_without_sleeping(tmp_path: Path, monkeypatch):
    from urllib.error import HTTPError

    source = RssSource("Reddit r/Bitcoin", "https://example.test/reddit", "discovery", ("BTC",))
    headers = {"Retry-After": "120"}
    monkeypatch.setattr(
        "crypto_radar.rss_collector.fetch_feed",
        lambda source, timeout: (_ for _ in ()).throw(HTTPError(source.feed_url, 429, "Too Many Requests", headers, None)),
    )

    report = collect_rss(RssArticleStore(tmp_path / "rss.sqlite3"), (source,), reddit_only=True)

    assert report["retry_after_seconds"] == 120
    assert report["by_tier"]["discovery"]["retry_after_seconds"] == 120


def test_collect_rss_reports_overall_and_tier_health(tmp_path: Path, monkeypatch):
    sources = (
        RssSource("Primary", "https://example.test/primary", "primary", ("BTC",)),
        RssSource("Reddit", "https://example.test/reddit", "discovery", ("BTC",)),
    )

    def fake_fetch(source, timeout):
        if source.tier == "discovery":
            raise RuntimeError("temporary provider failure")
        return []

    monkeypatch.setattr("crypto_radar.rss_collector.fetch_feed", fake_fetch)
    report = collect_rss(RssArticleStore(tmp_path / "rss.sqlite3"), sources)

    assert report["status"] == "degraded"
    assert report["source_health"] == {"primary": "ok", "discovery": "error"}


def test_load_rss_sources_from_yaml_is_configurable(tmp_path: Path):
    config = tmp_path / "sources.yaml"
    config.write_text(
        "sources:\n"
        "  - name: Custom Reddit\n"
        "    feed_url: https://www.reddit.com/r/Bitcoin/.rss\n"
        "    tier: discovery\n"
        "    assets: [BTC]\n",
        encoding="utf-8",
    )

    sources = load_rss_sources(config)

    assert sources == (RssSource("Custom Reddit", "https://www.reddit.com/r/Bitcoin/.rss", "discovery", ("BTC",)),)
