import os
import sys

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..')
sys.path.insert(0, project_root)

try:
    from code.models.glm_4_air import llm_response
    from data.prompt.DecisionScenario5 import PROMPT1, PROMPT2
except ImportError as e:
    print(f"Import error: {e}")
    # 如果导入失败，尝试相对导入
    from ..models.glm_4_air import llm_response

import json
import re
from typing import Any, Dict, List, Tuple


# =========================
# 1) Prompt 模板
# =========================

PROMPT1 = """
你是一个严苛的康复指导教练。你可以选择启用部分工具来更好地服务用户。
请基于“上一组真实情况 + 教练风格 + 用户偏好”，从工具清单中做出下一组训练要启用的工具决策。

# 输入

## 上一组的上下文信息
{INTRAGROUP_CONTEXT}

## 教练风格（一句话）
{COACH_STYLE_ONE_LINE}

## 用户偏好（一句话）
{USER_PREFERENCE_ONE_LINE}

## 工具清单（每行一个工具：工具名 - 一句话能力描述）
{TOOLS_ONE_LINERS}

# 决策规则（必须遵守）
1) 工具名必须严格从“工具清单”中逐字选择；不得编造、改名、缩写。
2) 允许“启用工具”为空数组（即本组不启用任何工具）。
3) 最多启用 3 个工具；如超过 3 个必须合并/舍弃，保留最关键的。
4) 每个“理由/原因”必须是**一句话**，且必须引用上一组信息中的具体信号（如：疼痛、疲劳、完成度、动作质量、依从性、风险点、时间预算等）。
5) 优先级：安全与风险控制 > 训练效果 > 用户体验 > 成本/复杂度。
6) 输出只能是 JSON；不得包含多余文本、不得使用 Markdown 代码块。

# 输出 JSON 格式（必须严格一致）

```json
{{
  "启用工具": [
    {{
      "工具": "工具名",
      "理由": "一句话（包含上一组证据）"
    }}
  ],
  "不启用工具": [
    {{
      "工具": "工具名",
      "原因": "一句话（包含上一组证据或明确说明不需要）"
    }}
  ],
  "自检": {{
    "是否满足教练风格": true,
    "是否满足用户偏好": true,
    "是否充分考虑上一组的情况": true,
    "证据": ["最多3条，每条一句话，指向上一组具体信息"],
    "风险是否可控": true
  }}
}}
```

"""

PROMPT2 = """
你是一个严苛的康复指导教练。以下工具已经确认会在“下一组训练”中使用。
你的任务：基于【上一组实际情况 + 当前实时情况 + 教练风格 + 用户偏好】，对每个工具的“触发条件”进行必要的微调，使其更安全、更有效、更符合用户。

# 输入

## 上一组的上下文信息
{INTRAGROUP_CONTEXT}

## 当前实时情况（如果为空，按“未知/需保守”处理）
{REALTIME_CONTEXT}

## 教练风格（一句话）
{COACH_STYLE_ONE_LINE}

## 用户偏好（一句话）
{USER_PREFERENCE_ONE_LINE}

## 已确认要使用的工具清单（每行：工具名 - 当前触发条件 - 一句话能力描述）
{TOOLS_ONE_LINERS}

# 修改规则（必须遵守）
1) 工具名必须严格来自“已确认要使用的工具清单”，不得新增工具、不得改名。
2) 允许“需要修改触发条件的工具”为[]（即全部不改）。
3) “修改后的触发条件”必须是**可执行的判据**，用清晰的布尔规则表达：
   - 推荐格式：IF <条件> THEN <触发> ELSE <不触发/降级>
   - 条件必须尽量引用可观测信号：疼痛评分、疲劳、动作质量、完成度、心率/步数（若有）、时间预算等。
4) 修改优先级：安全与风险控制 > 训练效果 > 依从性 > 成本/复杂度。
5) 若当前实时情况缺失或不确定，触发条件必须更保守（提高阈值/增加停止条件/减少强度）。
6) 每条“理由/原因”必须是一句话，并且必须指出来自上一组或实时情况的具体依据。
7) 输出只能是 JSON，不能包含任何额外文本；不要使用 Markdown 代码块。

# 输出 JSON 格式（必须严格一致）

```json
{{
  "需要修改触发条件的工具": [
    {{
      "工具": "工具名",
      "修改后的触发条件": "IF ... THEN ... ELSE ...",
      "理由": "一句话（含证据）"
    }}
  ],
  "不需要修改触发条件的工具": [
    {{
      "工具": "工具名",
      "原因": "一句话（含证据）"
    }}
  ],
  "自检": {{
    "是否满足教练风格": true,
    "是否满足用户偏好": true,
    "是否充分考虑上一组的情况": true,
    "证据": ["最多3条，每条一句话，指向上一组/实时情况"],
    "风险是否可控": true
  }}
}}
```

"""

# =========================
# 2) description 解析与替换
# =========================

TRIGGER_HEADER = "# 触发条件"

def extract_section(description: str, header: str) -> str:
    """
    提取 header 下的内容，直到下一个 '# ' 标题或文末。
    """
    pattern = rf"({re.escape(header)}\s*\n)(.*?)(?=\n# |\Z)"
    m = re.search(pattern, description, flags=re.S)
    if not m:
        return ""
    return m.group(2).strip()


