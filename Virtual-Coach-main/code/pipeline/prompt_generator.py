import os
import re
import json


# 系统模板根目录
SYSTEM_INFO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "system_info"
)

# ─── 占位符与 OUTPUT 规则（两套 meta-prompt 共用） ──────────────────────────

_PLACEHOLDER_RULES = """**占位符使用规则（极其重要，违反将直接导致评测失败）**：
   - 输入变量必须使用双花括号占位符语法：{{{{field_name}}}}，例如 {{{{target_language}}}}、{{{{coach_persona}}}}。
   - 字段占位符是系统底层通用协议，不是 Python `.format()` 语法；不要生成单花括号 {{field_name}}。
   - 占位符**只能用于把变量值直接嵌入到给模型阅读的自然语言上下文**中，例如："用户的目标是：{{{{investment_goal}}}}"。
   - **严禁**在条件判断/规则描述中嵌入占位符。错误示例：`如{{{{is_risk_detected}}}}=true则…`，替换后会变成 `如False=true则…`，逻辑彻底崩坏；正确写法是引用**字段英文名**：`如果 is_risk_detected 字段为 true 则…`。
   - **严禁**把占位符塞进固定话术里，例如：`"为你{{{{adjustment_proposal_details}}}}"`，当值为 None 或空字符串时会变成 `"为你None"` / `"为你"`。涉及条件话术请改写为「先判定字段，再输出对应文本」。
   - 模板中的 JSON 示例使用普通 JSON 花括号即可，例如 `{{ "field": "value" }}`；只有真实输入字段使用 `{{{{field_name}}}}`。
   - **生产环境语言约束**：所有输入字段的**值**在生产环境中均来自英文训练系统（如 training_focus="Knee Protection"、exercise_list=["Wall Sit"]），模板中的语言参数 target_language **仅控制最终输出语言**。模板的 CONTEXT / TASK 段应据此设计：字段引用用英文名，输出指令指定目标语言即可，不要假设输入值会被翻译。"""

_OUTPUT_RULES = """**OUTPUT REQUIREMENTS 板块（极其重要，缺失会导致全部样本判错）**：
   - 必须给出**完整字段定义表**：每个字段的英文名、类型（string/number/boolean/object/array/null）、取值范围或含义说明。
   - 必须给出一个**完整、可直接复制的 JSON 示例**（用 ```json``` 代码块包裹），字段名与字段表完全一致。
   - 严禁出现"结构如下："然后内容缺失或被截断的情况。
   - 字段命名必须与需求文档中给出的字段保持一致；如果需求未明示字段，沿用业务文档中的字段名，**禁止自创字段名**。"""


_PLACEHOLDER_RULES = """**占位符使用规则（必须严格遵守）**：
   - 输入变量必须使用上线 Go template 语法：{{.field_name}} 或 {{.field.sub_field}}，例如 {{.target_language}}、{{.coach_persona}}。
   - 字段占位符不是 Python `.format()` 语法；不要生成单花括号 {field_name}，也不要省略 Go template 的前导点。
   - 占位符只能用于把变量值嵌入模型可读的上下文，例如：用户目标：{{.investment_goal}}。
   - 条件和业务规则里引用字段名即可，不要把占位符写进逻辑判断表达式。
   - 模板中的 JSON 示例使用普通 JSON 花括号；只有真实输入字段使用 {{.field_name}} 或 {{.field.sub_field}}。
"""

_PLACEHOLDER_RULES = """**占位符使用规则（必须严格遵守）**：
   - 输入变量必须使用上线 Go template 语法：{{{{.field_name}}}} 或 {{{{.field.sub_field}}}}，例如 {{{{.target_language}}}}、{{{{.coach_persona}}}}。
   - 字段占位符不是 Python `.format()` 语法；不要生成省略前导点的中间格式，也不要生成单花括号占位符。
   - 占位符只能用于把变量值嵌入模型可读上下文，例如：用户目标：{{{{.investment_goal}}}}。
   - 条件和业务规则里引用字段名即可，不要把占位符写进逻辑判断表达式。
   - 模板中的 JSON 示例使用普通 JSON 花括号；只有真实输入字段使用 {{{{.field_name}}}} 或 {{{{.field.sub_field}}}}。
"""

