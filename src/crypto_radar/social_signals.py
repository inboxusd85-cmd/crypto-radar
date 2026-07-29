from __future__ import annotations

from .models import Signal


def social_candidate_to_signal(candidate: dict, observed_at: str | None = None) -> Signal:
    asset = str(candidate["asset"])
    claim_type = str(candidate["claim_type"])
    evidence = candidate.get("evidence", [])
    source_urls = [str(item["url"]) for item in evidence if item.get("url")]
    independent_authors = int(candidate.get("independent_authors", 0))
    evidence_count = int(candidate.get("evidence_count", len(evidence)))
    fact = f"Social evidence indicates {claim_type} claim for {asset}"
    reputation_decay = float(candidate.get("reputation_decay", 1.0))
    reputation_reviewed_authors = int(candidate.get("reputation_reviewed_authors", 0))
    reputation_last_reviewed_at = str(candidate.get("reputation_last_reviewed_at", ""))
    basis = (
        f"{evidence_count} social evidence item(s) from {independent_authors} independent author(s); "
        f"claim_type={claim_type}"
    )
    if reputation_reviewed_authors or reputation_last_reviewed_at:
        basis += f"; reputation_decay={reputation_decay:g}; reviewed_authors={reputation_reviewed_authors}"
        if reputation_last_reviewed_at:
            basis += f"; last_reviewed={reputation_last_reviewed_at}"
    raw_confidence = float(candidate.get("confidence", 0.0))
    freshness = float(candidate.get("freshness", 1.0))
    freshness_weighted_confidence = float(candidate.get("freshness_weighted_confidence", raw_confidence))
    source_quality = float(candidate.get("source_quality", 0.5))
    confidence = float(candidate.get("quality_weighted_confidence", freshness_weighted_confidence))
    basis += (
        f"; raw={raw_confidence:g}; freshness={freshness:g}; source_quality={source_quality:g}"
        f"; reputation={float(candidate.get('reputation', 0.5)):g}; weighted={confidence:g}"
    )
    return Signal(
        asset=asset,
        signal_type="social_claim",
        fact=fact,
        basis=basis,
        source_urls=source_urls,
        severity=str(candidate.get("severity", "low")),
        confidence=confidence,
        requires_manual_review=True,
        auto_trade=False,
        measurements={
            "factor_signature": claim_type,
            "confidence_model": "social-quality-v1",
            "confidence_components": {
                "raw": raw_confidence,
                "freshness": freshness,
                "freshness_weighted": freshness_weighted_confidence,
                "source_quality": source_quality,
                "reputation": float(candidate.get("reputation", 0.5)),
                "reputation_decay": reputation_decay,
                "effective_quality": float(candidate.get("effective_quality", source_quality)),
                "weighted": confidence,
            },
            "independent_authors": independent_authors,
            "evidence_count": evidence_count,
            "raw_confidence": raw_confidence,
            "freshness": freshness,
            "freshness_weighted_confidence": freshness_weighted_confidence,
            "source_quality": source_quality,
            "reputation": float(candidate.get("reputation", 0.5)),
            "reputation_decay": float(candidate.get("reputation_decay", 1.0)),
            "effective_quality": float(candidate.get("effective_quality", source_quality)),
            "reputation_evidence_count": int(candidate.get("reputation_evidence_count", 0)),
            "reputation_reviewed_authors": int(candidate.get("reputation_reviewed_authors", 0)),
            "reputation_last_reviewed_at": candidate.get("reputation_last_reviewed_at", ""),
            "quality_weighted_confidence": confidence,
        },
        observed_at=observed_at or Signal.__dataclass_fields__["observed_at"].default_factory(),
    )
