from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .rss import RssArticle, parse_feed
from .rss_store import RssArticleStore


@dataclass(frozen=True)
class RssSource:
    name: str
    feed_url: str
    tier: str
    assets: tuple[str, ...]


DEFAULT_RSS_SOURCES = (
    RssSource("Bitcoin Optech", "https://bitcoinops.org/feed.xml", "technical", ("BTC",)),
    RssSource("Bitcoin Core releases", "https://github.com/bitcoin/bitcoin/releases.atom", "technical", ("BTC",)),
    RssSource("Ethereum Foundation", "https://blog.ethereum.org/en/feed.xml", "primary", ("ETH",)),
    RssSource("Ethereum Research", "https://ethresear.ch/latest.rss", "technical", ("ETH",)),
    RssSource("Geth releases", "https://github.com/ethereum/go-ethereum/releases.atom", "technical", ("ETH",)),
    RssSource("Solana News", "https://solana.com/news/rss.xml", "primary", ("SOL",)),
    RssSource("Anza releases", "https://github.com/anza-xyz/agave/releases.atom", "technical", ("SOL",)),
    RssSource("Electric Coin Company", "https://electriccoin.co/blog/feed/", "primary", ("ZEC",)),
    RssSource("Zcash Foundation", "https://zfnd.org/feed/", "primary", ("ZEC",)),
    RssSource("Zcash releases", "https://github.com/zcash/zcash/releases.atom", "technical", ("ZEC",)),
    RssSource("Zebra releases", "https://github.com/ZcashFoundation/zebra/releases.atom", "technical", ("ZEC",)),
    RssSource("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss", "secondary", ("BTC", "ETH", "SOL", "HYPE", "ZEC")),
    RssSource("The Block", "https://www.theblock.co/rss.xml", "secondary", ("BTC", "ETH", "SOL", "HYPE", "ZEC")),
    RssSource("Unchained", "https://unchainedcrypto.com/feed/", "secondary", ("BTC", "ETH", "SOL", "HYPE", "ZEC")),
    RssSource("Reddit r/Bitcoin", "https://www.reddit.com/r/Bitcoin/.rss", "discovery", ("BTC",)),
    RssSource("Reddit r/ethereum", "https://www.reddit.com/r/ethereum/.rss", "discovery", ("ETH",)),
    RssSource("Reddit r/solana", "https://www.reddit.com/r/solana/.rss", "discovery", ("SOL",)),
    RssSource("Reddit r/Hyperliquid", "https://www.reddit.com/r/Hyperliquid/.rss", "discovery", ("HYPE",)),
    RssSource("Reddit r/zec", "https://www.reddit.com/r/zec/.rss", "discovery", ("ZEC",)),
    RssSource("Reddit r/CryptoCurrency", "https://www.reddit.com/r/CryptoCurrency/.rss", "discovery", ("BTC", "ETH", "SOL", "HYPE", "ZEC")),
    RssSource("Reddit r/CryptoMarkets", "https://www.reddit.com/r/CryptoMarkets/.rss", "discovery", ("BTC", "ETH", "SOL", "HYPE", "ZEC")),
    RssSource("Reddit r/defi", "https://www.reddit.com/r/defi/.rss", "discovery", ("ETH", "SOL", "HYPE", "ZEC")),
    RssSource("Reddit r/altcoin", "https://www.reddit.com/r/altcoin/.rss", "discovery", ("BTC", "ETH", "SOL", "HYPE", "ZEC")),
    RssSource("Reddit r/BitcoinTechnology", "https://www.reddit.com/r/BitcoinTechnology/.rss", "discovery", ("BTC",)),
)