META_PROMPT_GENERATE = """你是一个专业的Prompt工程师。根据以下需求描述，生成一个高质量的LLM提示词模板。

# 用户需求
{requirements}

{field_schema_block}# 生成规则
1. 先从用户需求中识别当前场景自己的任务目标、输入字段、输出字段和业务规则；只围绕当前场景生成 Prompt。
2. """ + _PLACEHOLDER_RULES + """
3. """ + _OUTPUT_RULES + """
4. 模板必须包含以下部分：ROLE / CONTEXT / TASK / GENERATION RULES / RESTRICTIONS / OUTPUT REQUIREMENTS。
5. 严禁继承其他场景的业务结构：如果当前需求没有要求三分类、classification/category、三段 feedback 或多个输出对象，不要生成这些内容。
6. 输出字段必须来自当前需求、Context 文档或当前场景文档；不要因为参考过其他 Prompt 就复用旧字段。
7. 规则要足够严格但不过度：只写能约束当前任务正确性的规则，不要把评测系统自身的话术写入生产 Prompt。
8. 生成前自检：占位符是否全部为双括号、占位符是否全部来自字段白名单、OUTPUT REQUIREMENTS 是否只包含当前场景需要的输出字段。
9. 模板必须是纯文本字符串，不要包含 Python 代码。

{retry_hint}# 输出格式
直接输出提示词模板内容，用```template```包裹：
```template
...你的模板内容...
```"""


META_PROMPT_GENERATE_WITH_TEMPLATE = """你是一个专业的Prompt工程师。根据以下需求描述，参照系统预设的模板格式，生成一个高质量的LLM提示词模板。

# 系统预设模板参考
以下是系统要求的 Prompt 模板格式和规范，你生成的模板必须遵循相同的结构和风格：

{system_template}

# 用户需求
{requirements}

{field_schema_block}# 生成规则
1. 先从用户需求中识别当前场景自己的任务目标、输入字段、输出字段和业务规则；只围绕当前场景生成 Prompt。
2. """ + _PLACEHOLDER_RULES + """
3. """ + _OUTPUT_RULES + """
4. **只复用系统预设模板的板块结构和写作风格，不复用其中的具体业务规则、分类逻辑、输出字段或示例内容**，除非当前用户需求明确要求。
5. 每个板块的内容必须根据当前用户需求填写；不要把其他场景的三分类、三段 feedback、旧字段名或旧 JSON 结构带入。
6. 模板应该清晰、严格，减少模型输出的歧义，但不要把评测系统自身的话术写入生产 Prompt。
7. 模板必须是纯文本字符串，不要包含 Python 代码。
8. OUTPUT REQUIREMENTS 板块必须严格按规则 3 给出完整字段表与 JSON 示例，**不允许只写一句"输出 JSON"就结束**。
9. 生成前自检：占位符是否全部为双括号、占位符是否全部来自字段白名单、OUTPUT REQUIREMENTS 是否只包含当前场景需要的输出字段。

{retry_hint}# 输出格式
直接输出提示词模板内容，用```template```包裹：
```template
...你的模板内容...
```"""


# ─── 自动注入的 OUTPUT Schema 区块标记（用于幂等替换） ──────────────────────

_AUTO_SCHEMA_BEGIN = "<!-- AUTO_OUTPUT_SCHEMA_START -->"
_AUTO_SCHEMA_END = "<!-- AUTO_OUTPUT_SCHEMA_END -->"
_AUTO_SCHEMA_RE = re.compile(
    re.escape(_AUTO_SCHEMA_BEGIN) + r".*?" + re.escape(_AUTO_SCHEMA_END),
    re.S,
)


# ─── 公开接口 ────────────────────────────────────────────────────────────────


def _render_field_schema_block(field_schema: dict) -> str:
    """Render the selected Context whitelist for the meta prompt."""
    if not field_schema:
        return ""
    parts = [
        "# Context 字段白名单（极其重要：只能使用下列字段；写入 Prompt 时必须使用 {{.field_name}} / {{.field.path}}）",
        "注意：白名单是精确匹配，不允许自动上升到父级对象。",
        "例如只列出 {{.training_session.grading}} 或 {{.training_session.workout_vector}} 时，禁止使用 {{.training_session}}，除非 {{.training_session}} 本身也在下列白名单中。",
    ]
    for kind, label in (("input_fields", "输入字段"), ("output_fields", "输出字段")):
        fields = field_schema.get(kind) or []
        parts.append(f"\n## {label}")
        if not fields:
            parts.append("（无）")
            continue
        allowed_names = {f.get("name") for f in fields if f.get("name")}
        for f in fields:
            name = f.get("name") or ""
            source = f.get("source_excerpt") or f.get("path") or ""
            source_text = f" - {source}" if source else ""
            parent_note = ""
            parent = name.rsplit(".", 1)[0] if "." in name else ""
            if parent and parent not in allowed_names:
                parent_note = f"；只能用此精确路径，不能改写为 {{{{.{parent}}}}}"
            parts.append(
                f"- `{{{{.{name}}}}}` ({f.get('type') or 'unknown'}, "
                f"{'必填' if f.get('required', True) else '可空'}){parent_note}{source_text}"
            )
    parts.append("")
    return "\n".join(parts) + "\n"

