import json


def analyze_errors(results: dict, eval_data: list) -> dict:
    """
    分析评测结果中的错误。

    参数:
        results: run_evaluation 返回的结果
        eval_data: 评测数据集

    返回:
        dict: 错误分析结果
    """
    errors = []
    error_patterns = {
        "hard_structure_mismatch": 0,
        "semantic_quality_failure": 0,
        "semantic_judge_unavailable": 0,
        "exact_text_mismatch": 0,
        "json_parse_error": 0,
        "no_response": 0,
        "unknown": 0,
    }

    for i, result in enumerate(results["results"]):
        if result.get("is_correct"):
            continue

        error_reason = result.get("error_reason", "")
        error_entry = {
            "sample_index": i,
            "input": result.get("input"),
            "expected": result.get("ground_truth"),
            "predicted": None,
            "error_type": "unknown",
            "error_detail": error_reason,
            "hard_diffs": result.get("hard_diffs") or [],
            "semantic_diffs": result.get("semantic_diffs") or [],
            "judge_score": result.get("judge_score"),
            "judge_reason": result.get("judge_reason"),
        }

        if "无法获取有效响应" in error_reason:
            error_entry["error_type"] = "no_response"
            error_patterns["no_response"] += 1
        elif "JSON格式错误" in error_reason or "格式化失败" in error_reason:
            error_entry["error_type"] = "json_parse_error"
            error_patterns["json_parse_error"] += 1
        elif result.get("structural_pass") is False:
            error_entry["error_type"] = "hard_structure_mismatch"
            error_patterns["hard_structure_mismatch"] += 1
        elif result.get("semantic_needed") and result.get("judge_pass") is False:
            error_entry["error_type"] = "semantic_quality_failure"
            error_patterns["semantic_quality_failure"] += 1
        elif result.get("semantic_needed") and result.get("judge_pass") is None:
            error_entry["error_type"] = "semantic_judge_unavailable"
            error_patterns["semantic_judge_unavailable"] += 1
        elif result.get("exact_match_pass") is False:
            error_entry["error_type"] = "exact_text_mismatch"
            error_patterns["exact_text_mismatch"] += 1
        else:
            error_patterns["unknown"] += 1

        # 尝试提取最后一个有效的 response_json
        for key in sorted(result.keys()):
            if key.startswith("response_json_") and result[key] is not None:
                error_entry["predicted"] = result[key]

        errors.append(error_entry)

    return {
        "total": results["total"],
        "correct": results["correct"],
        "accuracy": results.get("accuracy", results.get("overall_accuracy", 0.0)),
        "errors": errors,
        "error_patterns": error_patterns,
    }


META_PROMPT_OPTIMIZE = """你是一个Prompt优化专家。以下是当前提示词模板及其评测结果。请分析错误样本并给出改进建议。

请先判断每个错误到底是 prompt 问题、评测口径问题，还是评测数据 ground truth 质量问题。不要把自然语言同义改写当成分类错误；如果 expected 与 predicted 只是措辞不同但核心语义、字段结构、分类结果一致，应明确建议调整评测逻辑/启用语义 Judge/修订 ground truth，而不是要求 prompt 逐字贴近期望文案。

# 当前提示词模板
{prompt_template}

# 评测结果
总样本数: {total}
正确数: {correct}
准确率: {accuracy}

# 错误样本详情
{error_details}

# 请给出以下内容
1. 错误归因：区分 prompt 缺陷、评测逻辑缺陷、ground truth 数据质量问题
2. 错误模式分析：这些错误是否有共同特征？
3. 根因分析：提示词中哪些部分可能导致了真正的 prompt 错误？
4. 具体改进建议：只针对真正的 prompt 问题列出3-5条可执行改进点
5. 建议的修改片段：给出关键段落的修改建议；如果主要是评测问题，请说明不建议改 prompt 的原因

请用中文回答。"""


META_PROMPT_OPTIMIZE_FROM_MANUAL = """你是一个Prompt优化专家。当前提示词模板的评测结果**全部通过**（准确率 100%），但用户仍然提出了手动优化建议。请根据用户的建议，给出具体的 prompt 修改方案。

# 当前提示词模板
{prompt_template}

# 评测结果
总样本数: {total}
正确数: {correct}
准确率: {accuracy}

# 用户手动输入的优化建议
{manual_suggestions}

# 请给出以下内容
1. 建议理解：复述你对用户优化意图的理解
2. 具体改进方案：针对每一条用户建议，给出对应的 prompt 修改方案
3. 建议的修改片段：给出关键段落的具体修改前后对比（原文 → 修改后）
4. 注意事项：这些修改是否可能引入新的问题或边界情况

请用中文回答。"""


