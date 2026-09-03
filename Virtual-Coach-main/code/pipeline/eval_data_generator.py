import json

from .json_utils import extract_json_array
from .prompt_generator import extract_placeholders


META_PROMPT_EVAL_AUTO = """你是一个专业的测试数据生成器。根据以下提示词模板和需求描述，生成评测数据集。

# 提示词模板
{prompt_template}

# 需求描述
{requirements}

# 输入变量列表
{placeholders}

# 生成规则
1. 生成10-15个测试样本
2. 每个样本包含 "input" 和 "output" 两个字段
3. "input" 是一个字典，键必须与上面的输入变量列表一一对应
4. "output" 是模型应该返回的正确JSON结果（ground truth）
5. 样本应覆盖各种边界情况和典型场景
6. 确保样本的输入多样性（不同值、不同组合）
7. 覆盖维度只能来自当前提示词模板和需求描述明确要求的业务场景；不要引入模板未要求的分类、分支、字段或输出结构
8. 每个样本的 output 必须严格符合提示词模板中要求的输出格式；output 的字段集合必须与当前提示词模板的 OUTPUT REQUIREMENTS 一致
9. 如果当前提示词模板没有要求分类、category、classification 或多分支判断，不要为了“覆盖场景”自行创造分类字段或三种情况
10. **生产环境一致性规则（极其重要）**：
   - "input" 中的所有字段值**必须使用英文**（模拟真实生产环境中从训练系统产生的上下文数据）。例如：训练目标写 "Knee Protection" 而非 "膝关节保护"，动作名写 "Wall Sit" 而非 "靠墙静蹲"，教练人设写 "Professional Physical Therapist" 而非 "专业物理治疗师"。
   - "output" 中的字段值**必须严格匹配提示词模板中指定的 target_language**。若模板要求输出中文，则 output 值用中文；若要求输出英文，则 output 值用英文。
   - 这模拟真实场景：Context 数据天然来自英文训练系统，只有 LLM 最终输出受 target_language 控制。

# 输出格式
输出一个JSON数组，不要包含任何其他内容：
```json
[
  {{"input": {{...}}, "output": {{...}}}},
  ...
]
```"""


META_PROMPT_EVAL_EXPAND = """你是一个专业的测试数据生成器。根据以下种子数据和提示词模板，扩展生成更多评测数据。

# 提示词模板
{prompt_template}

# 需求描述
{requirements}

# 种子数据（用户提供的示例）
{seed_examples}

# 生成规则
1. 保留所有种子数据
2. 额外生成8-12个新样本
3. 新样本必须与种子数据格式完全一致（相同的 input 和 output 字段结构）
4. 新样本应覆盖种子数据未涵盖的边界情况
5. 保持输入多样性，避免与种子数据过于相似
6. 确保每个新样本的 output 是正确的 ground truth
7. 覆盖维度只能来自当前提示词模板和种子数据体现出的业务场景；不要引入模板未要求的分类、分支、字段或输出结构
8. 如果当前提示词模板没有要求分类、category、classification 或多分支判断，不要自行创造分类字段或三种情况
9. **生产环境一致性规则（极其重要）**：
   - "input" 中的所有字段值**必须使用英文**（模拟真实生产环境中从训练系统产生的上下文数据）。例如：训练目标写 "Knee Protection" 而非 "膝关节保护"，动作名写 "Wall Sit" 而非 "靠墙静蹲"，教练人设写 "Professional Physical Therapist" 而非 "专业物理治疗师"。
   - "output" 中的字段值**必须严格匹配提示词模板中指定的 target_language**。若模板要求输出中文，则 output 值用中文；若要求输出英文，则 output 值用英文。
   - 这模拟真实场景：Context 数据天然来自英文训练系统，只有 LLM 最终输出受 target_language 控制。

# 输出格式
输出一个JSON数组（包含种子数据 + 新生成数据），不要包含任何其他内容：
```json
[
  {{"input": {{...}}, "output": {{...}}}},
  ...
]
```"""

def _compact_requirements_for_eval(requirements: str) -> str:
    """Remove bulky Context reference text before generating eval data."""
    text = requirements or ""
    markers = [
        "\n\n# 全局字段定义",
        "\n# 全局字段定义",
        "\n\n# Global Context",
        "\n# Global Context",
        "\n\n===== [全局 Context]",
        "\n===== [全局 Context]",
    ]
    cut_at = len(text)
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            cut_at = min(cut_at, idx)
    compact = text[:cut_at].strip()
    return compact or text.strip()


