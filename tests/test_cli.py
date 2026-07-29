from crypto_radar.candle_history import CandleHistory
from crypto_radar.cli import build_backfill_windows
from crypto_radar.providers.hyperliquid import Candle

from pathlib import Path
import subprocess


def test_build_backfill_windows_uses_source_interval_and_covers_range() -> None:
    windows = build_backfill_windows(0, 360_000, source_interval_ms=60_000, window_candles=2)
    assert windows == [(0, 120_000), (120_000, 240_000), (240_000, 360_000)]


def test_archive_upsert_preserves_old_intraday_candles(tmp_path: Path) -> None:
    history = CandleHistory(tmp_path / "archive.sqlite3", max_candles=1, retention_days=1)
    candles = [
        Candle("BTC", "1h", 0, 1, 2, 0.5, 1.5, 10),
        Candle("BTC", "1h", 3_600_000, 1.5, 2.5, 1, 2, 12),
    ]
    history.archive_upsert_many(candles)
    assert len(history.list_candles("BTC", "1h")) == 2


def test_market_cycle_help_is_non_destructive() -> None:
    script = Path(__file__).parents[1] / "scripts" / "run_market_cycle.sh"
    result = subprocess.run([str(script), "--help"], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "run_indicators_pipeline.sh" not in result.stdout


def test_market_cycle_uses_macos_safe_mktemp_templates() -> None:
    script = Path(__file__).parents[1] / "scripts" / "run_market_cycle.sh"
    content = script.read_text()
    assert 'mktemp "${TMPDIR:-/tmp}/crypto-radar-indicators.XXXXXX"' in content
    assert 'mktemp "${TMPDIR:-/tmp}/crypto-radar-outcomes.XXXXXX"' in content


def test_market_cycle_launcher_runs_indicators_then_snapshot() -> None:
    script = Path(__file__).parents[1] / "scripts" / "run_market_cycle.sh"
    content = script.read_text()
    assert "run_indicators_pipeline.sh" in content
    assert "crypto_radar.cli snapshot" in content
    assert "run_outcome_worker.sh" in content
    assert "--jsonl-output" in content
