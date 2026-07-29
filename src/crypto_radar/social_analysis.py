from __future__ import annotations

import re

from .social import SocialPost


_COMMON_WORDS = {
    "A", "AI", "AND", "API", "ARE", "BREAKING", "ETF", "FOR", "FROM", "IN", "IS", "NEWS",
    "NEW", "OF", "ON", "OR", "THE", "THIS", "TO", "UPDATE", "USD", "US", "WITH",
}
_PROJECT_ALIASES = {"HYPERLIQUID": "HYPE", "BITCOIN": "BTC", "ETHEREUM": "ETH", "SOLANA": "SOL", "ZCASH": "ZEC"}


def extract_assets(text: str) -> list[str]:
    found: list[str] = []
    for match in re.findall(r"\$([A-Za-z][A-Za-z0-9]{1,9})", text):
        found.append(match.upper())
    for match in re.findall(r"\b[A-Z]{2,10}\b", text):
        token = match.upper()
        if token not in _COMMON_WORDS:
            found.append(token)
    upper_text = text.upper()
    for alias, ticker in _PROJECT_ALIASES.items():
        if re.search(rf"\b{alias}\b", upper_text):
            found.append(ticker)
    return sorted(set(found), key=found.index)


def _claim_type(text: str) -> str:
    lower = text.lower()
    if any(word in lower for word in ("exploit", "hack", "attack", "paused", "risk", "vulnerability", "scam")):
        return "risk"
    if any(word in lower for word in ("launch", "listing", "mainnet", "partnership", "integration", "announcement")):
        return "announcement"
    if any(word in lower for word in ("raise", "funding", "investment", "million", "billion")):
        return "funding"
    if any(word in lower for word in ("airdrop", "rewards", "incentives", "points")):
        return "incentive"
    return "general"


def analyze_post(post: SocialPost) -> dict:
    assets = extract_assets(post.text)
    claim_type = _claim_type(post.text)
    confidence = min(0.9, 0.25 + (0.2 if assets else 0.0) + (0.15 if claim_type != "general" else 0.0) + post.source_quality * 0.25)
    return {
        "platform": post.platform,
        "post_id": post.post_id,
        "source_url": post.url,
        "author_handle": post.author_handle,
        "text": post.text,
        "created_at": post.created_at,
        "source_quality": post.source_quality,
        "assets": assets,
        "claim_type": claim_type,
        "confidence": round(confidence, 4),
        "requires_manual_review": True,
    }
