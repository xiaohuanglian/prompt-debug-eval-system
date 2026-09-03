from __future__ import annotations

import argparse
import json
import os
import uuid
from typing import Any, Dict, List, Optional

from .logger import JsonlLogger
from .retriever import NaiveKeywordRetriever
from .planner import DummyPlanner, LLMPlanner
from .validate import validate_workflow_file

def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_json(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def cmd_validate(args: argparse.Namespace) -> int:
    obj = _read_json(args.workflow)
    _, issues = validate_workflow_file(obj)
    errors = [x for x in issues if x.level == "error"]
    warns = [x for x in issues if x.level == "warn"]

    print(f"[validate] errors={len(errors)} warns={len(warns)}")
    for it in issues:
        print(f" - [{it.level}] {it.code} @ {it.json_path}: {it.message}")
    return 0 if not errors else 2

def cmd_synth(args: argparse.Namespace) -> int:
    run_id = args.run_id or str(uuid.uuid4())
    logger = JsonlLogger(args.log)
    logger.log(run_id, "RUN_START", {"requirement": args.requirement, "define_dir": args.define_dir})

    retriever = NaiveKeywordRetriever(args.define_dir) if args.define_dir else NaiveKeywordRetriever(None)
    planner = DummyPlanner() if args.planner == "dummy" else LLMPlanner(args.prompt_template)

    best_obj: Dict[str, Any] = {}
    for it in range(args.max_iter):
        context_docs: List[Dict[str, Any]] = []
        if args.define_dir:
            hits = retriever.retrieve(args.requirement, top_k=args.top_k)
            context_docs = [{
                "doc_id": ch.doc_id,
                "path": ch.path,
                "title": ch.title,
                "score": float(score),
                "snippet": (ch.content[:400] + ("..." if len(ch.content) > 400 else "")),
            } for ch, score in hits]
        logger.log(run_id, "RETRIEVE", {"iteration": it, "hits": context_docs})

        plan = planner.plan(args.requirement, context_docs, it)
        obj = plan.workflow_draft
        logger.log(run_id, "PLAN", {"iteration": it, "confidence": plan.confidence, "need_more_knowledge": plan.need_more_knowledge})

        _, issues = validate_workflow_file(obj)
        errors = [x for x in issues if x.level == "error"]
        warns = [x for x in issues if x.level == "warn"]
        logger.log(run_id, "VALIDATE", {
            "iteration": it,
            "ok": len(errors) == 0,
            "errors": [x.__dict__ for x in errors],
            "warns": [x.__dict__ for x in warns],
        })

        best_obj = obj
        print(f"[iter {it}] confidence={plan.confidence:.2f} ok={len(errors)==0} errors={len(errors)} warns={len(warns)}")

        if len(errors) == 0:
            _write_json(args.out, obj)
            logger.log(run_id, "FINALIZE", {"out": args.out})
            logger.close()
            print(f"[done] saved to: {args.out}")
            return 0

    _write_json(args.out, best_obj)
    logger.log(run_id, "RUN_END", {"stop_reason": "max_iter", "out": args.out})
    logger.close()
    print(f"[stop] max_iter reached, best-effort saved to: {args.out}")
    return 3

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="workflow_synth", description="RAG-guided workflow JSON synthesis (skeleton).")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="Validate an existing workflow json")
    p_val.add_argument("--workflow", required=True)
    p_val.set_defaults(func=cmd_validate)

    p_syn = sub.add_parser("synth", help="Synthesize a workflow json from natural language requirement")
    p_syn.add_argument("--requirement", required=True)
    p_syn.add_argument("--define-dir", default=None, help="Path to your define/ folder (md docs).")
    p_syn.add_argument("--out", required=True, help="Output workflow json path.")
    p_syn.add_argument("--log", default=None, help="JSONL log path.")
    p_syn.add_argument("--max-iter", type=int, default=3)
    p_syn.add_argument("--top-k", type=int, default=6)
    p_syn.add_argument("--planner", choices=["dummy", "llm"], default="dummy")
    p_syn.add_argument("--prompt-template", default=os.path.join(os.path.dirname(__file__), "..", "..", "templates", "planner_prompt.md"))
    p_syn.add_argument("--run-id", default=None)
    p_syn.set_defaults(func=cmd_synth)

    return p

def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
