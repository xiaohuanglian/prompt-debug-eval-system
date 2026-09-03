import json
import re
import time
import concurrent.futures

from .json_utils import extract_last_complete_json
from .llm_judge import DEFAULT_THRESHOLD, judge_sample
from .prompt_generator import extract_placeholders, render_prompt_template


# 字段名 token 命中以下集合时视为「自由长文本」，不参与精确比对（默认跳过）。
# 必须按 token 精确匹配，避免 "adjustment_noted" 这种含 "note" 子串的字段被误跳。
LONG_TEXT_KEY_KEYWORDS = frozenset({
    # 英文（含常见单复数）
    "reason", "reasons",
    "rationale", "rationales",
    "summary", "summaries",
    "narrative", "narratives",
    "explanation", "explanations", "explain",
    "description", "descriptions",
    "comment", "comments",
    "feedback",
    "review", "reviews",
    "analysis", "analyses",
    "insight", "insights",
    "message", "messages",
    "content", "contents",
    "text", "texts",
    "note", "notes",
    "remark", "remarks",
    # 中文（少量高命中场景）
    "理由", "原因", "说明", "描述", "总结", "评价", "建议",
})

# 这些字段通常承载模型生成的自然语言话术/文案。它们仍需被评估，
# 但不应像枚举、布尔、数字那样用逐字相等来判定。
SEMANTIC_TEXT_KEY_KEYWORDS = LONG_TEXT_KEY_KEYWORDS | frozenset({
    "prompt", "prompts",
    "utterance", "utterances",
    "sentence", "sentences",
    "phrase", "phrases",
    "copy",
    "script", "scripts",
    "speech",
    "dialogue", "dialog",
    "caption", "captions",
    "title", "subtitle",
    "话术", "文案", "提示", "提示语", "引导语", "开场白", "结束语",
})

EXACT_TEXT_KEY_KEYWORDS = frozenset({
    "id", "ids",
    "code", "codes",
    "version",
    "type", "types",
    "category", "categories",
    "class", "classes",
    "classification",
    "label", "labels",
    "name", "names",
    "status", "state",
    "mode",
    "language", "locale",
})

# 字符串字段的「自由长文本」长度阈值——
# 即使字段名不命中 keyword，过长字符串仍按宽松比对处理。
LONG_TEXT_LEN_THRESHOLD = 80

# 拆分 snake_case / kebab-case / camelCase / 空格 的正则
_TOKEN_SPLIT_RE = re.compile(
    r'[_\s\-]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])'
)


def _tokenize_key(key: str) -> list:
    """把字段名拆成小写 token 列表，便于按词精确匹配。"""
    return [t.lower() for t in _TOKEN_SPLIT_RE.split(key) if t]


def _is_long_text_key(key: str) -> bool:
    return any(t in LONG_TEXT_KEY_KEYWORDS for t in _tokenize_key(key))


def _is_semantic_text_key(key: str) -> bool:
    tokens = _tokenize_key(key or "")
    if any(t in EXACT_TEXT_KEY_KEYWORDS for t in tokens):
        return False
    return any(t in SEMANTIC_TEXT_KEY_KEYWORDS for t in tokens)


def _should_defer_semantic_text(key: str, value) -> bool:
    """
    判断字段是否属于自然语言生成文本。

    这类字段不跳过评测，而是从“硬结构逐字比对”中剥离出来：
    - 结构层只确认字段存在、类型正确、数组长度/对象层级正确；
    - 文本内容差异交给 LLM judge 做语义复判。
    """
    if not isinstance(value, str):
        return False
    if _is_semantic_text_key(key):
        return True
    if len(value) >= LONG_TEXT_LEN_THRESHOLD:
        return True
    return False


def _should_skip_field(key: str, value) -> bool:
    """
    兼容旧调用名：历史上这里表示“跳过精确比对”。
    新逻辑不再真正跳过，而是把自然语言文本交给语义层评估。
    """
    return _should_defer_semantic_text(key, value)