def verify_placeholders_against_schema(prompt_template: str,
                                       field_schema: dict) -> tuple:
    """
    校验 prompt 模板里出现的占位符是否全部在 field_schema.input_fields 白名单内。

    返回:
        (ok: bool, illegal: list[str])
    """
    if not field_schema:
        return True, []
    placeholders = extract_placeholders(prompt_template)
    allowed = {f["name"] for f in (field_schema.get("input_fields") or [])}
    illegal = [p for p in placeholders if p not in allowed]
    return (len(illegal) == 0), illegal


def _escape_for_meta_format(text: str) -> str:
    """Escape literal braces before injecting text into a .format() template."""
    return (text or "").replace("{", "{{").replace("}", "}}")


def load_system_templates() -> list:
    """
    扫描 system_info/ 目录，返回所有可用的参考模板列表。

    返回:
        list of dict: [{"name": "six_section_template", "path": "...", "content": "..."}, ...]
    """
    templates = []
    if not os.path.isdir(SYSTEM_INFO_DIR):
        return templates

    for fname in sorted(os.listdir(SYSTEM_INFO_DIR)):
        fpath = os.path.join(SYSTEM_INFO_DIR, fname)
        if fname.lower() == "readme.md":
            continue
        if os.path.isfile(fpath) and fname.endswith((".md", ".txt", ".json", ".py")):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                name = os.path.splitext(fname)[0]
                templates.append({
                    "name": name,
                    "path": fpath,
                    "content": content,
                })
            except Exception as e:
                print(f"读取系统模板失败 {fpath}: {e}")
    return templates


def generate_prompt_template(helper_llm: callable, requirements: str,
                             template_ref: str = "",
                             field_schema: dict = None,
                             max_retries: int = 3) -> str:
    """
    使用 helper 模型根据需求生成 prompt 模板。

    参数:
        helper_llm: helper 模型的调用函数 (prompt: str) -> str
        requirements: 用户描述的需求
        template_ref: 可选的模板内容（参考模板结构），为空时使用默认规则
        field_schema: 已确认字段表，会作为白名单注入 meta-prompt 并对生成结果做校验
        max_retries: 占位符违规时的最大重试次数

    返回:
        str: 生成的 prompt 模板
    """
    field_block = _render_field_schema_block(field_schema)
    retry_hint = ""

    last_template = None
    last_illegal = []

    for attempt in range(max_retries):
        if template_ref:
            meta_prompt = META_PROMPT_GENERATE_WITH_TEMPLATE.format(
                system_template=template_ref, requirements=requirements,
                field_schema_block=field_block, retry_hint=retry_hint,
            )
        else:
            meta_prompt = META_PROMPT_GENERATE.format(
                requirements=requirements,
                field_schema_block=field_block, retry_hint=retry_hint,
            )
        response = helper_llm(meta_prompt)

        if response is None:
            raise RuntimeError("Helper 模型未返回有效响应，请检查模型配置。")

        template = _extract_template_block(response)
        allowed_for_normalize = {
            f["name"] for f in (field_schema or {}).get("input_fields", [])
        }
        template = normalize_placeholders_to_double_braces(template, allowed_for_normalize)
        last_template = template

        ok, illegal = verify_placeholders_against_schema(template, field_schema)
        if ok:
            return template

        last_illegal = illegal
        print(
            f"  [重试 {attempt + 1}/{max_retries}] 生成的 prompt 含字段白名单外的占位符: "
            f"{illegal}；将提示模型修正后重新生成。"
        )
        allowed_names = ", ".join(f"`{f['name']}`" for f in (field_schema or {}).get("input_fields", []))
        retry_hint = (
            "# 重试警示（上一轮失败原因）\n"
            f"上一轮模板出现了**白名单外的占位符**: {illegal}。\n"
            f"必须**只使用**白名单字段（{allowed_names}）作为 `{{{{.name}}}}` / `{{{{.field.path}}}}` 上线占位符；如该字段确无可用白名单字段，"
            "请把对应内容改写为纯文本叙述，不要造新字段。\n\n"
        )

    if field_schema and last_illegal:
        allowed_names = ", ".join(
            f["name"] for f in (field_schema or {}).get("input_fields", [])
        ) or "（Context 未定义任何输入字段）"
        raise RuntimeError(
            "生成的 Prompt 仍包含 Context 外占位符，已拒绝使用。"
            f"\n非法占位符: {last_illegal}"
            f"\n允许字段: {allowed_names}"
        )

    # 无字段白名单时保留旧行为，把最近一次结果交回让上层兜底。
    print(
        f"  [警告] 重试 {max_retries} 次仍存在非法占位符 {last_illegal}，"
        "已交由人工处理。"
    )
    return last_template


