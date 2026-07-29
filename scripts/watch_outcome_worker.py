#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

STALE_AFTER_SECONDS = 15 * 60


def main() -> int:
    path = Path(os.environ.get("HISTORY", "data/crypto_radar.sqlite3"))
    if not path.exists():
        print(json.dumps({"kind": "outcome_worker_alert", "reason": "not_started", "history": str(path)}))
        return 0

    with sqlite3.connect(path) as connection:
        try:
            row = connection.execute(
                "SELECT value FROM outcome_worker_state WHERE key = 'last_run'"
            ).fetchone()
        except sqlite3.OperationalError:
            row = None

    if row is None:
        print(json.dumps({"kind": "outcome_worker_alert", "reason": "not_started", "history": str(path)}))
        return 0

    state = json.loads(row[0])
    age_seconds = max(0, int(time.time() - float(state["completed_at"])))
    reason = "error" if state.get("errors", 0) else "stale" if age_seconds > STALE_AFTER_SECONDS else None
    if reason is not None:
        print(json.dumps({
            "kind": "outcome_worker_alert",
            "reason": reason,
            "age_seconds": age_seconds,
            "errors": state.get("errors", 0),
            "status": state.get("status", "ok"),
            "history": str(path),
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