def _values_match(predicted, expected) -> bool:
    """类型感知的比对器，仅用于结构化字段（短字符串 / bool / 数字 / null / 嵌套 dict / list）。"""
    if expected is None:
        return predicted is None
    if isinstance(expected, bool):
        return isinstance(predicted, bool) and predicted == expected
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return isinstance(predicted, (int, float)) and predicted == expected
    if isinstance(expected, str):
        if not isinstance(predicted, str):
            return False
        return predicted.strip() == expected.strip()
    if isinstance(expected, dict):
        if not isinstance(predicted, dict):
            return False
        for k, v in expected.items():
            if k not in predicted:
                return False
            if not _values_match(predicted[k], v):
                return False
        return True
    if isinstance(expected, list):
        if not isinstance(predicted, list) or len(predicted) != len(expected):
            return False
        return all(_values_match(p, e) for p, e in zip(predicted, expected))
    return predicted == expected


def _path_child(path: str, key: str) -> str:
    return f"{path}.{key}" if path else str(key)


def _path_index(path: str, index: int) -> str:
    return f"{path}[{index}]" if path else f"[{index}]"


def _merge_compare(dst: dict, src: dict):
    dst["hard_diffs"].extend(src["hard_diffs"])
    dst["semantic_diffs"].extend(src["semantic_diffs"])
    dst["hard_compared_count"] += src["hard_compared_count"]
    dst["semantic_compared_count"] += src["semantic_compared_count"]


def _compare_values(predicted, expected, path: str = "", key: str = "") -> dict:
    """
    递归比较 expected 与 predicted。

    hard_diffs: 字段缺失、类型错误、数组长度、枚举/数字/布尔等硬结构错误。
    semantic_diffs: 自然语言文本字段的非逐字差异，需要 LLM judge 复判。
    """
    result = {
        "hard_diffs": [],
        "semantic_diffs": [],
        "hard_compared_count": 0,
        "semantic_compared_count": 0,
    }
    label = path or key or "$"

    if expected is None:
        result["hard_compared_count"] += 1
        if predicted is not None:
            result["hard_diffs"].append(f"{label}: 期望=None, 预测={predicted!r}")
        return result

    if isinstance(expected, bool):
        result["hard_compared_count"] += 1
        if not isinstance(predicted, bool) or predicted != expected:
            result["hard_diffs"].append(f"{label}: 期望={expected!r}, 预测={predicted!r}")
        return result

    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        result["hard_compared_count"] += 1
        if not isinstance(predicted, (int, float)) or isinstance(predicted, bool) or predicted != expected:
            result["hard_diffs"].append(f"{label}: 期望={expected!r}, 预测={predicted!r}")
        return result

    if isinstance(expected, str):
        if _should_defer_semantic_text(key, expected):
            result["semantic_compared_count"] += 1
            if not isinstance(predicted, str):
                result["hard_diffs"].append(
                    f"{label}: 期望为文本字段, 预测类型={type(predicted).__name__}"
                )
            elif predicted.strip() != expected.strip():
                result["semantic_diffs"].append(
                    f"{label}: 期望语义={expected!r}, 预测={predicted!r}"
                )
            return result

        result["hard_compared_count"] += 1
        if not isinstance(predicted, str) or predicted.strip() != expected.strip():
            result["hard_diffs"].append(f"{label}: 期望={expected!r}, 预测={predicted!r}")
        return result

    if isinstance(expected, dict):
        if not isinstance(predicted, dict):
            result["hard_diffs"].append(f"{label}: 期望为对象, 预测={predicted!r}")
            return result
        for k, v in expected.items():
            child_path = _path_child(path, k)
            if k not in predicted:
                result["hard_diffs"].append(f"{child_path}: 缺失（期望={v!r}）")
                continue
            child = _compare_values(predicted[k], v, child_path, k)
            _merge_compare(result, child)
        return result

    if isinstance(expected, list):
        if not isinstance(predicted, list):
            result["hard_diffs"].append(f"{label}: 期望为数组, 预测={predicted!r}")
            return result
        if len(predicted) != len(expected):
            result["hard_diffs"].append(
                f"{label}: 数组长度不一致（期望={len(expected)}, 预测={len(predicted)}）"
            )
            return result
        for idx, (p, e) in enumerate(zip(predicted, expected)):
            child = _compare_values(p, e, _path_index(path, idx), key)
            _merge_compare(result, child)
        return result

    result["hard_compared_count"] += 1
    if predicted != expected:
        result["hard_diffs"].append(f"{label}: 期望={expected!r}, 预测={predicted!r}")
    return result


