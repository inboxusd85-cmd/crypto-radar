from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .source_reputation import SourceReputationStore


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def freshness_weight(created_at: str, now: datetime | None = None, half_life_hours: float = 24.0) -> float:
    if half_life_hours <= 0:
        raise ValueError("half_life_hours must be positive")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_hours = max(0.0, (current - _parse_timestamp(created_at)).total_seconds() / 3600.0)
    return 2.0 ** (-age_hours / half_life_hours)


def _bounded_quality(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5


def aggregate_social_analyses(
    analyses: list[dict[str, Any]],
    now: datetime | None = None,
    half_life_hours: float = 24.0,
    reputation_store: SourceReputationStore | None = None,
    reputation_half_life_hours: float = 168.0,
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for analysis in analyses:
        claim_type = analysis.get("claim_type", "general")
        for asset in analysis.get("assets", []):
            groups[(asset, claim_type)].append(analysis)

    results: list[dict[str, Any]] = []
    reputation_as_of = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    for (asset, claim_type), items in groups.items():
        evidence_by_url: dict[str, dict[str, Any]] = {}
        authors: set[str] = set()
        for item in items:
            url = str(item.get("source_url", ""))
            if url and url not in evidence_by_url:
                weight = freshness_weight(str(item.get("created_at", "")), now, half_life_hours)
                quality = _bounded_quality(item.get("source_quality", 0.5))
                author_handle = str(item.get("author_handle", "")).strip().lower()
                reputation_record = reputation_store.get(author_handle, as_of=reputation_as_of, half_life_hours=reputation_half_life_hours) if reputation_store and author_handle else None
                reputation_score = reputation_record["score"] if reputation_record else quality
                reputation_decay_factor = reputation_record.get("reputation_decay", 1.0) if reputation_record else 1.0
                reputation_outcomes = reputation_store.list_outcomes(author_handle, limit=1) if reputation_store and author_handle else []
                last_reviewed_at = reputation_record.get("last_reviewed_at", reputation_outcomes[0]["recorded_at"] if reputation_outcomes else "") if reputation_record else ""
                effective_quality = (quality + reputation_score) / 2.0 if reputation_store else quality
                evidence_by_url[url] = {
                    "url": url,
                    "post_id": item.get("post_id", ""),
                    "author_handle": item.get("author_handle", ""),
                    "text": item.get("text", ""),
                    "created_at": item.get("created_at", ""),
                    "freshness_weight": round(weight, 4),
                    "source_quality": round(quality, 4),
                    "reputation_score": round(reputation_score, 4),
                    "reputation_decay": round(reputation_decay_factor, 4),
                    "reputation_outcome_count": (reputation_record["confirmed"] + reputation_record["refuted"] + reputation_record["uncertain"]) if reputation_record else 0,
                    "reputation_last_reviewed_at": last_reviewed_at,
                    "effective_quality": round(effective_quality, 4),
                }
                author = item.get("author_handle") or item.get("post_id")
                if author:
                    authors.add(str(author).lower())
        evidence = list(evidence_by_url.values())
        independent_authors = len(authors)
        severity = "high" if independent_authors >= 3 else "medium" if independent_authors >= 2 else "low"
        mean_confidence = sum(float(item.get("confidence", 0.0)) for item in items) / len(items)
        consensus = min(1.0, independent_authors / 3.0)
        confidence = round(min(0.95, mean_confidence * 0.6 + consensus * 0.4), 4)
        freshness = sum(item["freshness_weight"] for item in evidence) / len(evidence) if evidence else 0.0
        source_quality = sum(item["source_quality"] for item in evidence) / len(evidence) if evidence else 0.0
        reputation = sum(item["reputation_score"] for item in evidence) / len(evidence) if evidence else 0.0
        reputation_decay_factor = sum(item["reputation_decay"] for item in evidence) / len(evidence) if evidence else 1.0
        effective_quality = sum(item["effective_quality"] for item in evidence) / len(evidence) if evidence else 0.0
        reputation_evidence_count = sum(1 for item in evidence if item["reputation_outcome_count"] > 0)
        reputation_reviewed_authors = len({item["author_handle"].lower() for item in evidence if item["reputation_outcome_count"] > 0 and item["author_handle"]})
        reputation_last_reviewed_at = max((item["reputation_last_reviewed_at"] for item in evidence), default="")
        freshness_weighted_confidence = round(min(0.95, mean_confidence * 0.6 * freshness + consensus * 0.4), 4)
        quality_weighted_confidence = round(min(0.95, freshness_weighted_confidence * (0.5 + 0.5 * effective_quality)), 4)
        results.append({
            "asset": asset,
            "claim_type": claim_type,
            "severity": severity,
            "confidence": confidence,
            "freshness": round(freshness, 4),
            "source_quality": round(source_quality, 4),
            "reputation": round(reputation, 4),
            "reputation_decay": round(reputation_decay_factor, 4),
            "effective_quality": round(effective_quality, 4),
            "reputation_evidence_count": reputation_evidence_count,
            "reputation_reviewed_authors": reputation_reviewed_authors,
            "reputation_last_reviewed_at": reputation_last_reviewed_at,
            "freshness_weighted_confidence": freshness_weighted_confidence,
            "quality_weighted_confidence": quality_weighted_confidence,
            "independent_authors": independent_authors,
            "evidence_count": len(evidence),
            "evidence": evidence,
            "requires_manual_review": True,
            "explanation": f"{len(evidence)} social evidence item(s) from {independent_authors} independent author(s)",
        })
    return sorted(results, key=lambda item: (item["severity"], item["asset"]), reverse=True)
