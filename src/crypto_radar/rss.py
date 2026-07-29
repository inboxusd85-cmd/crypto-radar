from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import re
import xml.etree.ElementTree as ET


ASSET_ALIASES = {
    "BTC": ("bitcoin", "btc"),
    "ETH": ("ethereum", "eth", "evm"),
    "SOL": ("solana", "sol"),
    "HYPE": ("hyperliquid", "hyper foundation", "hyperliquid", "hype"),
    "ZEC": ("zcash", "zec", "zebra", "shielded", "orchard", "sapling"),
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _text(element: ET.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def _first(element: ET.Element, names: set[str]) -> ET.Element | None:
    for child in element.iter():
        if _local(child.tag) in names:
            return child
    return None


def _parse_date(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _matches(text: str, aliases: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", lowered) for alias in aliases)


def extract_assets(text: str) -> list[str]:
    return [asset for asset, aliases in ASSET_ALIASES.items() if _matches(text, aliases)]


def classify_event_type(title: str, summary: str = "") -> str:
    """Classify news into explainability-only event taxonomy."""
    text = f"{title} {summary}".casefold()
    rules = (
        ("security_incident", ("hack", "exploit", "breach", "attack", "взлом", "атака", "уязв")),
        ("regulatory", ("regulat", "lawsuit", "lawsuit", "ban", "approval", "sec ", "запрет", "регулятор", "иск")),
        ("listing_delisting", ("list", "delist", "listing", "листинг", "делист")),
        ("partnership_adoption", ("partnership", "integration", "adoption", "партнер", "интеграц", "сотруднич")),
        ("protocol_upgrade", ("upgrade", "update", "hard fork", "release", "mainnet", "testnet", "обновлен", "релиз", "форк")),
        ("funding_institutional", ("funding", "investment", "etf", "institutional", "финансирован", "инвестиц")),
        ("tokenomics_supply", ("unlock", "emission", "supply", "vesting", "разблокиров", "эмисс", "токеномик")),
        ("governance", ("governance", "vote", "proposal", "голосован", "предложен")),
        ("macro", ("inflation", "interest rate", "fed ", "fomc", "cpi", "инфляц", "ставк")),
    )
    for category, markers in rules:
        if any(marker in text for marker in markers):
            return category
    return "general"


@dataclass(frozen=True)
class RssArticle:
    source_name: str
    source_url: str
    article_id: str
    title: str
    url: str
    published_at: str
    summary: str
    assets: tuple[str, ...]
    source_tier: str
    fetched_at: str
    ranking_features: tuple[float, ...] = ()
    event_type: str = "general"

    def __post_init__(self) -> None:
        for field in ("source_name", "source_url", "article_id", "title", "url", "fetched_at"):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} is required")
        if self.source_tier not in {"primary", "technical", "secondary", "discovery"}:
            raise ValueError("invalid source_tier")


def parse_feed(
    payload: str | bytes,
    *,
    feed_url: str,
    source_name: str,
    source_tier: str = "secondary",
    fetched_at: str | None = None,
) -> list[RssArticle]:
    root = ET.fromstring(payload)
    fetched = fetched_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    articles: list[RssArticle] = []
    seen: set[str] = set()
    entries = [node for node in root.iter() if _local(node.tag) in {"item", "entry"}]
    for entry in entries:
        title = _text(_first(entry, {"title"}))
        link_node = _first(entry, {"link"})
        url = (link_node.attrib.get("href", "") if link_node is not None else "") or _text(link_node)
        guid = _text(_first(entry, {"guid", "id"})) or url
        article_id = hashlib.sha256(f"{source_name}\0{guid}".encode()).hexdigest()
        if article_id in seen or not title or not url:
            continue
        seen.add(article_id)
        published = _text(_first(entry, {"pubdate", "published", "updated", "date"}))
        summary = _text(_first(entry, {"description", "summary", "content"}))
        assets = tuple(extract_assets(f"{title} {summary}"))
        from .news_ranker import extract_news_features
        ranking_features = tuple(extract_news_features(title, summary).vector())
        articles.append(RssArticle(
            source_name=source_name, source_url=feed_url, article_id=article_id,
            title=title, url=url, published_at=_parse_date(published), summary=summary,
            assets=assets, source_tier=source_tier, fetched_at=fetched,
            ranking_features=ranking_features,
            event_type=classify_event_type(title, summary),
        ))
    return articles