def structural_compare(predicted, ground_truth) -> dict:
    """
    新版结构比对，返回:
        {
            "pass": bool,                # 是否逐字/结构都通过（无需 judge）
            "hard_pass": bool,           # 硬结构/枚举/数值是否通过
            "semantic_needed": bool,     # 是否存在自然语言字段的非逐字差异
            "all_skipped": bool,         # 兼容旧字段：只有语义文本、无硬结构字段
            "diffs": list[str],
            "hard_diffs": list[str],
            "semantic_diffs": list[str],
            "compared_count": int,       # 硬字段数量
            "semantic_compared_count": int,
            "skipped_count": int,        # 兼容旧字段：语义文本字段数量
        }

    关键点：
    - 分类、枚举、布尔、数字、数组长度、字段层级仍然严格比对；
    - prompt_start / feedback / summary 等自然语言字段不做逐字硬判，
      差异会进入 semantic_diffs，交由 LLM judge 复判；
    - 不再出现“长文本字段全部跳过后默认通过”的 100% 假阳性。
    """
    cmp_result = _compare_values(predicted, ground_truth)
    hard_diffs = cmp_result["hard_diffs"]
    semantic_diffs = cmp_result["semantic_diffs"]
    hard_compared = cmp_result["hard_compared_count"]
    semantic_compared = cmp_result["semantic_compared_count"]

    hard_pass = len(hard_diffs) == 0
    semantic_needed = len(semantic_diffs) > 0
    exact_pass = hard_pass and not semantic_needed
    all_skipped = (hard_compared == 0 and semantic_compared > 0)
    return {
        "pass": exact_pass,
        "hard_pass": hard_pass,
        "semantic_needed": semantic_needed,
        "all_skipped": all_skipped,
        "diffs": hard_diffs + semantic_diffs,
        "hard_diffs": hard_diffs,
        "semantic_diffs": semantic_diffs,
        "compared_count": hard_compared,
        "semantic_compared_count": semantic_compared,
        "skipped_count": semantic_compared,
    }


def compare_output(predicted: dict, ground_truth: dict) -> bool:
    """
    薄包装，保留向后兼容；行为已变更：all_skipped 时返回 False。
    新代码请直接用 structural_compare 拿到详细结构。
    """
    return structural_compare(predicted, ground_truth)["pass"]


def diff_output(predicted: dict, ground_truth: dict) -> list:
    """构造可读的字段差异列表（基于 structural_compare）。"""
    return structural_compare(predicted, ground_truth)["diffs"]


def coerce_single_text_response(response: str, ground_truth):
    """
    单文本输出场景的容错解析。

    有些生产 prompt 只要求输出一段自然语言文本，但评测数据为了统一保存成
    {"intro_text": "..."}。当模型返回纯文本且 ground_truth 恰好只有一个字符串字段时，
    将其临时包装成同名字段，避免把“有文本响应”误记为“无法获取有效响应”。
    """
    if not isinstance(response, str) or not response.strip():
        return None
    if not isinstance(ground_truth, dict) or len(ground_truth) != 1:
        return None
    key, expected = next(iter(ground_truth.items()))
    if not isinstance(expected, str):
        return None
    text = response.strip()
    if text.startswith("{") or text.startswith("["):
        return None
    return {key: text}


