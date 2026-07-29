from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
import sqlite3
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class GitHubSnapshot:
    repo: str
    full_name: str
    html_url: str
    description: str | None
    stars: int
    forks: int
    open_issues: int
    default_branch: str
    last_push_at: str | None
    latest_release: str | None
    latest_release_at: str | None
    latest_issue_or_pr_at: str | None


@dataclass(frozen=True)
class GitHubChange:
    repo: str
    kind: str
    external_id: str
    occurred_at: str
    title: str
    url: str
    value: dict


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def summarize_events(events: list[dict]) -> dict:
    by_kind: dict[str, int] = {}
    by_severity = {"low": 0, "medium": 0, "high": 0}
    enriched: list[dict] = []
    for event in events:
        kind = str(event.get("kind", "unknown"))
        value = event.get("value") or {}
        delta = abs(int(value.get("delta", 0))) if isinstance(value, dict) else 0
        severity = "high" if kind == "release" and value.get("tag") else "high" if delta >= 10 else "medium" if delta > 0 else "low"
        if kind == "release":
            severity = "low"
        by_kind[kind] = by_kind.get(kind, 0) + 1
        by_severity[severity] += 1
        enriched.append({**event, "severity": severity})
    return {"total": len(events), "by_kind": dict(sorted(by_kind.items())), "by_severity": by_severity, "latest": enriched[-1] if enriched else None}


def diff_snapshot(old: GitHubSnapshot, new: GitHubSnapshot) -> list[GitHubChange]:
    changes: list[GitHubChange] = []
    occurred_at = new.last_push_at or new.latest_release_at or utc_now()
    if new.stars != old.stars:
        delta = new.stars - old.stars
        changes.append(GitHubChange(new.repo, "stars", f"stars:{new.stars}", occurred_at, "Изменилось число звёзд", new.html_url, {"from": old.stars, "to": new.stars, "delta": delta}))
    if new.forks > old.forks:
        changes.append(GitHubChange(new.repo, "fork", f"forks:{new.forks}", occurred_at, "Появился новый fork", new.html_url, {"from": old.forks, "to": new.forks, "delta": new.forks - old.forks}))
    if new.latest_release and new.latest_release != old.latest_release:
        changes.append(GitHubChange(new.repo, "release", f"release:{new.latest_release}", new.latest_release_at or occurred_at, f"Новый release {new.latest_release}", new.html_url + "/releases", {"tag": new.latest_release}))
    if new.last_push_at and new.last_push_at != old.last_push_at:
        changes.append(GitHubChange(new.repo, "push", f"push:{new.last_push_at}", new.last_push_at, "Изменился default branch", new.html_url + "/commits/" + new.default_branch, {"branch": new.default_branch}))
    if new.latest_issue_or_pr_at and new.latest_issue_or_pr_at != old.latest_issue_or_pr_at:
        changes.append(GitHubChange(new.repo, "issue_pr", f"issue-pr:{new.latest_issue_or_pr_at}", new.latest_issue_or_pr_at, "Новая активность issue/PR", new.html_url + "/issues", {}))
    return changes


class GitHubClient:
    def __init__(self, token: str | None = None, fetch_json: Callable[[str], object] | None = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.fetch_json = fetch_json or self._fetch_json

    def _fetch_json(self, url: str) -> object:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "crypto-radar-github-watch"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            with urlopen(Request(url, headers=headers), timeout=20) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, RemoteDisconnected) as exc:
            raise RuntimeError(f"GitHub request failed: {url}") from exc

    def snapshot(self, repo: str) -> GitHubSnapshot:
        repo = repo.strip().strip("/")
        if repo.count("/") != 1:
            raise ValueError("GitHub repository must be owner/name")
        base = f"https://api.github.com/repos/{repo}"
        info = self.fetch_json(base)
        if not isinstance(info, dict):
            raise RuntimeError("Invalid GitHub repository response")
        try:
            releases = self.fetch_json(base + "/releases/latest")
        except RuntimeError:
            releases = None
        release = releases if isinstance(releases, dict) and releases.get("tag_name") else None
        issues = self.fetch_json(base + "/issues?state=all&per_page=1&sort=updated&direction=desc")
        latest_issue = issues[0].get("updated_at") if isinstance(issues, list) and issues and isinstance(issues[0], dict) else None
        return GitHubSnapshot(repo=repo, full_name=str(info.get("full_name", repo)), html_url=str(info.get("html_url", f"https://github.com/{repo}")), description=info.get("description"), stars=int(info.get("stargazers_count", 0)), forks=int(info.get("forks_count", 0)), open_issues=int(info.get("open_issues_count", 0)), default_branch=str(info.get("default_branch", "main")), last_push_at=info.get("pushed_at"), latest_release=release.get("tag_name") if release else None, latest_release_at=release.get("published_at") if release else None, latest_issue_or_pr_at=latest_issue)


class GitHubWatchStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS github_snapshots (repo TEXT PRIMARY KEY, observed_at TEXT NOT NULL, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS github_events (repo TEXT NOT NULL, kind TEXT NOT NULL, external_id TEXT NOT NULL, occurred_at TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL, value TEXT NOT NULL, recorded_at TEXT NOT NULL, PRIMARY KEY(repo, kind, external_id))")
            db.execute("CREATE INDEX IF NOT EXISTS idx_github_events_recorded ON github_events(recorded_at DESC)")

    def get_snapshot(self, repo: str) -> GitHubSnapshot | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT payload FROM github_snapshots WHERE repo = ?", (repo,)).fetchone()
        return GitHubSnapshot(**json.loads(row[0])) if row else None

    def record_snapshot(self, snapshot: GitHubSnapshot) -> bool:
        payload = json.dumps(asdict(snapshot), ensure_ascii=False, separators=(",", ":"))
        with sqlite3.connect(self.path) as db:
            result = db.execute("INSERT OR IGNORE INTO github_snapshots(repo, observed_at, payload) VALUES (?, ?, ?)", (snapshot.repo, utc_now(), payload))
        return result.rowcount == 1

    def replace_snapshot(self, snapshot: GitHubSnapshot) -> None:
        payload = json.dumps(asdict(snapshot), ensure_ascii=False, separators=(",", ":"))
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO github_snapshots(repo, observed_at, payload) VALUES (?, ?, ?) ON CONFLICT(repo) DO UPDATE SET observed_at=excluded.observed_at, payload=excluded.payload", (snapshot.repo, utc_now(), payload))

    def record_event(self, event: GitHubChange) -> bool:
        with sqlite3.connect(self.path) as db:
            result = db.execute("INSERT OR IGNORE INTO github_events(repo, kind, external_id, occurred_at, title, url, value, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (event.repo, event.kind, event.external_id, event.occurred_at, event.title, event.url, json.dumps(event.value, ensure_ascii=False), utc_now()))
        return result.rowcount == 1

    def list_events(self, repo: str | None = None, kinds: Iterable[str] | None = None, since: str | None = None, limit: int = 50) -> list[dict]:
        sql = "SELECT repo, kind, external_id, occurred_at, title, url, value, recorded_at FROM github_events"
        clauses: list[str] = []
        params: list[object] = []
        if repo:
            clauses.append("repo = ?")
            params.append(repo)
        normalized_kinds = [kind.strip() for kind in (kinds or []) if kind.strip()]
        if normalized_kinds:
            clauses.append("kind IN (" + ",".join("?" for _ in normalized_kinds) + ")")
            params.extend(normalized_kinds)
        if since:
            clauses.append("occurred_at >= ?")
            params.append(since)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY occurred_at DESC, recorded_at DESC LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.path) as db:
            rows = db.execute(sql, params).fetchall()
        return [{"repo": row[0], "kind": row[1], "external_id": row[2], "occurred_at": row[3], "title": row[4], "url": row[5], "value": json.loads(row[6]), "recorded_at": row[7]} for row in rows]


def poll_repositories(repos: Iterable[str], store: GitHubWatchStore, client: GitHubClient) -> dict:
    report = {"repositories": 0, "changed": 0, "events": 0, "errors": []}
    for repo in repos:
        try:
            current = client.snapshot(repo)
            previous = store.get_snapshot(current.repo)
            changes = diff_snapshot(previous, current) if previous else []
            for event in changes:
                report["events"] += int(store.record_event(event))
            store.replace_snapshot(current)
            report["repositories"] += 1
            report["changed"] += len(changes)
        except (RuntimeError, ValueError) as exc:
            report["errors"].append({"repo": repo, "error": str(exc)})
    return report