from __future__ import annotations

import json
import time
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

@dataclass
class Event:
    ts: str  # now as ISO datetime string
    run_id: str
    type: str
    payload: Dict[str, Any]

class JsonlLogger:
    def __init__(self, path: Optional[str]):
        self.path = path
        self._fp = open(path, "a", encoding="utf-8") if path else None

    def log(self, run_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        now = datetime.fromtimestamp(time.time()).isoformat(sep=" ", timespec="seconds")
        evt = Event(ts=now, run_id=run_id, type=event_type, payload=payload)
        line = json.dumps(asdict(evt), ensure_ascii=False)
        if self._fp:
            self._fp.write(line + "\n")
            self._fp.flush()

    def close(self) -> None:
        if self._fp:
            self._fp.close()
            self._fp = None
