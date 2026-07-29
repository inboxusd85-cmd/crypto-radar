#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

if [ "${BUILD_FRONTEND:-0}" = "1" ] || [ ! -f web/dist/index.html ]; then
  npm --prefix web run build
fi

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
export GITHUB_WATCH_REPOS="${GITHUB_WATCH_REPOS:-bitcoin/bitcoin,ethereum/go-ethereum,anza-xyz/agave,hyperliquid-dex/hyperliquid-python-sdk,ZcashFoundation/zebra}"
exec .venv/bin/python -m uvicorn crypto_radar.web.app:create_app --factory --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
