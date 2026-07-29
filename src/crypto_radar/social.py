from __future__ import annotations

from dataclasses import dataclass
import json
import shutil
import subprocess
from typing import Any


class SocialProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class SocialPost:
    platform: str
    post_id: str
    author_id: str
    author_handle: str
    text: str
    created_at: str
    url: str
    query: str
    engagement: int
    source_quality: float

    def __post_init__(self) -> None:
        for name in ("platform", "post_id", "author_id", "text", "created_at", "url", "query"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} is required")
        if self.engagement < 0:
            raise ValueError("engagement must be non-negative")
        if not 0.0 <= self.source_quality <= 1.0:
            raise ValueError("source_quality must be between 0 and 1")


def _source_quality(author_handle: str, engagement: int) -> float:
    score = 0.25
    if author_handle:
        score += 0.25
    if engagement >= 1000:
        score += 0.25
    if engagement >= 10000:
        score += 0.25
    return min(score, 1.0)


def normalize_x_response(response: dict[str, Any], query: str) -> list[SocialPost]:
    users = {user.get("id"): user for user in response.get("includes", {}).get("users", [])}
    posts: list[SocialPost] = []
    seen: set[str] = set()
    for item in response.get("data", []):
        post_id = str(item.get("id", ""))
        if not post_id or post_id in seen:
            continue
        seen.add(post_id)
        author_id = str(item.get("author_id", ""))
        user = users.get(author_id, {})
        handle = str(user.get("username", ""))
        metrics = item.get("public_metrics", {}) or {}
        engagement = sum(int(metrics.get(key, 0) or 0) for key in ("like_count", "reply_count", "retweet_count", "quote_count"))
        posts.append(SocialPost(
            platform="x", post_id=post_id, author_id=author_id, author_handle=handle,
            text=str(item.get("text", "")), created_at=str(item.get("created_at", "")),
            url=f"https://x.com/{handle or author_id}/status/{post_id}", query=query,
            engagement=engagement, source_quality=_source_quality(handle, engagement),
        ))
    return posts


class XSearchAdapter:
    def __init__(self, executable: str = "xurl"):
        self.executable = executable

    def search(self, query: str, limit: int = 10) -> list[SocialPost]:
        if not query.strip():
            raise ValueError("query is required")
        if limit < 1:
            raise ValueError("limit must be positive")
        if shutil.which(self.executable) is None:
            raise SocialProviderError("xurl is not installed; install and authenticate it before X monitoring")
        result = subprocess.run(
            [self.executable, "search", query, "-n", str(limit)],
            check=False, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise SocialProviderError(result.stderr.strip() or "xurl search failed")
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise SocialProviderError("xurl returned invalid JSON") from error
        return normalize_x_response(response, query)
