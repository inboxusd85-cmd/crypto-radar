from __future__ import annotations

from typing import Any


_POSITIVE_EVENT_TYPES = {"funding_institutional", "partnership_adoption", "protocol_upgrade", "listing_delisting", "governance"}
_NEGATIVE_EVENT_TYPES = {"security_incident", "regulatory", "tokenomics_supply"}
_GITHUB_POSITIVE = {"release", "push"}
_GITHUB_NEGATIVE = {"security", "issue"}


def _direction(value: int | float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def synthesize_fundamental_evidence(news: list[dict[str, Any]], github: list[dict[str, Any]]) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    positive = 0
    negative = 0
    for item in news:
        event_type = str(item.get("event_type", "general"))
        score = item.get("score") or {}
        score_direction = _direction(score.get("score", 0)) if isinstance(score, dict) else 0
        taxonomy_direction = 1 if event_type in _POSITIVE_EVENT_TYPES else -1 if event_type in _NEGATIVE_EVENT_TYPES else 0
        direction = score_direction or taxonomy_direction
        if direction > 0:
            positive += 1
        elif direction < 0:
            negative += 1
        if direction:
            evidence.append({"source": "news", "direction": "positive" if direction > 0 else "negative", "event_type": event_type, "title": str(item.get("title", ""))})
    for item in github:
        kind = str(item.get("kind", "unknown"))
        direction = 1 if kind in _GITHUB_POSITIVE else -1 if kind in _GITHUB_NEGATIVE else 0
        if direction > 0:
            positive += 1
        elif direction < 0:
            negative += 1
        if direction:
            evidence.append({"source": "github", "direction": "positive" if direction > 0 else "negative", "kind": kind, "title": str(item.get("title", ""))})
    total = positive + negative
    if total == 0:
        status = "insufficient"
    elif positive and negative and abs(positive - negative) <= 1:
        status = "conflicting"
    elif total < 3:
        status = "emerging"
    else:
        status = "confirmed"
    direction = "positive" if positive > negative else "negative" if negative > positive else "mixed"
    return {
        "status": status,
        "direction": direction,
        "positive_count": positive,
        "negative_count": negative,
        "evidence": evidence,
        "production_impact": "none",
        "read_only": True,
        "note": "Explainable fundamental synthesis only; no market score, model weight, or execution impact.",
    }
