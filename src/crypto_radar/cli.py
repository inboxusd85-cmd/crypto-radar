from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .alerts import render_markdown
from .candle_history import CandleHistory
from .jsonl_export import write_jsonl
from .deduplication import AlertDeduplicator
from .events import AlertEventJournal
from .providers.hyperliquid import HyperliquidProvider, ProviderError, MarketSnapshot, SUPPORTED_CANDLE_INTERVALS, SOURCE_CANDLE_INTERVALS
from .market_snapshot_service import MarketSnapshotService
from .indicator_collector import IndicatorCollector
from .serialization import signals_to_json
from .social import SocialPost, SocialProviderError, XSearchAdapter
from .social_store import SocialPostStore
from .social_analysis import analyze_post
from .social_aggregation import aggregate_social_analyses
from .social_signals import social_candidate_to_signal
from .source_reputation import SourceReputationStore
from .quality_gate import validate_signal
from .rss_collector import DEFAULT_RSS_SOURCES, RssProviderError, collect_rss, load_rss_sources
from .rss_store import RssArticleStore
from .github_watch import GitHubClient, GitHubWatchStore, poll_repositories, summarize_events

DEFAULT_ASSETS = "BTC,ETH,SOL,HYPE,ZEC"
_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


def severity_at_least(actual: str, minimum: str) -> bool:
    return _SEVERITY_ORDER[actual] >= _SEVERITY_ORDER[minimum]


def build_backfill_windows(start_ms: int, end_ms: int, source_interval_ms: int, window_candles: int = 500) -> list[tuple[int, int]]:
    if start_ms < 0 or end_ms <= start_ms or source_interval_ms < 1 or window_candles < 1:
        raise ValueError("invalid historical backfill range or window")
    step = source_interval_ms * window_candles
    return [(cursor, min(cursor + step, end_ms)) for cursor in range(start_ms, end_ms, step)]


