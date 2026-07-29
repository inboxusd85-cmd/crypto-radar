from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .social import SocialPost


class SocialPostStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS social_posts ("
                "platform TEXT NOT NULL, post_id TEXT NOT NULL, author_handle TEXT, created_at TEXT NOT NULL, "
                "query TEXT NOT NULL, engagement INTEGER NOT NULL, source_quality REAL NOT NULL, payload TEXT NOT NULL, "
                "PRIMARY KEY(platform, post_id))"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_social_posts_query ON social_posts(query, created_at DESC)")

    def upsert(self, post: SocialPost) -> bool:
        payload = json.dumps(post.__dict__, ensure_ascii=False, separators=(",", ":"))
        with sqlite3.connect(self.path) as connection:
            result = connection.execute(
                "INSERT OR IGNORE INTO social_posts(platform, post_id, author_handle, created_at, query, engagement, source_quality, payload) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (post.platform, post.post_id, post.author_handle, post.created_at, post.query,
                 post.engagement, post.source_quality, payload),
            )
        return result.rowcount == 1

    def list_posts(self, query: str | None = None, limit: int = 50) -> list[dict]:
        if limit < 1:
            raise ValueError("limit must be positive")
        sql = "SELECT payload FROM social_posts"
        parameters: list[object] = []
        if query:
            sql += " WHERE query = ?"
            parameters.append(query)
        sql += " ORDER BY created_at DESC LIMIT ?"
        parameters.append(limit)
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [json.loads(row[0]) for row in rows]
