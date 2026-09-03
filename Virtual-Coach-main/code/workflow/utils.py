import json
from typing import Dict, Any
import re

def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_json(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=4)

def _parse_llm_json(text: str) -> Dict[str, Any]:
    """Best-effort parse of a JSON object returned by an LLM.

    Handles:
      - raw JSON
      - ```json ... ``` fenced blocks
      - extra prose before/after JSON
    """
    if not text:
        raise ValueError("Empty LLM response")

    s = text.strip()

    # 1) fenced block
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", s, flags=re.IGNORECASE)
    if m:
        s = m.group(1).strip()

    # 2) try direct json
    try:
        return json.loads(s)
    except Exception:
        pass

    # 3) fallback: find first '{' and last '}'
    i = s.find("{")
    j = s.rfind("}")
    if i != -1 and j != -1 and j > i:
        candidate = s[i : j + 1]
        return json.loads(candidate)

    raise ValueError("Failed to parse JSON from LLM response")