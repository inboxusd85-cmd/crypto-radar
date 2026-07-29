from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from pathlib import Path

from .rss import RssArticle, classify_event_type


class RssArticleStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS rss_articles ("
                "source_name TEXT NOT NULL, article_id TEXT NOT NULL, title TEXT NOT NULL, "
                "url TEXT NOT NULL, published_at TEXT NOT NULL, summary TEXT NOT NULL, "
                "assets TEXT NOT NULL, source_tier TEXT NOT NULL, source_url TEXT NOT NULL, "
                "fetched_at TEXT NOT NULL, payload TEXT NOT NULL, "
                "PRIMARY KEY(source_name, article_id))"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_rss_articles_published ON rss_articles(published_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_rss_articles_asset ON rss_articles(assets)"
            )

    def upsert(self, article: RssArticle) -> bool:
        payload = json.dumps(asdict(article), ensure_ascii=False, separators=(",", ":"))
        with sqlite3.connect(self.path) as connection:
            result = connection.execute(
                "INSERT OR IGNORE INTO rss_articles "
                "(source_name, article_id, title, url, published_at, summary, assets, source_tier, source_url, fetched_at, payload) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (article.source_name, article.article_id, article.title, article.url, article.published_at,
                 article.summary, json.dumps(article.assets), article.source_tier, article.source_url,
                 article.fetched_at, payload),
            )
        return result.rowcount == 1

    def list_articles(self, asset: str | None = None, limit: int = 50) -> list[RssArticle]:
        if limit < 1:
            raise ValueError("limit must be positive")
        sql = "SELECT payload FROM rss_articles"
        params: list[object] = []
        if asset:
            sql += " WHERE assets LIKE ?"
            params.append(f'%"{asset.upper()}"%')
        sql += " ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(sql, params).fetchall()
        articles = []
        for row in rows:
            payload = json.loads(row[0])
            payload["assets"] = tuple(payload.get("assets", ()))
            payload["ranking_features"] = tuple(payload.get("ranking_features", ()))
            if "event_type" not in payload:
                payload["event_type"] = classify_event_type(payload.get("title", ""), payload.get("summary", ""))
            articles.append(RssArticle(**payload))
        return articles
