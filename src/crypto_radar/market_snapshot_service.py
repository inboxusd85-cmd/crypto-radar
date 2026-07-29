from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .candle_history import CandleHistory
from .indicator_consensus import generate_indicator_consensus_signal
from .aggregate import aggregate_signals
from .history import MetricHistory
from .market_signals import generate_basis_signals
from .price_signals import generate_price_change_signal
from .providers.hyperliquid import MarketSnapshot
from .signal_generation import generate_funding_signal


class MarketProvider(Protocol):
    def fetch(self, assets: set[str]) -> list[MarketSnapshot]: ...


@dataclass(frozen=True)
class MarketSnapshotResult:
    snapshots: list[MarketSnapshot]
    composites: list
    components: dict[str, list]
    unavailable_assets: set[str]


class MarketSnapshotService:
    def __init__(self, provider: MarketProvider, history_path: str | Path):
        self.provider = provider
        self.history_path = Path(history_path)

    def collect(
        self,
        assets: set[str],
        observed_at: str,
        *,
        persist_metrics: bool = False,
    ) -> MarketSnapshotResult:
        snapshots = self.provider.fetch(assets)
        history = MetricHistory(self.history_path)
        components_by_asset: dict[str, list] = {}
        composites = []

        for snapshot in snapshots:
            funding_history = history.values(snapshot.asset, "funding_rate")
            spread_history = history.values(snapshot.asset, "mark_mid_spread")
            turnover_history = history.values(snapshot.asset, "turnover_ratio")
            mark_price_history = history.values(snapshot.asset, "mark_price")
            open_interest_notional = snapshot.open_interest * snapshot.mark_price
            spread_bps = (
                abs(snapshot.mark_price - snapshot.mid_price) / snapshot.mark_price * 10_000
                if snapshot.mid_price is not None and snapshot.mark_price > 0
                else 0.0
            )
            turnover_ratio = snapshot.day_notional_volume / open_interest_notional if open_interest_notional > 0 else 0.0
            components = [
                generate_funding_signal(snapshot, funding_history),
                *generate_basis_signals(snapshot, spread_history, turnover_history),
                generate_price_change_signal(snapshot, mark_price_history[-1] if mark_price_history else None),
            ]
            indicator_observations = [
                observation
                for timeframe in ("1m", "10m", "1h", "6h", "1d", "1w")
                if (observation := CandleHistory(self.history_path).latest_observation(snapshot.asset, timeframe)) is not None
            ]
            indicator_consensus = generate_indicator_consensus_signal(snapshot.asset, indicator_observations)
            if indicator_consensus is not None:
                components.append(indicator_consensus)
            components_by_asset[snapshot.asset] = components
            composite = aggregate_signals(components, observed_at=observed_at)
            composite.measurements["entry_price"] = snapshot.mark_price
            composites.append(composite)

            if persist_metrics:
                history.append(snapshot.asset, "funding_rate", snapshot.funding_rate)
                history.append(snapshot.asset, "mark_mid_spread", spread_bps)
                history.append(snapshot.asset, "turnover_ratio", turnover_ratio)
                history.append(snapshot.asset, "mark_price", snapshot.mark_price)

        return MarketSnapshotResult(
            snapshots=snapshots,
            composites=composites,
            components=components_by_asset,
            unavailable_assets=assets - {snapshot.asset for snapshot in snapshots},
        )