def _parse_utc_ms(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def historical_backfill_report(args) -> dict:
    start_ms, end_ms = _parse_utc_ms(args.start), _parse_utc_ms(args.end)
    timeframes = tuple(item.strip() for item in args.timeframes.split(",") if item.strip())
    invalid = sorted(set(timeframes) - set(SUPPORTED_CANDLE_INTERVALS))
    if invalid:
        raise ValueError("unsupported timeframes: " + ", ".join(invalid))
    history = CandleHistory(Path(args.backfill_history))
    provider = HyperliquidProvider()
    run_id = uuid.uuid4().hex
    with sqlite3.connect(args.backfill_history) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS historical_backfill_runs (run_id TEXT PRIMARY KEY, source TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL, started_at REAL NOT NULL, finished_at REAL)")
        connection.execute("CREATE TABLE IF NOT EXISTS historical_backfill_pages (run_id TEXT NOT NULL, page_number INTEGER NOT NULL, asset TEXT NOT NULL, timeframe TEXT NOT NULL, source_timeframe TEXT NOT NULL, requested_start_ms INTEGER NOT NULL, requested_end_ms INTEGER NOT NULL, actual_min_open_time INTEGER, actual_max_open_time INTEGER, row_count INTEGER NOT NULL, status TEXT NOT NULL, error TEXT, fetched_at REAL NOT NULL, PRIMARY KEY(run_id, page_number))")
        connection.execute("INSERT INTO historical_backfill_runs(run_id, source, start, end, started_at) VALUES (?, ?, ?, ?, ?)", (run_id, "historical_backfill", args.start, args.end, time.time()))
    report = {"read_only": True, "source": "historical_backfill", "run_id": run_id, "start": args.start, "end": args.end, "assets": {}, "errors": []}
    page_number = 0
    for asset in sorted({item.strip().upper() for item in args.assets.split(",") if item.strip()}):
        report["assets"][asset] = {}
        for timeframe in timeframes:
            source_timeframe = SOURCE_CANDLE_INTERVALS[timeframe]
            interval = SUPPORTED_CANDLE_INTERVALS[source_timeframe]
            inserted = updated = fetched = 0
            for window_start, window_end in build_backfill_windows(start_ms, end_ms, interval, args.window_candles):
                page_number += 1
                try:
                    candles = provider.fetch_candles(asset, timeframe, window_start, window_end)
                    stats = history.archive_upsert_many(candles)
                    inserted += stats["inserted"]
                    updated += stats["updated"]
                    fetched += len(candles)
                    with sqlite3.connect(args.backfill_history) as connection:
                        connection.execute("INSERT INTO historical_backfill_pages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (run_id, page_number, asset, timeframe, source_timeframe, window_start, window_end, min((item.open_time for item in candles), default=None), max((item.open_time for item in candles), default=None), len(candles), "ok", None, time.time()))
                    if args.pause_seconds:
                        time.sleep(args.pause_seconds)
                except (ProviderError, ValueError) as exc:
                    report["errors"].append({"asset": asset, "timeframe": timeframe, "window_start": window_start, "error": str(exc)})
                    with sqlite3.connect(args.backfill_history) as connection:
                        connection.execute("INSERT INTO historical_backfill_pages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (run_id, page_number, asset, timeframe, source_timeframe, window_start, window_end, None, None, 0, "error", str(exc), time.time()))
                    break
            report["assets"][asset][timeframe] = {"source_timeframe": source_timeframe, "fetched": fetched, "inserted": inserted, "updated": updated}
    with sqlite3.connect(args.backfill_history) as connection:
        connection.execute("UPDATE historical_backfill_runs SET finished_at = ? WHERE run_id = ?", (time.time(), run_id))
    return report


def asset_to_dict(snapshot: MarketSnapshot) -> dict:
    return {
        "asset": snapshot.asset,
        "mark_price": snapshot.mark_price,
        "mid_price": snapshot.mid_price,
        "funding_rate": snapshot.funding_rate,
        "open_interest": snapshot.open_interest,
        "day_notional_volume": snapshot.day_notional_volume,
    }


def missing_assets(requested: set[str], snapshots: list[MarketSnapshot]) -> set[str]:
    return requested - {snapshot.asset for snapshot in snapshots}


def format_social_posts(posts: list[SocialPost], output_format: str) -> str:
    payload = [post.__dict__ for post in posts]
    if output_format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    lines = ["## X social posts", ""]
    for post in posts:
        author = f"@{post.author_handle}" if post.author_handle else post.author_id
        lines.append(f"- {post.created_at} {author} engagement={post.engagement} quality={post.source_quality:.2f}: {post.text}")
        lines.append(f"  {post.url}")
    return "\n".join(lines)


def format_events(events: list[dict], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(events, ensure_ascii=False, indent=2)
    lines = ["## Alert events", ""]
    for event in events:
        lines.append(
            f"- {event['observed_at']} {event['asset']} {event['severity'].upper()} {event['signal_id']}"
        )
    return "\n".join(lines)


def format_assets(snapshots: list[MarketSnapshot], output_format: str) -> str:
    if output_format == "json":
        return json.dumps([asset_to_dict(snapshot) for snapshot in snapshots], ensure_ascii=False, indent=2)
    lines = ["## Hyperliquid assets", ""]
    for snapshot in snapshots:
        lines.append(
            f"- {snapshot.asset}: mark={snapshot.mark_price:g}, mid={snapshot.mid_price:g} "
            f"funding={snapshot.funding_rate:.8f}, OI={snapshot.open_interest:g}, "
            f"24h volume={snapshot.day_notional_volume:g}"
        )
    return "\n".join(lines)


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def doctor_report(history_path: Path, skip_xurl: bool = False) -> dict:
    checks: dict[str, dict] = {}
    try:
        AlertEventJournal(history_path)
        SocialPostStore(history_path)
        SourceReputationStore(history_path)
        CandleHistory(history_path)
        with sqlite3.connect(history_path) as connection:
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
        required = {"alert_events", "social_posts", "source_reputation", "source_reputation_outcomes", "candle_history", "indicator_history"}
        missing = sorted(required - tables)
        checks["sqlite"] = {"ok": True, "path": str(history_path)}
        checks["schema"] = {"ok": not missing, "required_tables": sorted(required), "missing_tables": missing}
    except (OSError, sqlite3.Error) as exc:
        checks["sqlite"] = {"ok": False, "error": str(exc)}
        checks["schema"] = {"ok": False, "error": str(exc)}
    if skip_xurl:
        checks["xurl"] = {"ok": True, "status": "skipped", "authenticated": False, "blocking": False}
    else:
        xurl_path = shutil.which("xurl")
        if not xurl_path:
            checks["xurl"] = {
                "ok": False,
                "status": "missing",
                "authenticated": False,
                "path": None,
                "blocking": False,
            }
        else:
            result = subprocess.run(
                [xurl_path, "auth", "status"],
                check=False,
                capture_output=True,
                text=True,
            )
            auth_output = (result.stdout + "\n" + result.stderr).lower()
            authenticated = result.returncode == 0 and "no apps registered" not in auth_output and "oauth2: (none)" not in auth_output
            checks["xurl"] = {
                "ok": True,
                "status": "authenticated" if authenticated else "unauthenticated",
                "authenticated": authenticated,
                "path": xurl_path,
                "blocking": False,
            }
    return {"ok": bool(checks.get("sqlite", {}).get("ok") and checks.get("schema", {}).get("ok")), "checks": checks}


def social_run_report(args) -> dict:
    history_path = Path(args.history)
    store = SocialPostStore(history_path)
    if args.offline:
        posts = [SocialPost(**post) for post in store.list_posts(args.query, args.limit)]
        mode = "offline"
    else:
        if not args.query:
            raise ValueError("--query is required unless --offline is used")
        posts = XSearchAdapter().search(args.query, args.limit)
        for post in posts:
            store.upsert(post)
        mode = "live"
    stored_posts = [SocialPost(**post) for post in store.list_posts(args.query, args.limit)]
    analyses = [analyze_post(post) for post in stored_posts]
    reputation_store = SourceReputationStore(Path(args.reputation_history or args.history))
    candidates = aggregate_social_analyses(
        analyses,
        half_life_hours=args.freshness_half_life,
        reputation_store=reputation_store,
        reputation_half_life_hours=args.reputation_half_life,
    )
    observed_at = args.observed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    signals = [social_candidate_to_signal(candidate, observed_at=observed_at) for candidate in candidates]
    invalid = [(signal.signal_id, validate_signal(signal)) for signal in signals]
    invalid = [(signal_id, issues) for signal_id, issues in invalid if issues]
    if invalid:
        raise ValueError("Social signal quality gate failed: " + json.dumps(invalid, ensure_ascii=False))
    event_stats = {"attempted": 0, "recorded": 0, "duplicates_skipped": 0}
    if args.record_events:
        event_stats = AlertEventJournal(history_path).record_many(signals)
    return {
        "mode": mode,
        "query": args.query,
        "posts_fetched": len(posts),
        "posts_in_store": len(stored_posts),
        "candidates": len(candidates),
        "signals_emitted": len(signals),
        "event_stats": event_stats,
        "signals": [json.loads(signals_to_json(signals))][0],
    }


def format_doctor(report: dict, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(report, ensure_ascii=False, indent=2)
    lines = ["## Crypto Radar doctor", "", f"- overall: {'OK' if report['ok'] else 'FAIL'}"]
    for name, check in report["checks"].items():
        status = check.get("status", "ok" if check.get("ok") else "fail")
        lines.append(f"- {name}: {status}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Hyperliquid crypto radar")
    parser.add_argument("command", choices=["snapshot", "indicators", "assets", "events", "social-search", "social-posts", "social-analyze", "source-reputation", "source-reputation-history", "doctor", "social-run", "rss-run", "rss-articles", "github-watch", "github-events", "historical-backfill"], help="Collect signals, inspect emitted events, or check local readiness")
    parser.add_argument("--assets", default=DEFAULT_ASSETS, help="Comma-separated asset allowlist")
    parser.add_argument("--components", action="store_true", help="Render component signals as well as composite")
    parser.add_argument("--history", default="data/crypto_radar.sqlite3", help="SQLite history path")
    parser.add_argument("--backfill-history", default="data/crypto_radar_backfill.sqlite3", help="Separate SQLite archive path for historical-backfill")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", dest="output_format")
    parser.add_argument("--min-severity", choices=["low", "medium", "high"], default="low")
    parser.add_argument("--dedup-cooldown", type=float, default=900.0, help="Seconds before an identical alert may repeat")
    parser.add_argument("--no-dedup", action="store_true", help="Emit matching alerts on every run")
    parser.add_argument("--strict-assets", action="store_true", help="Fail if Hyperliquid does not return every requested ticker")
    parser.add_argument("--jsonl-output", help="Atomically write emitted composite signals to a JSONL file")
    parser.add_argument("--asset", help="Filter event history to one asset")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of events or social posts to return")
    parser.add_argument("--query", help="X search query for social-search or stored social-posts filter")
    parser.add_argument("--store", action="store_true", help="Persist social-search results in SQLite")
    parser.add_argument("--aggregate", action="store_true", help="Aggregate social analyses by asset and claim")
    parser.add_argument("--as-signals", action="store_true", help="Render aggregated social candidates as standard signals")
    parser.add_argument("--record-events", action="store_true", help="Record rendered social signals in the SQLite event journal")
    parser.add_argument("--freshness-half-life", type=positive_float, default=24.0, help="Social evidence half-life in hours")
    parser.add_argument("--reputation-half-life", type=positive_float, default=168.0, help="Source reputation half-life in hours")
    parser.add_argument("--author", help="Source author handle for source-reputation")
    parser.add_argument("--record-outcome", choices=["confirmed", "refuted", "uncertain"], help="Explicit human-reviewed source outcome")
    parser.add_argument("--skip-xurl", action="store_true", help="Skip xurl availability check in doctor")
    parser.add_argument("--offline", action="store_true", help="Run social-run from stored posts without X requests")
    parser.add_argument("--observed-at", help="Deterministic UTC observation timestamp for social-run replay")
    parser.add_argument("--reputation-history", help="SQLite path for source reputation (defaults to --history)")
    parser.add_argument("--reference", default="", help="Evidence URL or claim reference for reputation outcome")
    parser.add_argument("--note", default="", help="Human review note for reputation outcome")
    parser.add_argument("--rss-timeout", type=positive_float, default=20.0, help="RSS request timeout in seconds")
    parser.add_argument("--reddit-only", action="store_true", help="Collect only discovery/Reddit RSS sources")
    parser.add_argument("--rss-config", type=Path, help="YAML RSS source config (defaults to built-in registry)")
    parser.add_argument("--timeframes", default="1m,10m,1h,6h,1d,1w", help="Comma-separated candle timeframes for indicators")
    parser.add_argument("--fetch-limit", type=int, default=80, help="Number of candles to request per timeframe")
    parser.add_argument("--repos", default="", help="Comma-separated GitHub repositories owner/name; defaults to GITHUB_WATCH_REPOS")
    parser.add_argument("--kinds", default="", help="Comma-separated GitHub event kinds: stars,fork,release,push,issue_pr")
    parser.add_argument("--since", default=None, help="Only GitHub events at or after ISO-8601 timestamp")
    parser.add_argument("--start", help="Historical backfill start as ISO-8601 UTC")
    parser.add_argument("--end", help="Historical backfill end as ISO-8601 UTC")
    parser.add_argument("--window-candles", type=int, default=500, help="Source candles per historical API request")
    parser.add_argument("--pause-seconds", type=float, default=0.1, help="Pause between historical API requests")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    assets = {asset.strip().upper() for asset in args.assets.split(",") if asset.strip()}
    if args.command == "historical-backfill":
        if not args.start or not args.end:
            parser.error("--start and --end are required for historical-backfill")
        try:
            report = historical_backfill_report(args)
        except (ProviderError, ValueError, OSError, sqlite3.Error) as exc:
            parser.error(str(exc))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if not report["errors"] else 1
    if args.command == "rss-run":
        try:
            sources = load_rss_sources(args.rss_config) if args.rss_config else DEFAULT_RSS_SOURCES
            report = collect_rss(RssArticleStore(Path(args.history)), sources, timeout=args.rss_timeout, asset=args.asset, reddit_only=args.reddit_only)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "rss-articles":
        articles = RssArticleStore(Path(args.history)).list_articles(asset=args.asset, limit=args.limit)
        print(json.dumps([article.__dict__ for article in articles], ensure_ascii=False, indent=2))
        return 0
    if args.command == "github-watch":
        repos = [item.strip() for item in (args.repos or os.getenv("GITHUB_WATCH_REPOS", "")).split(",") if item.strip()]
        report = poll_repositories(repos, GitHubWatchStore(Path(args.history)), GitHubClient())
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if not report["errors"] else 1
    if args.command == "github-events":
        kinds = [item.strip() for item in args.kinds.split(",") if item.strip()]
        events = GitHubWatchStore(Path(args.history)).list_events(repo=args.repos.strip() or None, kinds=kinds, since=args.since, limit=args.limit)
        print(json.dumps({"events": events, "summary": summarize_events(events)}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "social-run":
        try:
            report = social_run_report(args)
        except (SocialProviderError, ValueError) as exc:
            parser.error(str(exc))
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.output_format == "json" else format_doctor({"ok": True, "checks": report}, args.output_format))
        return 0
    if args.command == "doctor":
        report = doctor_report(Path(args.history), skip_xurl=args.skip_xurl)
        print(format_doctor(report, args.output_format))
        return 0 if report["ok"] else 1
    if args.command == "indicators":
        timeframes = tuple(item.strip() for item in args.timeframes.split(",") if item.strip())
        try:
            report = IndicatorCollector(HyperliquidProvider(), CandleHistory(Path(args.history))).collect(
                assets,
                timeframes,
                observed_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                fetch_limit=args.fetch_limit,
            )
        except (ProviderError, ValueError) as exc:
            parser.error(str(exc))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "source-reputation":
        if not args.author:
            parser.error("--author is required for source-reputation")
        store = SourceReputationStore(Path(args.reputation_history or args.history))
        record = store.record_outcome(args.author, args.record_outcome, args.reference, args.note) if args.record_outcome else store.get(args.author)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0

    if args.command == "source-reputation-history":
        store = SourceReputationStore(Path(args.reputation_history or args.history))
        print(json.dumps(store.list_outcomes(args.author, args.limit), ensure_ascii=False, indent=2))
        return 0

    if args.command == "social-search":
        if not args.query:
            parser.error("--query is required for social-search")
        try:
            posts = XSearchAdapter().search(args.query, args.limit)
        except (SocialProviderError, ValueError) as exc:
            parser.error(str(exc))
        if args.store:
            store = SocialPostStore(Path(args.history))
            for post in posts:
                store.upsert(post)
        print(format_social_posts(posts, args.output_format))
        return 0

    if args.command == "social-analyze":
        stored_posts = SocialPostStore(Path(args.history)).list_posts(args.query, args.limit)
        analyses = [analyze_post(SocialPost(**post)) for post in stored_posts]
        reputation_store = SourceReputationStore(Path(args.reputation_history or args.history))
        output = aggregate_social_analyses(analyses, half_life_hours=args.freshness_half_life, reputation_store=reputation_store, reputation_half_life_hours=args.reputation_half_life) if args.aggregate else analyses
        if args.as_signals:
            if not args.aggregate:
                parser.error("--as-signals requires --aggregate")
            social_signals = [social_candidate_to_signal(item) for item in output]
            if args.record_events:
                invalid = [(signal.signal_id, validate_signal(signal)) for signal in social_signals]
                invalid = [(signal_id, issues) for signal_id, issues in invalid if issues]
                if invalid:
                    parser.error("Social signal quality gate failed: " + json.dumps(invalid, ensure_ascii=False))
                journal = AlertEventJournal(Path(args.history))
                stats = journal.record_many(social_signals)
                print("social_event_record_stats=" + json.dumps(stats, ensure_ascii=False), file=sys.stderr)
            print(signals_to_json(social_signals))
        else:
            print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    if args.command == "social-posts":
        posts = SocialPostStore(Path(args.history)).list_posts(args.query, args.limit)
        lines = ["## Stored social posts", ""]
        for post in posts:
            author = post["author_handle"] or post["author_id"]
            lines.append(f"- {post['created_at']} @{author}: {post['text']}\n  {post['url']}")
        print(json.dumps(posts, ensure_ascii=False, indent=2) if args.output_format == "json" else "\n".join(lines))
        return 0

    if args.command == "events":
        events = AlertEventJournal(Path(args.history)).list_events(args.asset, args.limit)
        print(format_events(events, args.output_format))
        return 0

    if args.command == "assets":
        try:
            snapshots = HyperliquidProvider().fetch(assets)
        except ProviderError as exc:
            parser.error(str(exc))
        unavailable = missing_assets(assets, snapshots)
        if unavailable and args.strict_assets:
            parser.error("Assets not found on Hyperliquid: " + ", ".join(sorted(unavailable)))
        print(format_assets(snapshots, args.output_format))
        return 0

    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    try:
        result = MarketSnapshotService(HyperliquidProvider(), Path(args.history)).collect(
            assets,
            observed_at=observed_at,
            persist_metrics=True,
        )
    except ProviderError as exc:
        parser.error(str(exc))
    if result.unavailable_assets and args.strict_assets:
        parser.error("Assets not found on Hyperliquid: " + ", ".join(sorted(result.unavailable_assets)))

    deduplicator = None if args.no_dedup else AlertDeduplicator(Path(args.history), args.dedup_cooldown)
    event_journal = AlertEventJournal(Path(args.history))
    composites = []
    components_for_markdown = []
    for composite in result.composites:
        if severity_at_least(composite.severity, args.min_severity) and (deduplicator is None or deduplicator.should_emit(composite)):
            event_journal.record(composite)
            composites.append(composite)
            components_for_markdown.append(result.components[composite.asset] if args.components else None)

    if args.jsonl_output:
        write_jsonl(args.jsonl_output, composites)
    if args.output_format == "json":
        print(signals_to_json(composites))
    else:
        for index, composite in enumerate(composites):
            if args.components:
                for component in components_for_markdown[index] or []:
                    print(render_markdown(component))
            print(render_markdown(composite))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
