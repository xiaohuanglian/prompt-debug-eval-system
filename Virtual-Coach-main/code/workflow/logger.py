from __future__ import annotations

import json
import time
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
import os

@dataclass
class Event:
    run_id: str
    ts: str  # now as ISO datetime string
    type: str
    payload: Dict[str, Any]

class JsonLogger:
    def __init__(self, path: Optional[str], run_id: str):
        self.path = path
        self._fp = open(path, "a", encoding="utf-8") if path else None
        self.run_id = run_id
        
        # Prepare jsonl path
        if path:
            root, ext = os.path.splitext(path)
            self._jsonl_path = f"{root}.jsonl"
            self._jsonl_fp = open(self._jsonl_path, "a", encoding="utf-8")
        else:
            self._jsonl_path = None
            self._jsonl_fp = None

    def log(self, event_type: str, payload: Dict[str, Any]) -> None:
        now = datetime.fromtimestamp(time.time()).isoformat(sep=" ", timespec="seconds")
        evt = Event(run_id=self.run_id, ts=now, type=event_type, payload=payload)
        line = json.dumps(asdict(evt), ensure_ascii=False, indent=2)
        line_jsonl = json.dumps(asdict(evt), ensure_ascii=False)
        if self._fp:
            self._fp.write(line + "\n")
            self._fp.flush()
        if self._jsonl_fp:
            self._jsonl_fp.write(line_jsonl + "\n")
            self._jsonl_fp.flush()
        return line

    def error(self, event_type: str, payload: Dict[str, Any]) -> None:
        print(self.log(event_type, payload))

    def close(self) -> None:
        if self._fp:
            self._fp.close()
            self._fp = None
        if self._jsonl_fp:
            self._jsonl_fp.close()
            self._jsonl_fp = None
