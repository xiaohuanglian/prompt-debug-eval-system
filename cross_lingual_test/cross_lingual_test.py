#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-Lingual Quality Test Harness
===================================
测试场景：English Prompt + English Context + target_language="zh" → Chinese Output
基线对比：English Prompt + English Context + target_language="en" → English Output

评估维度：
  1. 语言地道性 (Naturalness) - 是否存在翻译腔、生硬直译
  2. 专业术语处理 (Terminology) - 专业名词在中文语境下是否合理
  3. 语义一致性 (Semantic Consistency) - 中英文版本语义是否一致

Usage:
  python cross_lingual_test.py [--dry-run] [--model kimi]
"""

import os
import sys
import json
import time
import argparse
import concurrent.futures
from datetime import datetime
from typing import Any

# ── Path setup ──────────────────────────────────────────────
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(CURRENT_DIR, "..", "Virtual-Coach-main"))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from code.models.kimi_k2_5 import llm_response
from code.pipeline.json_utils import extract_last_complete_json

# ── Configuration ───────────────────────────────────────────
OUTPUT_DIR = os.path.join(CURRENT_DIR, "results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── English Prompt Template (v1-based, field names unified) ─
ENGLISH_PROMPT_TEMPLATE = """## ROLE
You are {agent_persona}, an exclusive AI Virtual Coach in a fitness training app.
Your tone is analytical, objective, yet deeply empowering and approachable—like a knowledgeable personal trainer speaking face-to-face with a client.

## CONTEXT
The user has just opened the app homepage and needs to quickly establish mental readiness for today's training session.

**Input Data Fields:**
- `training_focus` (string): Today's training focus, e.g., "Knee Protection", "Core Stability", "Lower Body Mobility", etc.
- `exercise_list` (array<string>): List of today's exercises, e.g., ["Wall Sit", "Goblet Squats"].
- `output_language` (string): Target output language, either "中文" (Chinese) or "English".
- `investment_goal` (string, optional): User's ultimate athletic vision, e.g., "Run a 10K with zero discomfort".
- `is_risk_detected` (boolean, optional): Whether a movement risk has been detected.
- `performance_risk_notes` (string, optional): Specific risk description to incorporate as safety reminders.

## TASK
Generate a training day introduction text that establishes psychological readiness. The text must:
1. Clearly state today's training goal (using `training_focus`).
2. Use plain, accessible language to explain how the exercises in `exercise_list` achieve this goal, avoiding technical jargon.
3. End with an encouraging call-to-action that motivates the user to start immediately.

**Structural Requirements:**
- Exactly 3 sentences.
- Sentence 1: State the training focus directly (no generic greetings like "Hello" or "Welcome back").
- Sentence 2: Connect 1-2 key exercises from `exercise_list` to the functional outcome using simple, non-technical language.
- Sentence 3: Provide an energetic, motivating closing that prompts immediate action.

## GENERATION RULES
1. **Language Adaptation**: Generate the text STRICTLY in the language specified by `output_language`.
   - If `output_language` is "中文": Output in natural, conversational Chinese. Use particles like "吧", "呢" naturally. Control total characters to 30-50 Chinese characters (not counting punctuation).
   - If `output_language` is "English": Output in natural English. Control total words to 30-50 words.

2. **Sentence Construction**:
   - First sentence must directly reference `training_focus`.
   - Second sentence should select the most representative 1-2 exercises from `exercise_list` and explain their benefit in layman's terms.
   - Third sentence must be a motivating call-to-action.

3. **Risk Adaptation** (if `is_risk_detected` is true):
   - MUST convert `performance_risk_notes` into a safety reminder (e.g., "move slowly", "keep a chair nearby for support").
   - The safety reminder should be a separate clause, NOT framed as a therapeutic benefit.
   - Maintain a positive yet cautious tone. NEVER use words like "dangerous", "forbidden", or "prohibited".

