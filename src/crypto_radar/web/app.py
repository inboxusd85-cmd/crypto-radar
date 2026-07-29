from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..events import AlertEventJournal
from ..candle_history import CandleHistory
from ..indicator_aggregation import aggregate_indicator_signals
from ..indicator_collector import IndicatorCollector
from ..indicator_signals import generate_indicator_signal
from ..history import MetricHistory
from ..market_snapshot_service import MarketProvider, MarketSnapshotService
from ..outcomes import OutcomeReviewStore, OutcomeStore, REVIEW_STATUSES, build_time_split_report, build_validation_depth_report, build_validation_policy_report, build_validation_report, materialize_event_outcomes, prepare_news_training_dataset, summarize_quality, summarize_news_event_types, summarize_news_readiness, summarize_news_training_readiness, _epoch_ms
from ..providers.hyperliquid import HyperliquidProvider, ProviderError, SUPPORTED_CANDLE_INTERVALS
from ..rss_store import RssArticleStore
from ..news_ranker import extract_news_features
from ..news_scoring import score_news
from ..outcomes import calculate_news_outcomes
from ..outcome_worker import build_archive_validation_report
from ..news_summary import summarize_news_ru
from ..github_watch import GitHubClient, GitHubWatchStore, poll_repositories, summarize_events
from ..fundamental import synthesize_fundamental_evidence

FUNDAMENTAL_REPOS = {
    "BTC": ["bitcoin/bitcoin"],
    "ETH": ["ethereum/go-ethereum"],
    "SOL": ["anza-xyz/agave"],
    "HYPE": ["hyperliquid-dex/hyperliquid-python-sdk"],
    "ZEC": ["ZcashFoundation/zebra"],
}
from ..serialization import signal_to_dict
from ..support_resistance import calculate_levels
from .schemas import AssetMetricResponse, OverviewMetaResponse, OverviewResponse, SignalResponse


DEFAULT_HISTORY_PATH = Path("data/crypto_radar.sqlite3")
WORKER_STALE_AFTER_SECONDS = 15 * 60


class ReviewUpdate(BaseModel):
    status: str
    note: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_worker_health(worker: dict | None, now: float | None = None) -> dict | None:
    if worker is None:
        return None
    current_time = time.time() if now is None else float(now)
    completed_at = worker.get("completed_at")
    if completed_at is None:
        return {**worker, "status": "not_started", "age_seconds": None, "stale": True}
    age_seconds = max(0, int(current_time - float(completed_at)))
    stale = age_seconds > WORKER_STALE_AFTER_SECONDS
    if worker.get("errors", 0):
        status = "error"
    elif stale:
        status = "stale"
    elif worker.get("pending", 0):
        status = "pending"
    else:
        status = "ok"
    return {**worker, "status": status, "age_seconds": age_seconds, "stale": stale}


def parse_assets(raw_assets: str) -> set[str]:
    assets = {asset.strip().upper() for asset in raw_assets.split(",") if asset.strip()}
    if not assets:
        raise HTTPException(status_code=422, detail="At least one asset is required")
    if len(assets) > 20:
        raise HTTPException(status_code=422, detail="A maximum of 20 assets is allowed")
    return assets


def build_event_outcomes(event: dict, history_path: Path) -> dict:
    return materialize_event_outcomes(event, CandleHistory(history_path), OutcomeStore(history_path))