def load_rss_sources(path: Path) -> tuple[RssSource, ...]:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyYAML is required for --rss-config; install project dependencies") from exc
    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    rows = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"RSS config must contain a non-empty sources list: {path}")
    sources: list[RssSource] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"RSS source #{index} must be a mapping")
        try:
            source = RssSource(
                str(row["name"]), str(row["feed_url"]), str(row["tier"]),
                tuple(str(asset).upper() for asset in row["assets"]),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Invalid RSS source #{index}") from exc
        if not source.name.strip() or not source.feed_url.strip() or not source.assets:
            raise ValueError(f"Invalid RSS source #{index}: required fields are empty")
        if source.tier not in {"primary", "technical", "secondary", "discovery"}:
            raise ValueError(f"Invalid RSS tier for {source.name}: {source.tier}")
        sources.append(source)
    return tuple(sources)


class RssProviderError(RuntimeError):
    pass


def _retry_after_seconds(error: HTTPError) -> int | None:
    try:
        value = error.headers.get("Retry-After")
        return max(0, int(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def fetch_feed(source: RssSource, timeout: float = 20.0) -> list[RssArticle]:
    request = Request(source.feed_url, headers={"User-Agent": "crypto-radar/0.1 RSS reader"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except Exception as exc:
        raise RssProviderError(f"RSS fetch failed for {source.name}: {exc}") from exc
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        return parse_feed(payload, feed_url=source.feed_url, source_name=source.name, source_tier=source.tier, fetched_at=fetched_at)
    except Exception as exc:
        raise RssProviderError(f"RSS parse failed for {source.name}: {exc}") from exc


def collect_rss(
    store: RssArticleStore,
    sources: tuple[RssSource, ...] = DEFAULT_RSS_SOURCES,
    *,
    timeout: float = 20.0,
    asset: str | None = None,
    reddit_only: bool = False,
) -> dict:
    selected = tuple(source for source in sources if (not asset or asset.upper() in source.assets) and (not reddit_only or source.tier == "discovery"))
    report = {"sources": 0, "failed": 0, "rate_limited": 0, "retry_after_seconds": 0, "articles_seen": 0, "new_articles": 0, "errors": []}
    by_tier: dict[str, dict[str, int]] = {}
    for source in selected:
        report["sources"] += 1
        tier = by_tier.setdefault(source.tier, {"sources": 0, "failed": 0, "rate_limited": 0, "retry_after_seconds": 0, "articles_seen": 0, "new_articles": 0})
        tier["sources"] += 1
        try:
            articles = fetch_feed(source, timeout=timeout)
            report["articles_seen"] += len(articles)
            new_articles = sum(store.upsert(article) for article in articles)
            report["new_articles"] += new_articles
            tier["articles_seen"] += len(articles)
            tier["new_articles"] += new_articles
        except HTTPError as exc:
            report["failed"] += 1
            tier["failed"] += 1
            if exc.code == 429:
                report["rate_limited"] += 1
                tier["rate_limited"] += 1
                retry_after = _retry_after_seconds(exc) or 0
                report["retry_after_seconds"] = max(report["retry_after_seconds"], retry_after)
                tier["retry_after_seconds"] = max(tier["retry_after_seconds"], retry_after)
            report["errors"].append(f"RSS fetch failed for {source.name}: HTTP Error {exc.code}: {exc.reason}")
        except RssProviderError as exc:
            report["failed"] += 1
            tier["failed"] += 1
            cause = exc.__cause__
            if isinstance(cause, HTTPError) and cause.code == 429:
                report["rate_limited"] += 1
                tier["rate_limited"] += 1
                retry_after = _retry_after_seconds(cause) or 0
                report["retry_after_seconds"] = max(report["retry_after_seconds"], retry_after)
                tier["retry_after_seconds"] = max(tier["retry_after_seconds"], retry_after)
            report["errors"].append(str(exc))
        except Exception as exc:
            report["failed"] += 1
            tier["failed"] += 1
            report["errors"].append(f"RSS fetch failed for {source.name}: {exc}")
    report["by_tier"] = by_tier
    report["status"] = "degraded" if report["failed"] else "ok"
    report["source_health"] = {
        name: ("error" if values["failed"] else "ok")
        for name, values in by_tier.items()
    }
    return report