def _extract_template_block(response: str) -> str:
    """从模型响应中抽取 ```template ... ``` / ``` ... ``` 内容，兜底返回去首尾空响应。"""
    match = re.search(r"```template\s*(.*?)\s*```", response, re.S)
    if match:
        return match.group(1)
    match = re.search(r"```\s*(.*?)\s*```", response, re.S)
    if match:
        content = match.group(1)
        if not content.strip().startswith(("import ", "def ", "class ")):
            return content
    return response.strip()


_PLACEHOLDER_NAME_RE = r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"


def normalize_placeholders_to_double_braces(prompt_template: str, allowed_fields: set = None) -> str:
    """Normalize placeholders to production Go-template syntax: {{.field}} / {{.field.path}}."""
    allowed_fields = set(allowed_fields or [])

    def replace_go(match):
        name = match.group(1)
        if allowed_fields and name not in allowed_fields:
            return match.group(0)
        return "{{." + name + "}}"

    def replace(match):
        name = match.group(1)
        if allowed_fields and name not in allowed_fields:
            return match.group(0)
        return "{{." + name + "}}"

    prompt_template = re.sub(
        r"\{\{\s*\.(" + _PLACEHOLDER_NAME_RE + r")\s*\}\}",
        replace_go,
        prompt_template or "",
    )
    prompt_template = re.sub(
        r"\{\{\s*(" + _PLACEHOLDER_NAME_RE + r")\s*\}\}",
        replace,
        prompt_template,
    )
    return re.sub(
        r"(?<!\{)\{(" + _PLACEHOLDER_NAME_RE + r")\}(?!\})",
        replace,
        prompt_template,
    )


def extract_placeholders(prompt_template: str) -> list:
    """
    从 prompt 模板中提取字段占位符名称。
    新规范使用 {{.name}} / {{.field.path}}；为兼容旧版本，也识别 {{name}} 和单花括号 {name}。

    返回:
        list: 占位符名称列表（去重）
    """
    matches = re.findall(r"\{\{\s*\.?(" + _PLACEHOLDER_NAME_RE + r")\s*\}\}", prompt_template or "")

    # 兼容旧的 {name}，但避免把 JSON 对象或双括号内部内容误判成占位符。
    temp = re.sub(r"\{\{.*?\}\}", "", prompt_template or "", flags=re.S)
    matches.extend(re.findall(r"(?<!\{)\{(" + _PLACEHOLDER_NAME_RE + r")\}(?!\})", temp))

    # 去重并保持顺序
    seen = set()
    result = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def _lookup_value(values: dict, name: str):
    if name in values:
        return True, values[name]
    current = values
    for part in name.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return False, None
    return True, current


def render_prompt_template(prompt_template: str, values: dict) -> str:
    """
    Render prompt placeholders using the system field syntax.
    Preferred syntax: {{.field_name}} / {{.field.path}}. Legacy {{field}} and {field} are supported.
    """
    values = values or {}
    missing = []

    def replace_double(match):
        name = match.group(1).strip()
        found, value = _lookup_value(values, name)
        if not found:
            missing.append(name)
            return match.group(0)
        return str(value)

    rendered = re.sub(
        r"\{\{\s*\.?(" + _PLACEHOLDER_NAME_RE + r")\s*\}\}",
        replace_double,
        prompt_template or "",
    )

    def replace_single(match):
        name = match.group(1)
        found, value = _lookup_value(values, name)
        if not found:
            missing.append(name)
            return match.group(0)
        return str(value)

    rendered = re.sub(
        r"(?<!\{)\{(" + _PLACEHOLDER_NAME_RE + r")\}(?!\})",
        replace_single,
        rendered,
    )

    if missing:
        unique_missing = []
        for name in missing:
            if name not in unique_missing:
                unique_missing.append(name)
        raise KeyError(tuple(unique_missing))

    return rendered


# ─── OUTPUT Schema 推导与注入 ────────────────────────────────────────────────


