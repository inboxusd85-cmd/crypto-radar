#!/bin/sh
set -eu

case "${1:-}" in
  --help|-h)
    cat <<'USAGE'
Usage: run_market_cycle.sh

Run the read-only market cycle: candles/indicators, composite snapshot,
and forward-outcome materialization. Configure with HISTORY, ASSETS,
TIMEFRAMES, FETCH_LIMIT, OUTCOME_LIMIT, and JSONL_OUTPUT.
USAGE
    exit 0
    ;;
  --*)
    printf '%s\n' "Unknown option: $1" >&2
    printf '%s\n' 'Usage: run_market_cycle.sh' >&2
    exit 2
    ;;
esac

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

HISTORY_PATH=${HISTORY:-data/crypto_radar.sqlite3}
ASSETS_VALUE=${ASSETS:-BTC,ETH,SOL,HYPE,ZEC}
TIMEFRAMES_VALUE=${TIMEFRAMES:-1m,10m,1h,6h,1d,1w}
FETCH_LIMIT_VALUE=${FETCH_LIMIT:-80}
JSONL_VALUE=${JSONL_OUTPUT:-data/alerts.jsonl}
OUTCOME_LIMIT_VALUE=${OUTCOME_LIMIT:-500}
INDICATOR_REPORT=$(mktemp "${TMPDIR:-/tmp}/crypto-radar-indicators.XXXXXX")
OUTCOME_REPORT=$(mktemp "${TMPDIR:-/tmp}/crypto-radar-outcomes.XXXXXX")
trap 'rm -f "$INDICATOR_REPORT" "$OUTCOME_REPORT"' EXIT

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

# First persist closed candles and indicator observations, then emit the
# current composite snapshot. Snapshot deduplication remains enabled by default.
HISTORY="$HISTORY_PATH" ASSETS="$ASSETS_VALUE" TIMEFRAMES="$TIMEFRAMES_VALUE" FETCH_LIMIT="$FETCH_LIMIT_VALUE" \
  "$ROOT_DIR/scripts/run_indicators_pipeline.sh" > "$INDICATOR_REPORT"

.venv/bin/python -m crypto_radar.cli snapshot \
  --assets "$ASSETS_VALUE" \
  --history "$HISTORY_PATH" \
  --format json \
  --jsonl-output "$JSONL_VALUE"

HISTORY="$HISTORY_PATH" LIMIT="$OUTCOME_LIMIT_VALUE" \
  "$ROOT_DIR/scripts/run_outcome_worker.sh" > "$OUTCOME_REPORT"
