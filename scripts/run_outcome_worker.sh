#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

HISTORY_PATH=${HISTORY:-data/crypto_radar.sqlite3}
LIMIT_VALUE=${LIMIT:-500}

exec .venv/bin/python -m crypto_radar.outcome_worker \
  --db "$HISTORY_PATH" \
  --limit "$LIMIT_VALUE"