def suggest_improvements(helper_llm: callable, prompt_template: str,
                         error_analysis: dict,
                         manual_suggestions: str = "") -> str:
    """
    使用 helper 模型分析错误并给出改进建议。

    参数:
        helper_llm: helper 模型调用函数
        prompt_template: 当前 prompt 模板
        error_analysis: analyze_errors 的输出
        manual_suggestions: 用户手动输入的优化建议（即使全对也生效）

    返回:
        str: 改进建议文本
    """
    has_errors = bool(error_analysis.get("errors"))
    has_manual = bool(manual_suggestions.strip())

    # 情况1: 有错误 → 正常分析
    if has_errors:
        error_types = {err.get("error_type") for err in error_analysis["errors"]}
        if error_types == {"semantic_judge_unavailable"} and not has_manual:
            return (
                "本轮失败主要不是 prompt 内容错误，而是自然语言文本字段存在非逐字差异，"
                "但未启用 Helper 语义 Judge，系统无法判断这些差异是否可接受。\n\n"
                "建议：\n"
                "1. 重新运行评测，并确保已配置 Helper 模型；系统会自动对自然语言字段做语义复判。\n"
                "2. 不要仅因为 expected/predicted 措辞不同就自动优化 prompt。\n"
                "3. 若业务确实要求固定话术，请在需求和 prompt 中明确“必须逐字输出固定模板”，"
                "否则应把 ground truth 视为参考答案而非快照答案。"
            )

        error_details_parts = []
        for err in error_analysis["errors"]:
            part = f"样本 {err['sample_index']}:\n"
            part += f"  错误类型: {err['error_type']}\n"
            part += f"  详情: {err['error_detail']}\n"
            if err.get("hard_diffs"):
                part += f"  硬结构差异: {json.dumps(err['hard_diffs'], ensure_ascii=False)}\n"
            if err.get("semantic_diffs"):
                part += f"  语义文本差异: {json.dumps(err['semantic_diffs'], ensure_ascii=False)}\n"
            if err.get("judge_score") is not None:
                part += f"  Judge分数: {err.get('judge_score')}\n"
            if err.get("judge_reason"):
                part += f"  Judge原因: {err.get('judge_reason')}\n"
            if err.get("expected"):
                part += f"  期望: {json.dumps(err['expected'], ensure_ascii=False)}\n"
            if err.get("predicted"):
                part += f"  实际: {json.dumps(err['predicted'], ensure_ascii=False)}\n"
            if err.get("input"):
                part += f"  输入: {json.dumps(err['input'], ensure_ascii=False)}\n"
            error_details_parts.append(part)

        error_details = "\n".join(error_details_parts)

        # 如果有手动建议，追加到错误详情后
        if has_manual:
            error_details += (
                "\n\n--- 用户额外手动输入的优化建议 ---\n"
                + manual_suggestions
                + "\n请同时考虑以上错误样本和用户手动建议，给出综合改进方案。"
            )

        meta_prompt = META_PROMPT_OPTIMIZE.format(
            prompt_template=prompt_template,
            total=error_analysis["total"],
            correct=error_analysis["correct"],
            accuracy=f"{error_analysis['accuracy']:.2%}",
            error_details=error_details,
        )

        response = helper_llm(meta_prompt)
        if response is None:
            return "Helper 模型未返回有效响应，无法生成改进建议。"
        return response

    # 情况2: 无错误但有手动建议 → 基于用户建议生成优化方案
    if has_manual:
        meta_prompt = META_PROMPT_OPTIMIZE_FROM_MANUAL.format(
            prompt_template=prompt_template,
            total=error_analysis["total"],
            correct=error_analysis["correct"],
            accuracy=f"{error_analysis['accuracy']:.2%}",
            manual_suggestions=manual_suggestions,
        )

        response = helper_llm(meta_prompt)
        if response is None:
            return "Helper 模型未返回有效响应，无法根据手动建议生成改进方案。"
        return response

    # 情况3: 无错误且无手动建议
    return "所有样本全部正确，无需改进。如有优化想法，请使用「手动输入优化建议」功能。"


META_PROMPT_APPLY = """你是一个Prompt工程师。请根据以下优化建议，直接修改当前的提示词模板，输出修改后的完整模板。

# 当前提示词模板
{prompt_template}

# 优化建议
{suggestions}

# 修改规则
1. 保持原有的板块结构（如 ROLE / CONTEXT / TASK / GENERATION RULES / RESTRICTIONS / OUTPUT REQUIREMENTS 等）
2. 只修改建议中指出的部分，其余内容严格保持不变
3. 保持所有占位符格式与原文完全一致，花括号和变量名都不要改动
4. 保持已有的输出格式要求（JSON schema、字段定义等）不变，除非建议明确要求修改

# 输出格式
直接输出修改后的完整模板内容，用 ```template``` 包裹：
```template
...修改后的完整模板...
```"""


def apply_improvements(helper_llm: callable, prompt_template: str,
                       suggestions: str) -> str:
    """
    让 helper 模型根据优化建议直接改写 prompt 模板。

    参数:
        helper_llm: helper 模型调用函数
        prompt_template: 当前 prompt 模板
        suggestions: 优化建议文本（来自 suggest_improvements 或手动输入）

    返回:
        str: 修改后的完整 prompt 模板
    """
    import re as _apply_re

    meta_prompt = META_PROMPT_APPLY.format(
        prompt_template=prompt_template,
        suggestions=suggestions,
    )

    response = helper_llm(meta_prompt)
    if response is None:
        raise RuntimeError("Helper 模型未返回有效响应，无法应用优化建议。")

    # 提取 ```template ... ``` 内容
    match = _apply_re.search(r"```template\s*(.*?)\s*```", response, _apply_re.S)
    if match:
        return match.group(1)

    # 兜底：尝试提取任意 ``` ... ```
    match = _apply_re.search(r"```\s*(.*?)\s*```", response, _apply_re.S)
    if match:
        content = match.group(1)
        if len(content) > 50:
            return content

    # 最终兜底：直接返回去首尾空白的响应
    stripped = response.strip()
    if stripped:
        return stripped

    raise RuntimeError("无法从模型输出中提取修改后的 prompt 模板。")
