from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Any


@dataclass
class Signal:
    asset: str
    signal_type: str
    fact: str
    basis: str
    source_urls: list[str]
    severity: str = "low"
    confidence: float = 0.0
    possible_explanations: list[str] = field(default_factory=list)
    requires_manual_review: bool = True
    auto_trade: bool = False
    measurements: dict[str, Any] = field(default_factory=dict)
    market_direction: str = "неопределённое"
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"))

    @property
    def signal_class(self) -> str:
        if self.signal_type == "social_claim":
            return "social"
        if self.signal_type in {"multi_timeframe_indicators", "multi_timeframe_consensus"}:
            return "technical"
        if self.signal_type == "composite_market_risk":
            return "composite"
        return "market"

    @property
    def evidence_metadata(self) -> dict[str, Any]:
        return {
            "source_count": len(self.source_urls),
            "has_sources": bool(self.source_urls),
            "confidence": self.confidence,
            "requires_manual_review": self.requires_manual_review,
        }

    @property
    def signal_id(self) -> str:
        detail = self.measurements.get("factor_signature", self.basis) if self.signal_type in {"composite_market_risk", "social_claim"} else self.basis
        payload = "\x1f".join((self.asset, self.signal_type, self.severity, str(detail)))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def __post_init__(self) -> None:
        if not self.asset.strip():
            raise ValueError("asset is required")
        if not self.signal_type.strip():
            raise ValueError("signal_type is required")
        if not self.fact.strip():
            raise ValueError("fact is required")
        if not self.basis.strip():
            raise ValueError("basis is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.auto_trade:
            raise ValueError("auto_trade is disabled in crypto-radar")
