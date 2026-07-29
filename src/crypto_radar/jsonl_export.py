from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import Signal
from .serialization import signal_to_dict


def write_jsonl(path: str | Path, signals: list[Signal]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent, prefix=f".{destination.name}.", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        for signal in signals:
            temporary.write(json.dumps(signal_to_dict(signal), ensure_ascii=False, separators=(",", ":")))
            temporary.write("\n")
    os.replace(temporary_path, destination)
