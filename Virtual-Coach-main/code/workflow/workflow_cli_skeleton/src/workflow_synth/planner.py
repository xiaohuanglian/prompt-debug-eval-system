from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from .decision_trace import TraceStep
from .llm_api import llm_chat

@dataclass
class PlanResult:
    workflow_draft: Dict[str, Any]
    confidence: float
    need_more_knowledge: bool
    knowledge_queries: List[Dict[str, Any]]
    decision_trace_step: TraceStep
    assumptions: List[str]

class BasePlanner:
    def plan(self, requirement: str, retrieved_docs: List[Dict[str, Any]], iteration: int) -> PlanResult:
        raise NotImplementedError

class DummyPlanner(BasePlanner):
    """Always returns a minimal workflow: receive_message -> finish."""
    def plan(self, requirement: str, retrieved_docs: List[Dict[str, Any]], iteration: int) -> PlanResult:
        wf_name = "generated_workflow"
        draft = {
            wf_name: {
                "start_node": "receive_00",
                "listen_at_start": True,
                "input_parameters": {},
                "nodes": [
                    {
                        "id": 0,
                        "node_type": "receive_message",
                        "node_name": "receive_00",
                        "key_node": True,
                        "msg_queue": True,
                        "input_map": {},
                        "choice_map": {"default": "finish"},
                        "attrs": {},
                    }
                ],
            }
        }
        step = TraceStep(
            iteration=iteration,
            summary="使用 DummyPlanner 生成最小可运行工作流：接收消息后结束。",
            retrieved=retrieved_docs,
            selected_nodes=[{"node_name": "receive_00", "node_type": "receive_message", "reason": "最小闭环骨架"}],
            validation={},
            next_queries=[],
        )
        return PlanResult(
            workflow_draft=draft,
            confidence=0.6,
            need_more_knowledge=False,
            knowledge_queries=[],
            decision_trace_step=step,
            assumptions=["未启用业务模板，仅生成最小结构以通过形式化验证。"],
        )

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

class LLMPlanner(BasePlanner):
    """LLM planner backed by a real model call (see llm_api.py).

    Expected LLM output (strict JSON):
      {
        "workflow_draft": {...},
        "confidence": 0~1,
        "need_more_knowledge": true/false,
        "knowledge_queries": [{"query": "...", "reason": "..."}],
        "decision_trace": {...},
        "assumptions": [...]
      }
    """

    def __init__(self, prompt_template_path: str):
        self.prompt_template_path = prompt_template_path

    def plan(self, requirement: str, retrieved_docs: List[Dict[str, Any]], iteration: int) -> PlanResult:
        template = open(self.prompt_template_path, "r", encoding="utf-8").read()

        docs_text = "\n\n".join(
            [
                f"[{d.get('doc_id','')}] {d.get('title','')}\n{d.get('snippet','')}"
                for d in (retrieved_docs or [])
            ]
        )

        prompt = template.format(requirement=requirement, docs=docs_text)

        try:
            raw = llm_chat(prompt)
            result = _parse_llm_json(raw)

            workflow_draft = result["workflow_draft"]
            confidence = float(result.get("confidence", 0.5))
            need_more_knowledge = bool(result.get("need_more_knowledge", False))
            knowledge_queries = result.get("knowledge_queries", []) or []
            assumptions = result.get("assumptions", []) or []

            # decision trace -> TraceStep
            dt = result.get("decision_trace", {}) or {}
            summary = (
                dt.get("summary")
                or dt.get("final_summary")
                or "LLMPlanner 生成候选工作流。"
            )
            selected_nodes = dt.get("selected_nodes", [])
            if not isinstance(selected_nodes, list):
                selected_nodes = []

            step = TraceStep(
                iteration=iteration,
                summary=summary,
                retrieved=retrieved_docs,
                selected_nodes=selected_nodes,
                validation={},
                next_queries=knowledge_queries,
            )

            return PlanResult(
                workflow_draft=workflow_draft,
                confidence=confidence,
                need_more_knowledge=need_more_knowledge,
                knowledge_queries=knowledge_queries,
                decision_trace_step=step,
                assumptions=assumptions,
            )

        except Exception as e:
            # Fail-safe fallback to keep the system runnable
            fallback = DummyPlanner().plan(requirement, retrieved_docs, iteration)
            fallback.assumptions = list(fallback.assumptions) + [
                f"LLMPlanner 失败，已回退 DummyPlanner。原因: {repr(e)}"
            ]
            return fallback