def replace_section(description: str, header: str, new_content: str) -> str:
    """
    替换 header 段落内容为 new_content（保持其他段落不变）。
    若 header 不存在，则追加到文末（更保守做法：你也可以选择报错）。
    """
    pattern = rf"({re.escape(header)}\s*\n)(.*?)(?=\n# |\Z)"
    if re.search(pattern, description, flags=re.S):
        return re.sub(
            pattern,
            lambda m: m.group(1) + new_content.strip() + "\n",
            description,
            flags=re.S,
        )
    else:
        # header 不存在：追加
        suffix = "\n" if not description.endswith("\n") else ""
        return description + suffix + f"\n{header}\n{new_content.strip()}\n"


# =========================
# 3) 工具 one-liners 生成（给 prompt 用）
# =========================

def tool_capability_oneliner(tool: Dict[str, Any]) -> str:
    """
    从 tool['description'] 里抽取“基本功能”段落的第一行作为能力描述（你也可以改成更强的摘要规则）。
    """
    desc = tool.get("description", "") or ""
    basic = extract_section(desc, "# 基本功能")
    if not basic:
        return "（未提供基本功能）"
    # 取第一行/第一句作为 one-liner
    first_line = basic.splitlines()[0].strip()
    return first_line if first_line else basic[:60]


def tools_for_prompt1(tools: List[Dict[str, Any]]) -> str:
    """
    prompt1: 工具名 - 能力描述
    """
    lines = []
    for t in tools:
        name = t.get("name", "")
        cap = tool_capability_oneliner(t)
        lines.append(f"{name} - {cap}")
    return "\n".join(lines)


def tools_for_prompt2(enabled_tools: List[Dict[str, Any]]) -> str:
    """
    prompt2: 工具名 - 当前触发条件 - 能力描述
    """
    lines = []
    for t in enabled_tools:
        name = t.get("name", "")
        cur_trg = extract_section(t.get("description", "") or "", TRIGGER_HEADER) or "（当前未定义触发条件，需补全）"
        cap = tool_capability_oneliner(t)
        # 为了可读，触发条件过长就截断；真实落地可不截断
        cur_trg_short = cur_trg if len(cur_trg) <= 200 else (cur_trg[:200] + "…")
        lines.append(f"{name} - {cur_trg_short} - {cap}")
    return "\n".join(lines)


# =========================
# 4) LLM 调用占位（你替换成真实调用）
# =========================

def extract_last_complete_json(text: str):
    """
    提取文本中的最后一个完整的JSON对象
    修复点：
    1. 修正正则表达式，去除多余的转义符，确保能正确匹配 ```json ... ``` 代码块
    2. 修正字符串转义处理逻辑，确保能正确处理字符串中的转义字符
    3. 修复：部分模型输出没有 ```json ...``` 包裹，直接输出 json 或前后有多余内容
    4. 修复：部分模型输出有多余的反斜杠或特殊转义符，尝试预处理
    """
    # 优先匹配 ```json ... ``` 代码块
    _CODE_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.S)

    def _try_load(blob: str):
        # 先尝试直接解析
        try:
            return json.loads(blob)
        except json.JSONDecodeError:
            pass
        # 尝试去除多余转义符
        try:
            blob2 = blob.encode('utf-8').decode('unicode_escape')
            return json.loads(blob2)
        except Exception:
            pass
        # 尝试去除多余的换行、空格
        try:
            return json.loads(blob.strip())
        except Exception:
            pass
        return None

    # ---------- 1) 先看 ```json``` 代码块 ----------
    for block in reversed(_CODE_BLOCK_RE.findall(text)):
        obj = _try_load(block)
        if obj is not None:
            return obj

    # ---------- 2) 从后往前定位 {...} ----------
    # 允许有多余内容，找到最后一个完整的 JSON 对象
    depth = 0
    in_string = False
    escape = False
    start_idx = None

    # 反向扫描，找到最外层 '{' 对应的索引 start
    for i in range(len(text) - 1, -1, -1):
        ch = text[i]

        # 维护 in_string / escape 状态，忽略字符串内部的大括号
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            continue
        else:
            if ch == '"':
                in_string = True
                escape = False
                continue

        if ch == '}':
            if depth == 0:
                end_idx = i
            depth += 1
        elif ch == '{':
            depth -= 1
            if depth == 0:
                start_idx = i
                candidate = text[start_idx:end_idx+1] if 'end_idx' in locals() else text[start_idx:]
                obj = _try_load(candidate)
                if obj is not None:
                    return obj
                # 否则继续向左找上一层可能的 '{'

    # ---------- 3) 兜底：尝试提取所有 {...} 并解析 ----------
    # 有些模型输出会有多余内容，尝试提取所有大括号包裹的内容
    matches = list(re.finditer(r'\{[\s\S]*?\}', text))
    for m in reversed(matches):
        candidate = m.group()
        obj = _try_load(candidate)
        if obj is not None:
            return obj

    return None