4. **Tone and Style**:
   - Speak like a real, enthusiastic coach—not an AI assistant.
   - Avoid medical or overly scientific terminology. Translate biomechanical concepts into everyday language.
   - For Chinese output: Use conversational particles naturally; avoid stiff, textbook-style Chinese.
   - For English output: Use contractions and natural speech patterns.

5. **Content Boundaries**:
   - Do not ask questions that require user response.
   - Do not include disclaimers, safety warnings phrased as medical advice, or explanations of the output format.

## RESTRICTIONS
- **Strictly Forbidden**: Generic greetings ("你好", "欢迎回来", "Hello", "Hi there"), Markdown formatting, HTML tags, or code blocks in the output text.
- **Strictly Forbidden**: Outputting field names, JSON structure explanations, or meta-information about the generation process.
- **Strictly Forbidden**: Medical diagnoses or mentions of "injury", "pain", "disease".
- **Strictly Forbidden**: Describing risk notes as therapeutic benefits.
- **Length Constraint**: 30-50 words/characters, exactly 3 sentences. No exceptions.
- **Pure Text Only**: Return only the spoken text.

## OUTPUT REQUIREMENTS
**Output Format**: JSON object with a single field `intro_text`.

| Field Name | Type | Description |
|------------|------|-------------|
| `intro_text` | string | The generated training day introduction. Plain text without Markdown or formatting. |

**Output Example** (Chinese):
{{"intro_text": "今天专注膝关节保护。通过靠墙静蹲和台阶踏步强化关节周围支撑力，减少日常压力。准备好开始今天的训练吧！"}}

**Output Example** (English):
{{"intro_text": "Today we're focusing on knee protection. Through wall sits and step-ups, we'll build strength around your joints to reduce everyday pressure. Let's start training!"}}
"""


def build_prompt(input_data: dict) -> str:
    """Build the full prompt by formatting the template with input data."""
    return ENGLISH_PROMPT_TEMPLATE.format(**input_data)


def call_llm(prompt: str, max_retries: int = 3) -> dict:
    """Call the LLM and extract structured JSON result."""
    start = time.time()
    last_error = None
    raw_response = None

    for attempt in range(max_retries):
        try:
            raw_response = llm_response(prompt)
            if raw_response is None:
                last_error = "LLM returned None"
                time.sleep(2)
                continue

            parsed = extract_last_complete_json(raw_response)
            if parsed is not None and isinstance(parsed, dict) and "intro_text" in parsed:
                return {
                    "success": True,
                    "raw": raw_response,
                    "parsed": parsed,
                    "time_cost": time.time() - start,
                    "attempts": attempt + 1,
                }

            last_error = f"Failed to parse JSON (attempt {attempt + 1})"
            time.sleep(1)

        except Exception as e:
            last_error = str(e)
            time.sleep(2)

    return {
        "success": False,
        "raw": raw_response,
        "parsed": None,
        "time_cost": time.time() - start,
        "error": last_error,
    }


def run_test_batch(test_data: list, label: str) -> list:
    """Run a batch of test cases and collect results."""
    results = []
    total = len(test_data)
    print(f"\n{'=' * 60}")
    print(f"  Running: {label} ({total} test cases)")
    print(f"{'=' * 60}")

    for i, item in enumerate(test_data):
        test_id = item["test_id"]
        scenario = item["scenario"]
        input_data = item["input"]

        # Build prompt
        prompt = build_prompt(input_data)

        # Call LLM
        print(f"\n[{i + 1}/{total}] {test_id} ({scenario})")
        print(f"  Language target: {input_data['output_language']}")
        print(f"  Training focus: {input_data['training_focus']}")
        print(f"  Exercises: {input_data['exercise_list']}")

        llm_result = call_llm(prompt)

        if llm_result["success"]:
            intro = llm_result["parsed"]["intro_text"]
            print(f"  Output: {intro}")
            print(f"  Time: {llm_result['time_cost']:.2f}s (attempts: {llm_result['attempts']})")
        else:
            print(f"  FAILED: {llm_result.get('error', 'Unknown error')}")
            print(f"  Raw (truncated): {str(llm_result.get('raw', ''))[:200]}")

        results.append({
            "test_id": test_id,
            "scenario": scenario,
            "input": input_data,
            "prompt": prompt,
            "success": llm_result["success"],
            "raw_response": llm_result.get("raw"),
            "output": llm_result["parsed"],
            "time_cost": llm_result["time_cost"],
            "error": llm_result.get("error"),
        })

        # Small delay between calls to avoid rate limiting
        if i < total - 1:
            time.sleep(1)

    # Summary
    success_count = sum(1 for r in results if r["success"])
    print(f"\n--- {label} Summary ---")
    print(f"  Success: {success_count}/{total}")
    avg_time = sum(r["time_cost"] for r in results) / total if total else 0
    print(f"  Avg time: {avg_time:.2f}s")

    return results


# ── Quality Evaluation ──────────────────────────────────────

EVALUATION_PROMPT_TEMPLATE = """You are a rigorous bilingual (Chinese/English) LLM output quality evaluator.

