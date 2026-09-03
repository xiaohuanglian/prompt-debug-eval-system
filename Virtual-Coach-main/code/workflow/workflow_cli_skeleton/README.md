# workflow_synth (CLI skeleton)

A runnable Python CLI skeleton for **RAG-guided workflow JSON synthesis** with:
- Pydantic schemas for workflow/node JSON
- Extensible validation rules (schema + structural rules)
- Decision trace format (auditable planning trace)
- JSONL event logging
- Planner prompt template (LLM plug-in point)
- Naive retriever (keyword overlap) as a placeholder for vector RAG

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Validate an existing workflow JSON
PYTHONPATH=src python -m workflow_synth.cli validate --workflow examples/wf_setup_s03_inter.json

# Run a stub synthesis (DummyPlanner) - outputs a minimal verified workflow
PYTHONPATH=src python -m workflow_synth.cli synth   --requirement "给我一个最简单的测试工作流：接收消息后直接结束"   --out out.json   --log out.jsonl
```

## Plug in your own docs (RAG)

```bash
PYTHONPATH=src python -m workflow_synth.cli synth   --requirement "我想要一个连续计数100次的俯卧撑训练服务"   --define-dir /path/to/define   --out out.json   --log out.jsonl
```

## Where to plug in your LLM
See `src/workflow_synth/planner.py` (`LLMPlanner` stub) and `templates/planner_prompt.md`.
