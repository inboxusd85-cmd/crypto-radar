from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class AssetMetricResponse(BaseModel):
    asset: str
    mark_price: float
    mid_price: float | None
    funding_rate: float
    open_interest: float
    day_notional_volume: float


class SignalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: str
    asset: str
    signal_type: str
    signal_class: str
    fact: str
    basis: str
    source_urls: list[str]
    severity: str
    confidence: float
    possible_explanations: list[str]
    requires_manual_review: bool
    auto_trade: bool
    measurements: dict[str, Any]
    market_direction: str
    observed_at: str
    evidence_metadata: dict[str, Any]


class OverviewMetaResponse(BaseModel):
    requested_assets: list[str]
    unavailable_assets: list[str]


class OverviewResponse(BaseModel):
    generated_at: str
    assets: list[AssetMetricResponse]
    signals: list[SignalResponse]
    meta: OverviewMetaResponse
