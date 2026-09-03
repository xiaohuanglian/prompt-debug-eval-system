"""LLM-as-Judge：当结构比对无法判定（all_skipped 或字段都是长文本）时，
用 helper 模型按 rubric 给样本打分，避免 100% 假阳性。
"""

import json

from .json_utils import extract_last_complete_json


# rubric 维度名 + 中文标签，喂给 helper 模型时维度名走英文 key，便于解析。
DEFAULT_RUBRIC = [
    ("faithfulness_to_input", "忠实输入：是否准确使用 input 中提供的字段值"),
    ("compliance_with_generation_rules", "符合 GENERATION RULES：是否满足结构、长度、句式等显式生成规则"),
    ("no_restriction_violation", "未违反 RESTRICTIONS：是否触犯禁止项（敏感词、格式标记、寒暄等）"),
    ("semantic_alignment_with_ground_truth", "语义对齐：与 ground truth 的核心信息是否一致（允许措辞差异）"),
]

DEFAULT_THRESHOLD = 4

# 评分 meta-prompt。说明:
# - input/predicted/ground_truth 都以 JSON 形式塞进 prompt
# - prompt_for_target 完整保留，让 judge 看到 GENERATION RULES / RESTRICTIONS 上下文
# - 用 ```json``` 包裹输出，便于 extract_last_complete_json 解析
JUDGE_META_PROMPT = """你是一名严格的 LLM 输出评测官。下面是一次实际样本评测，请按 rubric 给出 0-5 分（含 0 与 5）。

# 提交给 target 模型的完整 prompt（含 ROLE/CONTEXT/RULES/RESTRICTIONS）
{prompt_for_target}

# Target 模型实际输出（已抽取的 JSON 对象）
{predicted}

# Ground truth（参考答案）
{ground_truth}

# 评分维度
{rubric_block}

# 评分规则
- 每个维度独立给 0-5 分（0=完全失败，5=完美满足）。
- 综合得分 = 四个维度的算术平均，向下取整到 0-5 之间。
- 在 reason 中**用中文**简述失分点；若全部满分简写"全部通过"即可。
- 若 predicted 为空对象/明显格式错误，直接给 0 分并在 reason 注明。

# 输出格式（必须为合法 JSON，且仅一个 JSON 对象）
```json
{{
  "dimensions": {{
    "faithfulness_to_input": 0,
    "compliance_with_generation_rules": 0,
    "no_restriction_violation": 0,
    "semantic_alignment_with_ground_truth": 0
  }},
  "overall": 0,
  "reason": "..."
}}
```
"""


def _format_rubric_block(rubric):
    lines = []
    for key, desc in rubric:
        lines.append(f"- `{key}`：{desc}")
    return "\n".join(lines)


def _dump(value):
    """把任意值转为 JSON 字符串，None 保持 'null'。"""
    return json.dumps(value, ensure_ascii=False, indent=2)


def judge_sample(helper_llm,
                 prompt_for_target: str,
                 predicted,
                 ground_truth,
                 rubric=None,
                 threshold: int = DEFAULT_THRESHOLD) -> dict:
    """
    用 helper 模型给单个样本打分。

    参数:
        helper_llm: helper 模型调用函数 (prompt: str) -> str
        prompt_for_target: 实际发给 target 模型的完整 prompt（已 .format() 过）
        predicted: target 模型的输出（已 extract_last_complete_json 后的结构化对象，可为 None）
        ground_truth: 评测数据集中的 output 字段
        rubric: [(key, description), ...]，缺省用 DEFAULT_RUBRIC
        threshold: 综合分 >= threshold 视为通过

    返回:
        {
            "overall": int,
            "dimensions": {key: int, ...},
            "pass": bool,
            "reason": str,
            "raw": str,                # 模型原始返回（便于排查解析失败）
            "error": Optional[str],    # 解析失败时填写
        }
    """
    rubric = rubric or DEFAULT_RUBRIC

    meta = JUDGE_META_PROMPT.format(
        prompt_for_target=prompt_for_target,
        predicted=_dump(predicted),
        ground_truth=_dump(ground_truth),
        rubric_block=_format_rubric_block(rubric),
    )

    try:
        raw = helper_llm(meta)
    except Exception as e:
        return {
            "overall": 0,
            "dimensions": {},
            "pass": False,
            "reason": f"helper_llm 调用异常: {e}",
            "raw": "",
            "error": str(e),
        }

    if raw is None:
        return {
            "overall": 0,
            "dimensions": {},
            "pass": False,
            "reason": "helper_llm 未返回",
            "raw": "",
            "error": "helper_llm returned None",
        }

    parsed = extract_last_complete_json(raw)
    if not isinstance(parsed, dict):
        return {
            "overall": 0,
            "dimensions": {},
            "pass": False,
            "reason": f"无法解析 judge 输出 JSON: {raw[:200]}",
            "raw": raw,
            "error": "parse_failed",
        }

    dimensions = parsed.get("dimensions") or {}
    overall_raw = parsed.get("overall")

    # 容错：模型偶尔会返回 float 或字符串
    try:
        overall = int(overall_raw) if overall_raw is not None else _avg_dims(dimensions, rubric)
    except (TypeError, ValueError):
        overall = _avg_dims(dimensions, rubric)

    # 把维度强制收敛到 int 0-5
    dim_out = {}
    for key, _desc in rubric:
        val = dimensions.get(key)
        try:
            dim_out[key] = max(0, min(5, int(val))) if val is not None else 0
        except (TypeError, ValueError):
            dim_out[key] = 0

    # 若 overall 缺失或异常，按维度平均回填
    if overall is None:
        overall = _avg_dims(dim_out, rubric)
    overall = max(0, min(5, overall))

    return {
        "overall": overall,
        "dimensions": dim_out,
        "pass": overall >= threshold,
        "reason": str(parsed.get("reason") or "")[:1000],
        "raw": raw,
        "error": None,
    }


def _avg_dims(dimensions, rubric) -> int:
    vals = []
    for key, _desc in rubric:
        v = dimensions.get(key)
        try:
            vals.append(int(v))
        except (TypeError, ValueError):
            continue
    if not vals:
        return 0
    return int(sum(vals) / len(vals))