def call_llm_json(prompt: str) -> Dict[str, Any]:
    response = llm_response(prompt)
    response_json = extract_last_complete_json(response)
    return response_json

# =========================
# 5) 串联执行：prompt1 -> prompt2 -> 更新 tools.description
# =========================

def run_two_stage_decision(
    tools: List[Dict[str, Any]],
    intragroup_context: str,
    realtime_context: str,
    coach_style_one_line: str,
    user_preference_one_line: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """
    返回：更新后的 tools、prompt1 输出、prompt2 输出
    """
    # name->tool 映射用于校验/索引
    tool_map = {t["name"]: t for t in tools}

    # ---------- Stage 1: 选工具 ----------
    p1 = PROMPT1.format(
        INTRAGROUP_CONTEXT=intragroup_context,
        COACH_STYLE_ONE_LINE=coach_style_one_line,
        USER_PREFERENCE_ONE_LINE=user_preference_one_line,
        TOOLS_ONE_LINERS=tools_for_prompt1(tools),
    )
    out1 = call_llm_json(p1)

    enabled_names = [x["工具"] for x in out1.get("启用工具", []) if isinstance(x, dict) and "工具" in x]
    # 严格过滤：只保留存在于工具清单的工具
    enabled_names = [n for n in enabled_names if n in tool_map]

    enabled_tools = [tool_map[n] for n in enabled_names]

    # 如果没启用任何工具，直接返回（或你也可以跳过 prompt2）
    if not enabled_tools:
        return tools, out1, {
            "需要修改触发条件的工具": [],
            "不需要修改触发条件的工具": [],
            "自检": {
                "是否满足教练风格": True,
                "是否满足用户偏好": True,
                "是否充分考虑上一组的情况": True,
                "证据": ["未启用任何工具，因此无触发条件需要修改"],
                "风险是否可控": True,
            },
        }

    # ---------- Stage 2: 改触发条件 ----------
    p2 = PROMPT2.format(
        INTRAGROUP_CONTEXT=intragroup_context,
        REALTIME_CONTEXT=realtime_context,
        COACH_STYLE_ONE_LINE=coach_style_one_line,
        USER_PREFERENCE_ONE_LINE=user_preference_one_line,
        TOOLS_ONE_LINERS=tools_for_prompt2(enabled_tools),
    )
    out2 = call_llm_json(p2)

    # 应用修改：替换每个工具 description 中的触发条件段落
    for item in out2.get("需要修改触发条件的工具", []) or []:
        if not isinstance(item, dict):
            continue
        name = item.get("工具")
        new_trigger = item.get("修改后的触发条件", "")
        if not name or name not in tool_map:
            continue
        if not isinstance(new_trigger, str) or not new_trigger.strip():
            continue

        old_desc = tool_map[name].get("description", "") or ""
        tool_map[name]["description"] = replace_section(old_desc, TRIGGER_HEADER, new_trigger.strip())

    # 同步回 tools 列表（tool_map 中对象是同一引用，一般不需要这步；写上更清晰）
    updated_tools = [tool_map[t["name"]] for t in tools]

    return updated_tools, out1, out2


# =========================
# 6) 示例入口（你按需改）
# =========================

if __name__ == "__main__":
    # 你的工具列表示例（你实际会更长）
    tools = [
        {
            "type": "function",
            "name": "PainCheck",
            "description": """
# 基本功能
采集用户疼痛评分并判定是否需要降级训练强度。

# 适用情况
疼痛管理、风险控制、训练前后状态评估。

# 不适用情况
用户无法提供主观评分且无替代信号；急性重症需就医。

# 触发条件
默认：每组训练开始前询问一次疼痛评分。
""".strip(),
            "parameters": {
                "type": "object",
                "properties": {
                    "pain_score": {"type": "number", "description": "0-10 疼痛评分"},
                },
                "required": ["pain_score"],
            },
        },
        {
            "type": "function",
            "name": "FormVideoReview",
            "description": """
# 基本功能
分析用户动作视频并给出动作质量反馈与纠错要点。

# 适用情况
动作质量波动、出现代偿、需要纠错的训练阶段。

# 不适用情况
无视频/无法拍摄；隐私原因拒绝上传。

# 触发条件
默认：当上一组出现“动作不稳定/代偿”迹象时触发。
""".strip(),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    ]

    # 上下文输入（你实际会从系统状态填充）
    intragroup_context = "上一组：用户完成度80%，主诉膝前侧疼痛3/10，深蹲末端出现轻微内扣。"
    realtime_context = "当前：用户表示今天睡眠不足，主观疲劳7/10。"
    coach_style = "严苛、重安全、短指令、强调动作质量。"
    user_pref = "不喜欢冗长解释，希望直接给结论与下一步。"

    # 执行（记得实现 call_llm_json）
    updated_tools, out1, out2 = run_two_stage_decision(
        tools, intragroup_context, realtime_context, coach_style, user_pref
    )
    print("Prompt1 output:", json.dumps(out1, ensure_ascii=False, indent=2))
    print("Prompt2 output:", json.dumps(out2, ensure_ascii=False, indent=2))
    print("Updated tools:", updated_tools)