Your task: Evaluate the Chinese output quality of a fitness coaching AI that generates training day introductions.

## Context
The AI prompt and all input context fields are in ENGLISH. Only the `output_language` parameter was set to "中文" to request Chinese output. This means the model must perform cross-lingual generation: understanding English context and producing natural Chinese text.

## Input Data (English context)
{input_data}

## Chinese Output (to evaluate)
{chinese_output}

## English Baseline (same context, output_language="English")
{english_output}

## Evaluation Dimensions

Rate each dimension on a 1-5 scale (1=poor, 5=excellent):

### 1. Language Naturalness (语言地道性) [1-5]
- 5: Reads like native Chinese; natural word choices, sentence flow, and rhythm. No trace of "translationese."
- 3: Understandable but somewhat stiff; some phrases feel like literal translations from English.
- 1: Heavy translationese; awkward phrasing throughout; obviously machine-translated.

### 2. Terminology Handling (专业术语处理) [1-5]
- 5: Exercise names and fitness concepts are rendered in the most natural Chinese form. Technical terms are appropriately adapted (e.g., "Dead Bug" → "死虫式" not "死虫子"; "core anti-rotation" → "核心抗旋" not "核心反旋转"). English terms are kept only where natural in Chinese fitness context.
- 3: Terms are translated but some feel unnatural or inconsistent. Some terms would be better left in English or rendered differently.
- 1: Poor terminology choices; concepts are confusing in Chinese; English terms inappropriately dropped or kept.

### 3. Semantic Consistency (语义一致性) [1-5]
- 5: All key information from the English baseline is preserved. Training focus, exercise connection, safety reminders (if any), and motivational tone are faithfully conveyed.
- 3: Most information is preserved but there are minor omissions, additions, or shifts in emphasis.
- 1: Significant information loss, fabrication, or distortion compared to the English baseline.

### 4. Overall Cross-lingual Quality [1-5]
Overall assessment of how well the Chinese output serves its purpose compared to the English baseline.

