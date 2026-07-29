#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

HISTORY_PATH=${HISTORY:-data/crypto_radar.sqlite3}
ASSETS_VALUE=${ASSETS:-BTC,ETH,SOL,HYPE,ZEC}
TIMEFRAMES_VALUE=${TIMEFRAMES:-1m,10m,1h,6h,1d,1w}
FETCH_LIMIT_VALUE=${FETCH_LIMIT:-80}

exec .venv/bin/python -m crypto_radar.cli indicators \
  --assets "$ASSETS_VALUE" \
  --timeframes "$TIMEFRAMES_VALUE" \
  --fetch-limit "$FETCH_LIMIT_VALUE" \
  --history "$HISTORY_PATH" \
  --format json