def _type_label(value) -> str:
    """返回字段的类型标签，bool 必须先于 int 判断。"""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _summarize_value(value, max_len: int = 60) -> str:
    """生成简短示例文本，避免长字段把表格撑爆。"""
    if isinstance(value, str):
        text = value.replace("\n", " ").replace("|", "\\|")
        if len(text) > max_len:
            text = text[:max_len] + "…"
        return f'"{text}"'
    text = json.dumps(value, ensure_ascii=False)
    text = text.replace("|", "\\|")
    if len(text) > max_len:
        text = text[:max_len] + "…"
    return text


def _derive_output_schema_block(eval_data: list) -> str:
    """
    根据 eval_data[0..]["output"] 推断字段集合 + 类型，并构造一份强约束 schema 区块。
    返回的整块文本中所有花括号都已双写转义，可直接拼回 prompt 模板再 .format()。
    """
    fields = {}  # name -> {"types": set, "examples": list}
    for sample in eval_data:
        if not isinstance(sample, dict):
            continue
        out = sample.get("output")
        if not isinstance(out, dict):
            continue
        for k, v in out.items():
            info = fields.setdefault(k, {"types": set(), "examples": []})
            info["types"].add(_type_label(v))
            if len(info["examples"]) < 3 and v is not None:
                info["examples"].append(v)

    if not fields:
        return ""

    rows = []
    for name, info in fields.items():
        type_str = " \\| ".join(sorted(info["types"]))
        if info["examples"]:
            example_text = _summarize_value(info["examples"][0])
        else:
            example_text = "null"
        rows.append(f"| `{name}` | {type_str} | {example_text} |")
    table = "| 字段名 | 类型 | 示例 |\n|---|---|---|\n" + "\n".join(rows)

    # 真实样本 JSON（取第一条带合法 output 的样本），用于展示完整结构
    sample_output = next(
        (s["output"] for s in eval_data
         if isinstance(s, dict) and isinstance(s.get("output"), dict)),
        None,
    )
    sample_json = json.dumps(sample_output, ensure_ascii=False, indent=2)

    field_list = ", ".join(f"`{n}`" for n in fields)

    # 先用单层花括号构建整块 markdown，最后统一双写转义，避免 .format() 把 JSON 当占位符。
    block_raw = (
        "## 强制输出 Schema（必须严格遵守，否则将判错）\n\n"
        "你的输出必须是合法的 JSON 对象，**严格使用且只使用以下字段**"
        "（不得新增、改名、拆分或合并）：\n\n"
        f"{table}\n\n"
        f"必须包含的字段集合: {field_list}。\n"
        "如某字段当前样本不适用，按字段类型给出空值（string→\"\"，object→null，"
        "array→[]，boolean→false 视具体定义而定），但**不得省略字段**。\n\n"
        "### 输出 JSON 参考结构（仅用于对照字段名与层级，**不要照搬内容**）\n\n"
        "```json\n"
        f"{sample_json}\n"
        "```"
    )
    block_escaped = block_raw.replace("{", "{{").replace("}", "}}")

    # 包裹标记不需要转义（不含 {}）
    return f"{_AUTO_SCHEMA_BEGIN}\n{block_escaped}\n{_AUTO_SCHEMA_END}"


def strip_auto_output_schema(prompt_template: str) -> str:
    """Remove the evaluation-only auto output schema block from a prompt."""
    text = prompt_template or ""
    cleaned = _AUTO_SCHEMA_RE.sub("", text)
    if _AUTO_SCHEMA_BEGIN in cleaned:
        cleaned = cleaned[:cleaned.find(_AUTO_SCHEMA_BEGIN)]
    return cleaned + ("\n" if cleaned else "")


def augment_prompt_with_output_schema(prompt_template: str,
                                      eval_data: list,
                                      template_mode: str = "structural") -> str:
    """
    在 prompt 末尾追加（或幂等替换）显式 OUTPUT Schema 区块。

    - 从 eval_data 推断字段清单与类型；
    - 替换或追加形如 <!-- AUTO_OUTPUT_SCHEMA_START --> ... <!-- ..._END --> 的区块；
    - 如果 eval_data 为空或没有合法 output 字段，原样返回 prompt_template。
    - template_mode == "strict" 时：跳过注入，但仍会**剥掉**历史遗留的 AUTO_OUTPUT_SCHEMA 区块。
    """
    if template_mode == "strict":
        return strip_auto_output_schema(prompt_template)

    if not eval_data:
        return prompt_template

    schema_block = _derive_output_schema_block(eval_data)
    if not schema_block:
        return prompt_template

    cleaned = strip_auto_output_schema(prompt_template).rstrip()
    return cleaned + "\n\n" + schema_block + "\n"