## Output Format
Return a JSON object:
```json
{{
  "naturalness": <1-5>,
  "terminology": <1-5>,
  "semantic_consistency": <1-5>,
  "overall": <1-5>,
  "issues": ["<specific issue 1>", "<specific issue 2>", "..."],
  "strengths": ["<specific strength 1>", "..."],
  "summary_cn": "<2-3 sentence summary in Chinese evaluating the output quality>"
}}
```
"""


def evaluate_with_llm(zh_result: dict, en_result: dict) -> dict:
    """Use LLM-as-Judge to evaluate Chinese output quality against English baseline."""
    if not zh_result.get("success"):
        return {
            "naturalness": 1,
            "terminology": 1,
            "semantic_consistency": 1,
            "overall": 1,
            "issues": ["Chinese generation failed"],
            "strengths": [],
            "summary_cn": "中文生成失败，无法评估。",
            "error": zh_result.get("error"),
        }

    input_data = zh_result["input"]
    chinese_output = zh_result["output"]["intro_text"]
    english_output = en_result["output"]["intro_text"] if en_result.get("success") else "[English generation failed]"

    eval_prompt = EVALUATION_PROMPT_TEMPLATE.format(
        input_data=json.dumps(input_data, ensure_ascii=False, indent=2),
        chinese_output=chinese_output,
        english_output=english_output,
    )

    try:
        raw = llm_response(eval_prompt)
        parsed = extract_last_complete_json(raw)
        if parsed and isinstance(parsed, dict):
            return parsed
    except Exception as e:
        pass

    # Fallback: manual scoring cues
    return {
        "naturalness": 3,
        "terminology": 3,
        "semantic_consistency": 3,
        "overall": 3,
        "issues": ["LLM evaluation failed — using default scores"],
        "strengths": [],
        "summary_cn": "评估异常，采用默认评分。",
        "raw_eval": raw if 'raw' in dir() else None,
    }


# ── Main Test Flow ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Cross-lingual Chinese output quality test")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without calling LLM")
    parser.add_argument("--single", type=int, default=None, help="Run only test case N (0-indexed)")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Load test data
    en2zh_path = os.path.join(CURRENT_DIR, "test_data_en2zh.json")
    en2en_path = os.path.join(CURRENT_DIR, "test_data_en2en.json")

    with open(en2zh_path, "r", encoding="utf-8") as f:
        en2zh_data = json.load(f)
    with open(en2en_path, "r", encoding="utf-8") as f:
        en2en_data = json.load(f)

    if args.single is not None:
        en2zh_data = [en2zh_data[args.single]]
        en2en_data = [en2en_data[args.single]]

    if args.dry_run:
        print("=" * 60)
        print("  DRY RUN — Printing prompts without LLM calls")
        print("=" * 60)
        for item in en2zh_data:
            prompt = build_prompt(item["input"])
            print(f"\n--- {item['test_id']} ({item['scenario']}) ---")
            print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
            print("..." * 40)
        return

    # Phase 1: Generate Chinese outputs (English context → Chinese)
    print("\n" + "█" * 60)
    print("  PHASE 1: English Context → Chinese Output (THE TEST)")
    print("█" * 60)
    zh_results = run_test_batch(en2zh_data, "EN → ZH")

    # Phase 2: Generate English baselines (English context → English)
    print("\n" + "█" * 60)
    print("  PHASE 2: English Context → English Output (BASELINE)")
    print("█" * 60)
    en_results = run_test_batch(en2en_data, "EN → EN")

    # Phase 3: Evaluate Chinese quality
    print("\n" + "█" * 60)
    print("  PHASE 3: Quality Evaluation (LLM-as-Judge)")
    print("█" * 60)

    evaluations = []
    for i, (zh, en) in enumerate(zip(zh_results, en_results)):
        print(f"\n[{i + 1}/{len(zh_results)}] Evaluating {zh['test_id']}...")
        eval_result = evaluate_with_llm(zh, en)
        eval_result["test_id"] = zh["test_id"]
        eval_result["scenario"] = zh["scenario"]
        evaluations.append(eval_result)

        print(f"  Naturalness: {eval_result.get('naturalness', '?')}/5")
        print(f"  Terminology: {eval_result.get('terminology', '?')}/5")
        print(f"  Semantic Consistency: {eval_result.get('semantic_consistency', '?')}/5")
        print(f"  Overall: {eval_result.get('overall', '?')}/5")

    # Phase 4: Compile report
    print("\n" + "█" * 60)
    print("  PHASE 4: Final Report")
    print("█" * 60)

    zh_success = sum(1 for r in zh_results if r["success"])
    en_success = sum(1 for r in en_results if r["success"])

    avg_nat = sum(e.get("naturalness", 0) for e in evaluations) / len(evaluations)
    avg_term = sum(e.get("terminology", 0) for e in evaluations) / len(evaluations)
    avg_sem = sum(e.get("semantic_consistency", 0) for e in evaluations) / len(evaluations)
    avg_overall = sum(e.get("overall", 0) for e in evaluations) / len(evaluations)

    report = {
        "test_metadata": {
            "timestamp": timestamp,
            "model": "kimi-k2.5",
            "prompt_language": "English",
            "context_language": "English (field names + values)",
            "target_language": "Chinese (中文)",
            "total_test_cases": len(en2zh_data),
        },
        "generation_results": {
            "zh_success_rate": f"{zh_success}/{len(zh_results)}",
            "en_success_rate": f"{en_success}/{len(en_results)}",
        },
        "quality_scores": {
            "avg_naturalness": round(avg_nat, 2),
            "avg_terminology": round(avg_term, 2),
            "avg_semantic_consistency": round(avg_sem, 2),
            "avg_overall": round(avg_overall, 2),
        },
        "per_case": [],
    }

    for zh, en, ev in zip(zh_results, en_results, evaluations):
        case = {
            "test_id": zh["test_id"],
            "scenario": zh["scenario"],
            "input_training_focus": zh["input"]["training_focus"],
            "input_exercises": zh["input"]["exercise_list"],
            "zh_output": zh["output"]["intro_text"] if zh.get("output") else None,
            "en_output": en["output"]["intro_text"] if en.get("output") else None,
            "zh_success": zh["success"],
            "en_success": en["success"],
            "evaluation": {
                "naturalness": ev.get("naturalness"),
                "terminology": ev.get("terminology"),
                "semantic_consistency": ev.get("semantic_consistency"),
                "overall": ev.get("overall"),
                "issues": ev.get("issues", []),
                "strengths": ev.get("strengths", []),
                "summary_cn": ev.get("summary_cn", ""),
            },
        }
        report["per_case"].append(case)

    # Save report
    report_path = os.path.join(OUTPUT_DIR, f"cross_lingual_quality_report_{timestamp}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Save raw results separately
    raw_path = os.path.join(OUTPUT_DIR, f"raw_results_{timestamp}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({
            "zh_results": zh_results,
            "en_results": en_results,
            "evaluations": evaluations,
        }, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nReport saved: {report_path}")
    print(f"Raw results saved: {raw_path}")

    # Print final summary
    print(f"\n{'=' * 60}")
    print(f"  CROSS-LINGUAL QUALITY EVALUATION SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Model: kimi-k2.5")
    print(f"  Test cases: {len(en2zh_data)}")
    print(f"  ZH generation success: {zh_success}/{len(zh_results)}")
    print(f"  EN generation success: {en_success}/{len(en_results)}")
    print(f"  ---")
    print(f"  Avg Naturalness (地道性):        {avg_nat:.1f}/5")
    print(f"  Avg Terminology (术语处理):      {avg_term:.1f}/5")
    print(f"  Avg Semantic Consistency (语义):  {avg_sem:.1f}/5")
    print(f"  Avg Overall (综合):               {avg_overall:.1f}/5")
    print(f"{'=' * 60}")

    # Print per-case details
    print(f"\n{'=' * 60}")
    print(f"  PER-CASE COMPARISON")
    print(f"{'=' * 60}")
    for case in report["per_case"]:
        print(f"\n--- {case['test_id']} ({case['scenario']}) ---")
        print(f"  Focus: {case['input_training_focus']}")
        print(f"  ZH: {case['zh_output']}")
        print(f"  EN: {case['en_output']}")
        ev = case["evaluation"]
        print(f"  Scores: N={ev['naturalness']} T={ev['terminology']} S={ev['semantic_consistency']} O={ev['overall']}")
        if ev["issues"]:
            print(f"  Issues: {'; '.join(ev['issues'])}")
        if ev["strengths"]:
            print(f"  Strengths: {'; '.join(ev['strengths'])}")


if __name__ == "__main__":
    main()
