#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
HISTORY_PATH=${HISTORY:-data/crypto_radar.sqlite3}
ASSET_VALUE=${ASSET:-}
RSS_TIMEOUT_VALUE=${RSS_TIMEOUT:-20}
REDDIT_ONLY_VALUE=${RSS_REDDIT_ONLY:-0}
RSS_CONFIG_VALUE=${RSS_CONFIG:-}
RSS_STRICT_VALUE=${RSS_STRICT:-0}

case "$RSS_TIMEOUT_VALUE" in
  ''|*[!0-9.]*|0) printf '%s\n' "RSS_TIMEOUT must be positive" >&2; exit 64 ;;
esac

case "$ASSET_VALUE" in
  ''|BTC|ETH|SOL|HYPE|ZEC) ;;
  *) printf '%s\n' "ASSET must be one of BTC, ETH, SOL, HYPE, ZEC or empty" >&2; exit 64 ;;
esac

case "$REDDIT_ONLY_VALUE" in
  0|1) ;;
  *) printf '%s\n' "RSS_REDDIT_ONLY must be 0 or 1" >&2; exit 64 ;;
esac

case "$RSS_STRICT_VALUE" in
  0|1) ;;
  *) printf '%s\n' "RSS_STRICT must be 0 or 1" >&2; exit 64 ;;
esac

case "$HISTORY_PATH" in
  /*) ;;
  *) HISTORY_PATH="$ROOT_DIR/$HISTORY_PATH" ;;
esac

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
set -- "$ROOT_DIR/.venv/bin/python" -m crypto_radar.cli rss-run \
  --history "$HISTORY_PATH" --rss-timeout "$RSS_TIMEOUT_VALUE"
[ "$REDDIT_ONLY_VALUE" = 1 ] && set -- "$@" --reddit-only
[ -n "$ASSET_VALUE" ] && set -- "$@" --asset "$ASSET_VALUE"
[ -n "$RSS_CONFIG_VALUE" ] && set -- "$@" --rss-config "$RSS_CONFIG_VALUE"
REPORT_PATH=${TMPDIR:-/tmp}/crypto-radar-rss.$$.json
trap 'rm -f "$REPORT_PATH"' EXIT HUP INT TERM
"$@" >"$REPORT_PATH"
cat "$REPORT_PATH"
if [ "$RSS_STRICT_VALUE" = 1 ]; then
  "$ROOT_DIR/.venv/bin/python" -c 'import json,sys; sys.exit(1 if json.load(open(sys.argv[1]))["status"] == "degraded" else 0)' "$REPORT_PATH"
fi
