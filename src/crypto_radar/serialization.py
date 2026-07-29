from __future__ import annotations

import json
from dataclasses import asdict

from .models import Signal


def signal_to_dict(signal: Signal) -> dict:
    payload = asdict(signal)
    payload["signal_id"] = signal.signal_id
    payload["signal_class"] = signal.signal_class
    payload["evidence_metadata"] = signal.evidence_metadata
    return payload


def signals_to_json(signals: list[Signal]) -> str:
    return json.dumps([signal_to_dict(signal) for signal in signals], ensure_ascii=False, indent=2)
