from __future__ import annotations

from .models import Signal


def validate_signal(signal: Signal) -> list[str]:
    issues: list[str] = []
    if signal.signal_type == "social_claim":
        if not signal.source_urls:
            issues.append("source_urls are required")
        if not signal.requires_manual_review:
            issues.append("manual review is required")
        if signal.auto_trade:
            issues.append("auto_trade must be disabled")
        if not signal.measurements.get("confidence_model"):
            issues.append("confidence_model is required")
        if not signal.measurements.get("confidence_components"):
            issues.append("confidence_components are required")
        if int(signal.measurements.get("evidence_count", 0)) < 1:
            issues.append("evidence_count must be positive")
    return issues


def passes_signal_quality_gate(signal: Signal) -> bool:
    return not validate_signal(signal)
