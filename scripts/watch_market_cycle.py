#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

STALE_AFTER_SECONDS = 15 * 60


def main() -> int:
    path = Path(os.environ.get("HISTORY", "data/crypto_radar.sqlite3"))
    if not path.exists():
        print(json.dumps({"kind": "market_cycle_alert", "reason": "not_started", "history": str(path)}))
        return 0

    with sqlite3.connect(path) as connection:
        try:
            row = connection.execute(
                "SELECT recorded_at FROM alert_events ORDER BY recorded_at DESC LIMIT 1"
            ).fetchone()
        except sqlite3.OperationalError:
            row = None

    if row is None:
        print(json.dumps({"kind": "market_cycle_alert", "reason": "not_started", "history": str(path)}))
        return 0

    age_seconds = max(0, int(time.time() - float(row[0])))
    if age_seconds > STALE_AFTER_SECONDS:
        print(json.dumps({
            "kind": "market_cycle_alert",
            "reason": "stale",
            "age_seconds": age_seconds,
            "history": str(path),
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