def create_app(
    history_path: Path | None = None,
    provider: MarketProvider | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Crypto Radar API", version="0.1.0")
    app.state.history_path = history_path or DEFAULT_HISTORY_PATH
    app.state.provider = provider or HyperliquidProvider()
    app.state.last_market_success_at = None
    app.state.last_indicator_success_at = None
    default_static_dir = Path(__file__).resolve().parents[3] / "web" / "dist"
    static_dir = static_dir or default_static_dir

    @app.get("/api/v1/health")
    def health() -> dict:
        AlertEventJournal(app.state.history_path)
        worker = OutcomeStore(app.state.history_path).worker_state()
        worker = normalize_worker_health(worker)
        return {
            "status": "ok",
            "api_version": app.version,
            "database": {"ok": True},
            "provider": {
                "name": "hyperliquid",
                "last_success_at": app.state.last_market_success_at,
                "last_indicator_success_at": app.state.last_indicator_success_at,
            },
            "social": {
                "enabled": False,
                "status": "available_on_demand",
                "mode": "separate_pipeline",
                "entrypoint": "social-run",
                "included_in_market_composite": False,
                "requires_manual_review": True,
            },
            "outcomes": {"worker": worker},
        }

    @app.get("/api/v1/overview", response_model=OverviewResponse)
    def overview(assets: str = Query("BTC,ETH,SOL,HYPE,ZEC")) -> JSONResponse:
        requested_assets = parse_assets(assets)
        generated_at = utc_now()
        try:
            result = MarketSnapshotService(app.state.provider, app.state.history_path).collect(
                requested_assets,
                observed_at=generated_at,
                persist_metrics=False,
            )
        except ProviderError as exc:
            raise HTTPException(status_code=503, detail="Market data provider is unavailable") from exc
        app.state.last_market_success_at = generated_at

        payload = OverviewResponse(
            generated_at=generated_at,
            assets=[
                AssetMetricResponse(
                    asset=snapshot.asset,
                    mark_price=snapshot.mark_price,
                    mid_price=snapshot.mid_price,
                    funding_rate=snapshot.funding_rate,
                    open_interest=snapshot.open_interest,
                    day_notional_volume=snapshot.day_notional_volume,
                )
                for snapshot in result.snapshots
            ],
            signals=[SignalResponse(**signal_to_dict(signal)) for signal in result.composites],
            meta=OverviewMetaResponse(
                requested_assets=sorted(requested_assets),
                unavailable_assets=sorted(result.unavailable_assets),
            ),
        )
        return JSONResponse(payload.model_dump(), headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/events")
    def events(
        asset: str | None = None,
        severity: Literal["low", "medium", "high"] | None = None,
        before: float | None = None,
        cursor: str | None = None,
        limit: int = Query(50, ge=1, le=100),
    ) -> dict:
        page = AlertEventJournal(app.state.history_path).list_events_page(
            asset=asset,
            severity=severity,
            before=before,
            cursor=cursor,
            limit=limit,
        )
        return {"events": page["events"], "next_before": page["next_before"], "next_cursor": page["next_cursor"], "count": len(page["events"])}

    @app.get("/api/v1/reviews")
    def reviews(
        status: Literal["pending", "confirmed", "refuted", "deferred"] | None = None,
        limit: int = Query(100, ge=1, le=500),
    ) -> dict:
        store = OutcomeReviewStore(app.state.history_path)
        stored = {item["event_id"]: item for item in store.list_reviews(limit=500)}
        queue: list[dict] = []
        seen: set[str] = set()
        for event in AlertEventJournal(app.state.history_path).list_events(limit=limit):
            if not event.get("requires_manual_review", True):
                continue
            event_id = event.get("event_id")
            item = stored.get(event_id, {"event_id": event_id, "status": "pending", "note": "", "reviewed_at": None})
            if status is None or item["status"] == status:
                queue.append({**event, "review": item, "outcomes": build_event_outcomes(event, app.state.history_path)})
                seen.add(event_id)
        for event_id, item in stored.items():
            if event_id in seen or (status is not None and item["status"] != status):
                continue
            queue.append({"event_id": event_id, "review": item})
        return {"reviews": queue[:limit], "count": len(queue[:limit])}

    @app.get("/api/v1/reviews/summary")
    def review_summary() -> dict:
        store = OutcomeReviewStore(app.state.history_path)
        stored = {item["event_id"]: item for item in store.list_reviews(limit=500)}
        rows = []
        for event in AlertEventJournal(app.state.history_path).list_events(limit=500):
            item = stored.get(event.get("event_id"))
            if item is None or item["status"] == "pending":
                continue
            rows.append({**event, "review": item, "outcomes": build_event_outcomes(event, app.state.history_path)})
        return summarize_quality(rows)

    @app.get("/api/v1/reviews/{event_id}/outcomes")
    def review_outcomes(event_id: str) -> dict:
        event = next((item for item in AlertEventJournal(app.state.history_path).list_events(limit=500) if item.get("event_id") == event_id), None)
        if event is None:
            raise HTTPException(status_code=404, detail="Review event not found")
        outcomes = build_event_outcomes(event, app.state.history_path)
        entry_price = event.get("measurements", {}).get("entry_price", event.get("measurements", {}).get("mark_price"))
        return {"event_id": event_id, "entry_price": entry_price, "outcomes": outcomes}

    @app.get("/api/v1/reviews/validation")
    def review_validation() -> dict:
        store = OutcomeReviewStore(app.state.history_path)
        events = AlertEventJournal(app.state.history_path).list_events(limit=500)
        stored = {item["event_id"]: item for item in store.list_reviews(limit=500)}
        rows = []
        collection_rows = []
        for event in events:
            materialized = {**event, "outcomes": build_event_outcomes(event, app.state.history_path)}
            collection_rows.append(materialized)
            item = stored.get(event.get("event_id"))
            if item is None or item["status"] == "pending":
                continue
            rows.append({**materialized, "review": item})
        report = build_validation_report(rows)
        report["collection"] = build_validation_report(collection_rows)
        return report

    @app.get("/api/v1/reviews/validation/time-split")
    def review_validation_time_split() -> dict:
        events = AlertEventJournal(app.state.history_path).list_events(limit=500)
        rows = [{**event, "outcomes": build_event_outcomes(event, app.state.history_path)} for event in events]
        return build_time_split_report(rows)

    @app.get("/api/v1/reviews/validation/archive")
    def review_validation_archive(
        limit: int = Query(500, ge=1, le=10000),
        train_fraction: float = Query(0.8, ge=0.5, lt=1.0),
    ) -> dict:
        archive_path = Path(os.getenv("CRYPTO_RADAR_BACKFILL_HISTORY", "data/crypto_radar_backfill.sqlite3"))
        return build_archive_validation_report(
            app.state.history_path,
            archive_path,
            limit=limit,
            train_fraction=train_fraction,
        )

    @app.get("/api/v1/reviews/validation/depth")
    def review_validation_depth() -> dict:
        store = OutcomeReviewStore(app.state.history_path)
        stored = {item["event_id"]: item for item in store.list_reviews(limit=500)}
        rows = []
        for event in AlertEventJournal(app.state.history_path).list_events(limit=500):
            item = stored.get(event.get("event_id"))
            if item is None or item["status"] == "pending":
                continue
            rows.append({**event, "review": item, "outcomes": build_event_outcomes(event, app.state.history_path)})
        return build_validation_depth_report(rows)


    @app.get("/api/v1/reviews/validation/policy")
    def review_validation_policy() -> dict:
        store = OutcomeReviewStore(app.state.history_path)
        stored = {item["event_id"]: item for item in store.list_reviews(limit=500)}
        rows = []
        for event in AlertEventJournal(app.state.history_path).list_events(limit=500):
            item = stored.get(event.get("event_id"))
            if item is None or item["status"] == "pending":
                continue
            rows.append({**event, "review": item, "outcomes": build_event_outcomes(event, app.state.history_path)})
        return build_validation_policy_report(build_validation_depth_report(rows))


    @app.put("/api/v1/reviews/{event_id}")
    def update_review(event_id: str, payload: ReviewUpdate) -> dict:
        if payload.status not in REVIEW_STATUSES:
            raise HTTPException(status_code=422, detail="Unsupported review status")
        event = next((item for item in AlertEventJournal(app.state.history_path).list_events(limit=500) if item.get("event_id") == event_id), None)
        if event is None:
            raise HTTPException(status_code=404, detail="Review event not found")
        return OutcomeReviewStore(app.state.history_path).review(
            event_id,
            payload.status,
            reviewed_at=datetime.now(timezone.utc).timestamp(),
            note=payload.note.strip(),
        )

    @app.get("/api/v1/assets/{asset}")
    def asset_detail(asset: str) -> dict:
        requested_asset = asset.strip().upper()
        if not requested_asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        generated_at = utc_now()
        try:
            result = MarketSnapshotService(app.state.provider, app.state.history_path).collect(
                {requested_asset},
                observed_at=generated_at,
                persist_metrics=False,
            )
        except ProviderError as exc:
            raise HTTPException(status_code=503, detail="Market data provider is unavailable") from exc
        app.state.last_market_success_at = generated_at
        if not result.snapshots:
            raise HTTPException(status_code=404, detail="Asset not found")
        snapshot = result.snapshots[0]
        events_page = AlertEventJournal(app.state.history_path).list_events_page(asset=requested_asset, limit=50)
        return {
            "generated_at": generated_at,
            "asset": AssetMetricResponse(
                asset=snapshot.asset,
                mark_price=snapshot.mark_price,
                mid_price=snapshot.mid_price,
                funding_rate=snapshot.funding_rate,
                open_interest=snapshot.open_interest,
                day_notional_volume=snapshot.day_notional_volume,
            ).model_dump(),
            "signals": [SignalResponse(**signal_to_dict(signal)).model_dump() for signal in result.composites],
            "events": events_page["events"],
        }

    @app.get("/api/v1/github/watch")
    def github_watch(repo: str | None = None, kinds: str | None = None, since: str | None = None, limit: int = Query(50, ge=1, le=200)) -> dict:
        repos = [item.strip() for item in os.getenv("GITHUB_WATCH_REPOS", "").split(",") if item.strip()]
        event_kinds = [item.strip() for item in (kinds or "").split(",") if item.strip()]
        store = GitHubWatchStore(app.state.history_path)
        events = store.list_events(repo=repo, kinds=event_kinds, since=since, limit=limit)
        return {"enabled": bool(repos), "repos": repos, "events": events, "count": len(events), "summary": summarize_events(events), "polling": "explicit_or_cron", "filters": {"repo": repo, "kinds": event_kinds, "since": since}}

    @app.post("/api/v1/github/watch/poll")
    def github_watch_poll() -> dict:
        repos = [item.strip() for item in os.getenv("GITHUB_WATCH_REPOS", "").split(",") if item.strip()]
        if not repos:
            return {"enabled": False, "repositories": 0, "changed": 0, "events": 0, "errors": [], "reason": "GITHUB_WATCH_REPOS is not configured"}
        return {"enabled": True, **poll_repositories(repos, GitHubWatchStore(app.state.history_path), GitHubClient())}

    @app.get("/api/v1/assets/{asset}/history")
    def asset_history(
        asset: str,
        metric: Literal["funding_rate", "mark_mid_spread", "turnover_ratio", "mark_price"] | None = None,
        limit: int = Query(100, ge=1, le=100),
    ) -> dict:
        requested_asset = asset.strip().upper()
        if not requested_asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        history = MetricHistory(app.state.history_path)
        metrics = [metric] if metric else ["funding_rate", "mark_mid_spread", "turnover_ratio", "mark_price"]
        return {
            "asset": requested_asset,
            "metrics": {name: history.series(requested_asset, name, limit=limit) for name in metrics},
        }

    @app.get("/api/v1/assets/{asset}/fundamental")
    def asset_fundamental(asset: str, limit: int = Query(20, ge=1, le=100)) -> dict:
        requested_asset = asset.strip().upper()
        if not requested_asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        articles = RssArticleStore(app.state.history_path).list_articles(asset=requested_asset, limit=limit)
        news_items = [
            {
                "article_id": article.article_id,
                "title": article.title,
                "url": article.url,
                "published_at": article.published_at,
                "source_name": article.source_name,
                "source_tier": article.source_tier,
                "event_type": article.event_type,
                "score": score_news(article.title, article.summary),
                "provenance": "rss",
            }
            for article in articles
        ]
        mapped_repos = FUNDAMENTAL_REPOS.get(requested_asset, [])
        github_events = GitHubWatchStore(app.state.history_path).list_events(limit=200)
        github_items = [
            {**event, "provenance": "github_watch"}
            for event in github_events
            if event.get("repo") in mapped_repos
        ][:limit]
        synthesis = synthesize_fundamental_evidence(news_items, github_items)
        return {
            "asset": requested_asset,
            "read_only": True,
            "production_impact": "none",
            "synthesis": synthesis,
            "news": {"count": len(news_items), "items": news_items, "status": "ready" if news_items else "empty"},
            "github": {
                "mapped_repos": mapped_repos,
                "events": github_items,
                "status": "ready" if github_items else "empty" if mapped_repos else "unmapped",
            },
            "note": "Fundamental evidence is observational and does not alter market scoring, execution, or model weights.",
        }

    @app.get("/api/v1/assets/{asset}/news/dataset")
    def asset_news_dataset(asset: str, limit: int = Query(100, ge=1, le=500)) -> dict:
        requested_asset = asset.strip().upper()
        if not requested_asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        articles = RssArticleStore(app.state.history_path).list_articles(asset=requested_asset, limit=limit)
        records = []
        for article in articles:
            score = score_news(article.title, article.summary)
            try:
                outcomes = calculate_news_outcomes(CandleHistory(app.state.history_path), requested_asset, "1h", article.published_at)
            except (TypeError, ValueError, OverflowError):
                outcomes = {"entry": {"status": "pending", "reason": "invalid_publication_time"}, "outcomes": {horizon: {"status": "pending", "reason": "invalid_publication_time"} for horizon in ("1h", "6h", "1d", "1w")}}
            records.append({
                "article_id": article.article_id,
                "published_at": article.published_at,
                "features": list(article.ranking_features or extract_news_features(article.title, article.summary).vector()),
                "event_type": article.event_type,
                "production_model": "rules-v1",
                "production_score": score["score"],
                "shadow_model": "xgboost-news-v1",
                "label": None,
                "outcomes": outcomes,
            })
        readiness = summarize_news_readiness(records)
        training_readiness = summarize_news_training_readiness(readiness)
        training_preparation = {}
        for horizon in ("1h", "6h", "1d", "1w"):
            preparation = prepare_news_training_dataset(records, horizon)
            training_preparation[horizon] = {
                key: preparation[key]
                for key in ("status", "horizon", "ready_count", "coverage_pct", "reasons")
                if key in preparation
            }
        return {"asset": requested_asset, "count": len(records), "label_status": "unlabeled", "read_only": True, "readiness": readiness, "event_type_breakdown": summarize_news_event_types(records), "training_readiness": training_readiness, "training_preparation": training_preparation, "records": records}

    @app.get("/api/v1/assets/{asset}/news")
    def asset_news(asset: str, limit: int = Query(3, ge=1, le=3)) -> dict:
        requested_asset = asset.strip().upper()
        if not requested_asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        articles = RssArticleStore(app.state.history_path).list_articles(asset=requested_asset, limit=limit)
        return {
            "asset": requested_asset,
            "count": len(articles),
            "news": [
                {
                    "source_name": article.source_name,
                    "source_tier": article.source_tier,
                    "title": article.title,
                    "url": article.url,
                    "published_at": article.published_at,
                    "summary": article.summary,
                    "summary_ru": summarize_news_ru(article.title, article.summary),
                    "assets": list(article.assets),
                    "event_type": article.event_type,
                    "score": score_news(article.title, article.summary),
                    "ranking": {
                        "production_model": "rules-v1",
                        "shadow_model": "xgboost-news-v1",
                        "features": list(article.ranking_features or extract_news_features(article.title, article.summary).vector()),
                    },
                }
                for article in articles
            ],
        }

    @app.get("/api/v1/assets/{asset}/indicators")
    def asset_indicators(asset: str, timeframes: str = Query("1m,10m,1h,6h,1d,1w")) -> dict:
        requested_asset = asset.strip().upper()
        requested_timeframes = [item.strip() for item in timeframes.split(",") if item.strip()]
        if not requested_asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        unknown = sorted(set(requested_timeframes) - set(SUPPORTED_CANDLE_INTERVALS))
        if unknown:
            raise HTTPException(status_code=422, detail=f"Unsupported timeframes: {', '.join(unknown)}")
        if not requested_timeframes:
            raise HTTPException(status_code=422, detail="At least one timeframe is required")
        generated_at = utc_now()
        provider = app.state.provider
        if not hasattr(provider, "fetch_candles"):
            raise HTTPException(status_code=503, detail="Candle provider is unavailable")
        try:
            result = IndicatorCollector(provider, CandleHistory(app.state.history_path)).collect(
                {requested_asset},
                tuple(dict.fromkeys(requested_timeframes)),
                observed_at=generated_at,
            )
        except (ProviderError, ValueError) as exc:
            raise HTTPException(status_code=503, detail="Candle data provider is unavailable") from exc
        app.state.last_indicator_success_at = generated_at
        signals = [SignalResponse(**signal).model_dump() for signal in result["signals"]]
        aggregate = aggregate_indicator_signals([signal["measurements"] for signal in signals])
        return {"asset": requested_asset, "generated_at": generated_at, "signals": signals, "aggregate": aggregate}

    @app.get("/api/v1/assets/{asset}/candles")
    def asset_candles(
        asset: str,
        timeframe: str = Query("1h"),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict:
        requested_asset = asset.strip().upper()
        if not requested_asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        if timeframe not in SUPPORTED_CANDLE_INTERVALS:
            raise HTTPException(status_code=422, detail=f"Unsupported timeframe: {timeframe}")
        candles = CandleHistory(app.state.history_path).list_candles(requested_asset, timeframe, limit)
        return {
            "asset": requested_asset,
            "timeframe": timeframe,
            "candles": [
                {"open_time": candle.open_time, "open": candle.open, "high": candle.high, "low": candle.low, "close": candle.close, "volume": candle.volume, "timeframe": candle.timeframe}
                for candle in candles
            ],
        }

    @app.get("/api/v1/assets/{asset}/levels")
    def asset_levels(asset: str) -> dict:
        requested_asset = asset.strip().upper()
        if not requested_asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        candles = CandleHistory(app.state.history_path).list_candles(requested_asset, "1d", limit=500)
        levels = calculate_levels(candles)
        return {
            "asset": requested_asset,
            "levels": [
                {"period": level.period, "strength": level.strength, "support": level.support, "resistance": level.resistance, "start": level.start, "end": level.end}
                for level in levels
            ],
        }

    @app.get("/api/v1/assets/{asset}/indicator-history")
    def asset_indicator_history(
        asset: str,
        timeframe: str = Query("1h"),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict:
        requested_asset = asset.strip().upper()
        if not requested_asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        if timeframe not in SUPPORTED_CANDLE_INTERVALS:
            raise HTTPException(status_code=422, detail=f"Unsupported timeframe: {timeframe}")
        observations = CandleHistory(app.state.history_path).list_observations(requested_asset, timeframe, limit)
        return {"asset": requested_asset, "timeframe": timeframe, "observations": observations}

    if static_dir is not None and (static_dir / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets") if (static_dir / "assets").is_dir() else None

        @app.get("/{path:path}", include_in_schema=False)
        def spa_fallback(path: str) -> FileResponse:
            requested = static_dir / path
            if path and requested.is_file() and static_dir in requested.parents:
                return FileResponse(requested)
            return FileResponse(static_dir / "index.html")

    return app