def generate_eval_data_auto(helper_llm: callable, prompt_template: str,
                            requirements: str) -> list:
    """
    全自动生成评测数据集。

    参数:
        helper_llm: helper 模型的调用函数
        prompt_template: prompt 模板
        requirements: 用户需求描述

    返回:
        list: 评测数据集 [{"input": {...}, "output": {...}}, ...]
    """
    placeholders = extract_placeholders(prompt_template)
    requirements = _compact_requirements_for_eval(requirements)
    meta_prompt = META_PROMPT_EVAL_AUTO.format(
        prompt_template=prompt_template,
        requirements=requirements,
        placeholders=", ".join(placeholders),
    )
    meta_prompt += (
        "\n\n# 本次生成规模（覆盖上方样本数量要求）\n"
        "只生成 6 个测试样本。每个字段值保持短小，输出紧凑 JSON 数组，不要缩进、不要解释、不要 Markdown。"
    )

    response = helper_llm(meta_prompt)
    if response is None:
        raise RuntimeError("Helper 模型未返回有效响应。")

    eval_data = extract_json_array(response)
    if eval_data is None:
        # 保存完整原始输出到文件，方便排查
        import os as _os
        import tempfile as _tempfile
        _dump_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "data", "eval_result")
        _os.makedirs(_dump_dir, exist_ok=True)
        _dump_path = _os.path.join(_dump_dir, "_eval_data_parse_error.txt")
        with open(_dump_path, "w", encoding="utf-8") as _f:
            _f.write(f"=== 发送给 LLM 的 meta-prompt ===\n{meta_prompt}\n\n=== LLM 原始输出 ===\n{response}")
        raise RuntimeError(
            f"无法从模型输出中提取JSON数组。\n\n"
            f"完整原始输出已保存到:\n{_dump_path}\n\n"
            f"请打开该文件排查 LLM 返回内容。\n\n"
            f"模型输出末尾 500 字:\n{response[-500:]}"
        )

    # 修复并验证数据格式
    _repair_missing_inputs(eval_data, placeholders)
    _validate_eval_data(eval_data, placeholders)
    return eval_data


def generate_eval_data_from_seeds(helper_llm: callable, prompt_template: str,
                                  requirements: str, seeds_json: str) -> list:
    """
    从种子样本扩充生成评测数据集。

    参数:
        helper_llm: helper 模型的调用函数
        prompt_template: prompt 模板
        requirements: 用户需求描述
        seeds_json: 用户提供的种子数据（JSON字符串）

    返回:
        list: 评测数据集
    """
    # 解析种子数据
    try:
        seeds = json.loads(seeds_json)
        if not isinstance(seeds, list):
            raise ValueError("种子数据必须是JSON数组")
    except json.JSONDecodeError as e:
        raise ValueError(f"种子数据JSON解析失败: {e}")

    requirements = _compact_requirements_for_eval(requirements)
    meta_prompt = META_PROMPT_EVAL_EXPAND.format(
        prompt_template=prompt_template,
        requirements=requirements,
        seed_examples=json.dumps(seeds, ensure_ascii=False, indent=2),
    )
    meta_prompt += (
        "\n\n# 本次扩充规模（覆盖上方样本数量要求）\n"
        "在保留种子样本的基础上，只额外生成 4 个新样本。输出紧凑 JSON 数组，不要缩进、不要解释、不要 Markdown。"
    )

    response = helper_llm(meta_prompt)
    if response is None:
        raise RuntimeError("Helper 模型未返回有效响应。")

    eval_data = extract_json_array(response)
    if eval_data is None:
        import os as _os
        _dump_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "data", "eval_result")
        _os.makedirs(_dump_dir, exist_ok=True)
        _dump_path = _os.path.join(_dump_dir, "_eval_data_parse_error.txt")
        with open(_dump_path, "w", encoding="utf-8") as _f:
            _f.write(f"=== 发送给 LLM 的 meta-prompt ===\n{meta_prompt}\n\n=== LLM 原始输出 ===\n{response}")
        raise RuntimeError(
            f"无法从模型输出中提取JSON数组。\n\n"
            f"完整原始输出已保存到:\n{_dump_path}\n\n"
            f"请打开该文件排查 LLM 返回内容。\n\n"
            f"模型输出末尾 500 字:\n{response[-500:]}"
        )

    placeholders = extract_placeholders(prompt_template)
    _repair_missing_inputs(eval_data, placeholders)
    _validate_eval_data(eval_data, placeholders)
    return eval_data


def _find_nested_value(value, key):
    if isinstance(value, dict):
        if key in value:
            return value[key], True
        for child in value.values():
            found, ok = _find_nested_value(child, key)
            if ok:
                return found, True
    elif isinstance(value, list):
        for item in value:
            found, ok = _find_nested_value(item, key)
            if ok:
                return found, True
    return None, False


def _repair_missing_inputs(eval_data: list, placeholders: list):
    """Promote nested values to top-level input keys required by prompt placeholders."""
    required = set(placeholders or [])
    if not required:
        return
    for sample in eval_data or []:
        if not isinstance(sample, dict) or not isinstance(sample.get("input"), dict):
            continue
        input_obj = sample["input"]
        for field in sorted(required - set(input_obj.keys())):
            found, ok = _find_nested_value(input_obj, field)
            if ok:
                input_obj[field] = found
            else:
                input_obj[field] = ""


def _validate_eval_data(eval_data: list, placeholders: list):
    """验证评测数据格式。"""
    for i, sample in enumerate(eval_data):
        if not isinstance(sample, dict):
            raise ValueError(f"样本 {i} 不是字典")
        if "input" not in sample or "output" not in sample:
            raise ValueError(f"样本 {i} 缺少 'input' 或 'output' 字段")
        if not isinstance(sample["input"], dict):
            raise ValueError(f"样本 {i} 的 'input' 不是字典")
        if not isinstance(sample["output"], dict):
            raise ValueError(f"样本 {i} 的 'output' 不是字典")

        # 检查 input 的键是否包含所有占位符
        missing = set(placeholders) - set(sample["input"].keys())
        if missing:
            raise ValueError(
                f"样本 {i} 的 input 缺少占位符: {sorted(missing)}。"
                "评测数据已拒绝使用，请重新生成或手动补齐 input 顶层字段。"
            )