def run_evaluation(target_llm: callable, prompt_template: str,
                   eval_data: list, scenario_name: str, version: int,
                   result_path: str = None, max_workers: int = 8,
                   helper_llm: callable = None,
                   use_llm_judge: bool = False,
                   judge_threshold: int = DEFAULT_THRESHOLD,
                   template_mode: str = "structural",
                   progress_callback: callable = None,
                   stop_flag: callable = None) -> dict:
    """
    运行评测（结构 + LLM judge 双层）。

    参数:
        target_llm: 目标模型调用函数 (prompt: str) -> str
        prompt_template: prompt 模板
        eval_data: 评测数据集
        scenario_name: 场景名称
        version: prompt 版本号
        result_path: 结果保存路径（可选）
        max_workers: 评测并发数
        helper_llm: 用于 LLM-as-Judge 的 helper 模型；None 时跳过 judge
        use_llm_judge: True 时所有样本都跑 judge；False 时仅在结构 all_skipped 时跑
        judge_threshold: judge 综合分 >= 该值视为通过
        template_mode: "structural" / "strict"，仅用于结果元信息
        progress_callback: 可选回调 progress_callback(completed, total)，每完成一个样本调用一次
        stop_flag: 可选回调 stop_flag() -> bool，返回 True 时停止等待剩余结果

    返回:
        dict 包含 accuracy/structural_accuracy/semantic_accuracy/overall_accuracy 等
    """
    total = len(eval_data)
    placeholders = extract_placeholders(prompt_template)
    judge_enabled = helper_llm is not None

    def process_sample(i):
        sample = eval_data[i]
        result = {"input": sample["input"]}

        # 格式化 prompt
        try:
            formatted_prompt = render_prompt_template(prompt_template, sample["input"])
        except KeyError as e:
            print(f"样本 {i} 格式化失败，缺少占位符: {e}")
            result["is_correct"] = False
            result["final_pass"] = False
            result["structural_pass"] = False
            result["error_reason"] = f"格式化失败: {e}"
            result["time_cost"] = 0
            return result

        result["prompt"] = formatted_prompt

        response_json = None
        successful_times = None
        start_time = time.time()
        target_attempts = 0

        # 最多尝试3次
        for times in range(3):
            try:
                target_attempts += 1
                response = target_llm(formatted_prompt)
                result[f"response_{times}"] = response

                if response is None:
                    result[f"response_json_{times}"] = None
                    continue

                response_json = extract_last_complete_json(response)
                if response_json is None:
                    response_json = coerce_single_text_response(
                        response, sample.get("output")
                    )
                    if response_json is not None:
                        result[f"response_json_{times}_coerced"] = True
                result[f"response_json_{times}"] = response_json

                if response_json is not None:
                    successful_times = times
                    break
            except Exception as e:
                print(f"样本 {i} 第 {times + 1} 次尝试失败: {e}")
                result[f"response_{times}"] = f"Error: {e}"
                result[f"response_json_{times}"] = None

        target_time_cost = time.time() - start_time
        result["target_attempts"] = target_attempts
        result["target_time_cost"] = target_time_cost
        result["target_avg_attempt_time"] = (
            target_time_cost / target_attempts if target_attempts else 0
        )
        result["time_cost"] = target_time_cost

        if response_json is None or successful_times is None:
            print(f"样本 {i} 无法获取有效响应")
            result["is_correct"] = False
            result["final_pass"] = False
            result["structural_pass"] = False
            result["error_reason"] = "无法获取有效响应"
            return result

        ground_truth = sample["output"]
        result["ground_truth"] = ground_truth

        # ---------- 结构层 ----------
        try:
            sc = structural_compare(response_json, ground_truth)
        except Exception as e:
            print(f"样本 {i} 结构比对异常: {e}")
            result["is_correct"] = False
            result["final_pass"] = False
            result["structural_pass"] = False
            result["error_reason"] = f"比对异常: {e}"
            return result

        result["structural_pass"] = sc["hard_pass"]
        result["exact_match_pass"] = sc["pass"]
        result["hard_diffs"] = sc["hard_diffs"]
        result["semantic_needed"] = sc["semantic_needed"]
        result["semantic_diffs"] = sc["semantic_diffs"]
        result["semantic_compared_count"] = sc["semantic_compared_count"]
        result["all_skipped"] = sc["all_skipped"]
        result["structural_diffs"] = sc["diffs"]

        # ---------- 语义层（LLM judge） ----------
        # 触发条件：
        #   - helper_llm 给定 且 use_llm_judge=True   → 每条都跑
        #   - helper_llm 给定 且 semantic_needed=True → 文案非逐字一致，自动语义复判
        #   - helper_llm 给定 且 all_skipped=True     → 只有语义文本字段，兜底复判
        run_judge = judge_enabled and (
            use_llm_judge or sc["semantic_needed"] or sc["all_skipped"]
        )
        if run_judge:
            jr = judge_sample(
                helper_llm, formatted_prompt, response_json,
                ground_truth, threshold=judge_threshold,
            )
            result["judge_score"] = jr["overall"]
            result["judge_dimensions"] = jr["dimensions"]
            result["judge_pass"] = jr["pass"]
            result["judge_reason"] = jr["reason"]
            if jr.get("error"):
                result["judge_error"] = jr["error"]
        else:
            result["judge_score"] = None
            result["judge_pass"] = None
            result["judge_reason"] = None

        # ---------- 综合 ----------
        if not sc["hard_pass"]:
            # 硬结构错误不由语义 judge 覆盖，避免把分类/字段/数组错误误放行。
            final_pass = False
        elif run_judge:
            final_pass = bool(result["judge_pass"])
        else:
            # 没有 judge 时，只有逐字/硬结构全部通过才算通过；
            # 若存在 semantic_diffs，会在下面给出“需要语义 judge”的原因。
            final_pass = sc["pass"]

        result["final_pass"] = final_pass
        result["is_correct"] = final_pass  # 向后兼容

        if not final_pass:
            reason_parts = []
            if not sc["hard_pass"]:
                reason_parts.append("结构: " + ("; ".join(sc["hard_diffs"]) or "硬结构字段不一致"))
            if sc["semantic_needed"]:
                if run_judge:
                    reason_parts.append(
                        "语义文本: " + ("; ".join(sc["semantic_diffs"]) or "自然语言字段不一致")
                    )
                else:
                    reason_parts.append(
                        "语义待判: " + ("; ".join(sc["semantic_diffs"]) or "自然语言字段不一致")
                        + "（未配置 Helper Judge）"
                    )
            if sc["all_skipped"] and not run_judge and not sc["pass"]:
                reason_parts.append("结构: 只有自然语言文本字段，未启用 LLM judge，无法判定")
            if run_judge and not result.get("judge_pass"):
                reason_parts.append(
                    f"语义: score={result['judge_score']} < {judge_threshold}; "
                    f"reason={result.get('judge_reason') or '(空)'}"
                )
            if reason_parts:
                result["error_reason"] = "; ".join(reason_parts)

        return result

    # 并行执行评测
    results = []
    correct = 0
    structural_correct = 0
    structural_eligible = 0
    semantic_correct = 0
    semantic_eligible = 0
    all_time = 0
    all_target_attempts = 0
    min_time = float('inf')
    max_time = 0
    exact_match_correct = 0
    semantic_needed_count = 0
    semantic_override_correct = 0

    print(f"\n开始评测 (共 {total} 个样本, judge={'on' if judge_enabled else 'off'}, "
          f"mode={template_mode}) ...")
    completed = 0
    cancelled = False
    next_idx = 0
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    future_to_idx = {}
    try:
        initial = min(total, max_workers)
        for _ in range(initial):
            future_to_idx[executor.submit(process_sample, next_idx)] = next_idx
            next_idx += 1

        while future_to_idx:
            if stop_flag and stop_flag():
                cancelled = True
                for pending in future_to_idx:
                    pending.cancel()
                break

            done, _pending = concurrent.futures.wait(
                future_to_idx,
                timeout=0.2,
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            if not done:
                continue

            for future in done:
                idx = future_to_idx.pop(future)
                if future.cancelled():
                    continue
                try:
                    result = future.result()
                except Exception as e:
                    result = {
                        "input": eval_data[idx].get("input") if isinstance(eval_data[idx], dict) else None,
                        "is_correct": False,
                        "final_pass": False,
                        "structural_pass": False,
                        "error_reason": f"样本执行异常: {e}",
                        "time_cost": 0,
                    }

                results.append(result)
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

                if result.get("final_pass"):
                    correct += 1
                if result.get("exact_match_pass"):
                    exact_match_correct += 1
                if result.get("semantic_needed"):
                    semantic_needed_count += 1
                    if result.get("judge_pass"):
                        semantic_override_correct += 1
                # 结构层准确率：分母是非 all_skipped 且非格式化失败的样本
                if "structural_pass" in result and not result.get("all_skipped", False) \
                        and result.get("error_reason", "").startswith(("格式化失败", "无法获取")) is False:
                    structural_eligible += 1
                    if result["structural_pass"]:
                        structural_correct += 1
                # 语义层准确率：分母是真正跑过 judge 的样本
                if result.get("judge_pass") is not None:
                    semantic_eligible += 1
                    if result["judge_pass"]:
                        semantic_correct += 1

                tc = result.get("time_cost", 0)
                all_time += tc
                all_target_attempts += result.get("target_attempts", 0)
                if tc > 0:
                    min_time = min(min_time, tc)
                max_time = max(max_time, tc)

                if next_idx < total and not (stop_flag and stop_flag()):
                    future_to_idx[executor.submit(process_sample, next_idx)] = next_idx
                    next_idx += 1

        if cancelled:
            print(f"\n评测已取消，已完成 {completed}/{total} 个样本。")
    finally:
        executor.shutdown(wait=not cancelled, cancel_futures=True)

    if min_time == float('inf'):
        min_time = 0

    denominator = completed if cancelled else total
    overall_accuracy = correct / denominator if denominator > 0 else 0.0
    structural_accuracy = (structural_correct / structural_eligible) if structural_eligible > 0 else None
    semantic_accuracy = (semantic_correct / semantic_eligible) if semantic_eligible > 0 else None
    avg_time = all_time / completed if completed > 0 else 0.0
    avg_target_attempt_time = all_time / all_target_attempts if all_target_attempts > 0 else 0.0

    summary = {
        # 兼容旧字段：accuracy = overall
        "accuracy": overall_accuracy,
        "overall_accuracy": overall_accuracy,
        "structural_accuracy": structural_accuracy,
        "structural_eligible": structural_eligible,
        "structural_correct": structural_correct,
        "semantic_accuracy": semantic_accuracy,
        "semantic_eligible": semantic_eligible,
        "semantic_correct": semantic_correct,
        "exact_match_accuracy": (exact_match_correct / denominator) if denominator > 0 else 0.0,
        "semantic_needed": semantic_needed_count,
        "semantic_overridden_correct": semantic_override_correct,
        "correct": correct,
        "total": total,
        "completed": completed,
        "cancelled": cancelled,
        "results": results,
        "avg_time": avg_time,
        "avg_target_attempt_time": avg_target_attempt_time,
        "target_attempts": all_target_attempts,
        "min_time": min_time,
        "max_time": max_time,
        "judge_enabled": judge_enabled,
        "template_mode": template_mode,
    }

    # 保存结果
    if result_path:
        import os
        os.makedirs(os.path.dirname(result_path), exist_ok=True)
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump({
                "summary": {k: v for k, v in summary.items() if k != "results"},
                "samples": results,
            }, f, ensure_ascii=False, indent=4)
        print(f"评测结果已保存: {result_path}")

    return summary
