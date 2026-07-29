#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

MODE=${1:-offline}
HISTORY=${HISTORY:-data/crypto_radar.sqlite3}
QUERY=${QUERY:-'(HYPE OR ZEC) lang:en -is:retweet'}
LIMIT=${LIMIT:-20}
OUTPUT_FORMAT=${OUTPUT_FORMAT:-json}

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="$ROOT_DIR/.venv/bin/python"

if [ "$MODE" != "offline" ] && [ "$MODE" != "live" ]; then
  printf '%s\n' "usage: $0 [offline|live]" >&2
  exit 64
fi

if [ "$MODE" = "live" ]; then
  if ! command -v xurl >/dev/null 2>&1; then
    printf '%s\n' "xurl is required for live social monitoring" >&2
    exit 69
  fi
  XURL_STATUS=$(xurl auth status 2>&1 || true)
  case "$XURL_STATUS" in
    *"No apps registered"*|*"oauth2: (none)"*|*"NoAuthMethod"*)
      printf '%s\n' "xurl authentication is not ready; run xurl auth status after manual OAuth setup" >&2
      exit 69
      ;;
  esac
  exec "$PYTHON" -m crypto_radar.cli social-run \
    --history "$HISTORY" \
    --query "$QUERY" \
    --limit "$LIMIT" \
    --record-events \
    --format "$OUTPUT_FORMAT"
fi

exec "$PYTHON" -m crypto_radar.cli social-run \
  --history "$HISTORY" \
  --limit "$LIMIT" \
  --offline \
  --format "$OUTPUT_FORMAT"
