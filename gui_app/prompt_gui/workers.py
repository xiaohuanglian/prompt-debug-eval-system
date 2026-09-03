"""Background workers for long-running async operations."""

import os
import sys
import json
import traceback
from PyQt5.QtCore import QThread, pyqtSignal

from ._project_paths import PROJECT_ROOT  # noqa: F401

from code.pipeline.model_resolver import list_available_models, load_model
from code.pipeline.prompt_generator import (
    generate_prompt_template,
    extract_placeholders,
    normalize_placeholders_to_double_braces,
    verify_placeholders_against_schema,
)
from code.pipeline.eval_data_generator import generate_eval_data_auto, generate_eval_data_from_seeds
from code.pipeline.eval_code_generator import generate_eval_script
from code.pipeline.eval_runner import run_evaluation
from code.pipeline.optimizer import analyze_errors, suggest_improvements
from code.pipeline.version_manager import VersionManager


def _require_callable(fn, label: str):
    if not callable(fn):
        raise RuntimeError(f"{label} 未加载或不可调用，请先回到 Step 1 选择并确认模型。")


class RawDocsAnalyzeWorker(QThread):
    """Background worker for LLM auto-analysis of documents — merges manual input + PRD docs."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, helper_llm, scenario_folder, docs_content, manual_input=""):
        super().__init__()
        self.helper_llm = helper_llm
        self.scenario_folder = scenario_folder
        self.docs_content = docs_content
        self.manual_input = manual_input

    def run(self):
        try:
            _require_callable(self.helper_llm, "Helper 模型")
            self.progress.emit("正在调用 LLM 综合分析手动需求与 PRD 文档...")
            meta_prompt = f"""你是一个专业的需求分析工程师。你的任务是将「手动输入的需求」与「PRD 文档内容」合并为一份完整、结构化、无冗余的最终需求描述。

场景文件夹: {self.scenario_folder}

# 手动输入的需求
{self.manual_input}

# PRD 文档内容
{self.docs_content}

# 任务要求
请综合上述「手动输入的需求」和「PRD 文档内容」，输出一份合并后的结构化需求描述，包含以下内容：
1. **任务目标** - 这个 prompt 要完成什么任务？
2. **输入字段** - 所有输入字段的名称、类型和说明
3. **输出格式** - 预期的输出字段和 JSON 格式
4. **规则与约束** - 需要遵守的规则和限制

# 合并原则
1. 以手动输入的需求为核心骨架，PRD 文档内容为补充和丰富
2. 消除两者之间的重复和矛盾内容
3. PRD 文档中与手动需求无关的内容可以省略
4. 输出应为一份连贯、自包含的需求文档，不标注哪部分来自手动、哪部分来自 PRD

请用中文输出结构化的需求描述，直接输出需求内容，不需要额外解释。"""
            response = self.helper_llm(meta_prompt)
            if response is None:
                self.error.emit("LLM 未返回有效响应，请检查模型配置。")
                return
            self.finished.emit(response.strip())
        except Exception as e:
            self.error.emit(f"分析失败: {e}")


class ListModelsWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            models = list_available_models()
            self.finished.emit(models)
        except Exception as e:
            self.error.emit(str(e))


class GeneratePromptWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, helper_llm, requirements, template_ref=None, field_schema=None):
        super().__init__()
        self.helper_llm = helper_llm
        self.requirements = requirements
        self.template_ref = template_ref
        self.field_schema = field_schema

    def run(self):
        try:
            _require_callable(self.helper_llm, "Helper 模型")
            prompt = generate_prompt_template(
                self.helper_llm, self.requirements, self.template_ref,
                field_schema=self.field_schema,
            )
            self.finished.emit(prompt)
        except Exception as e:
            self.error.emit(f"{traceback.format_exc()}\n\nError: {e}")


class ContinuePromptOptimizeWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, helper_llm, scenario_name, current_prompt, requirements,
                 manual_suggestions, template_ref=None, field_schema=None):
        super().__init__()
        self.helper_llm = helper_llm
        self.scenario_name = scenario_name
        self.current_prompt = current_prompt
        self.requirements = requirements
        self.manual_suggestions = manual_suggestions
        self.template_ref = template_ref
        self.field_schema = field_schema

    def run(self):
        try:
            _require_callable(self.helper_llm, "Helper 模型")
            self.progress.emit("正在调用 Helper 模型生成候选 Prompt...")
            merged_requirements = f"""请基于以下信息生成一个新版 Prompt。

# 场景
{self.scenario_name}

# 原始/当前 Prompt
{self.current_prompt}

# 已有需求上下文
{self.requirements}

# 用户本次修改意见（必须优先满足）
{self.manual_suggestions}

# 生成要求
1. 生成完整可用的新 Prompt，不要只输出差异。
2. 以“原始/当前 Prompt”为锚点，只做满足本次修改意见所需的最小必要变更。
3. 未被本次修改意见点名的角色、输入字段、输出字段、输出结构、业务规则和限制条件必须保留，不要重写、删减或替换。
4. 保持 Context 字段白名单内的占位符，不要编造新占位符。
5. 不要把其他场景的分类、分支、输出字段或评测规则带入当前 Prompt；只有当前 Prompt 或本次修改意见明确要求时才允许新增。
6. 如果提供了参考模板，必须遵循参考模板的结构和分节风格。
7. OUTPUT REQUIREMENTS 必须包含完整字段定义表和 JSON 示例。
"""
            prompt = generate_prompt_template(
                self.helper_llm, merged_requirements, self.template_ref,
                field_schema=self.field_schema,
            )
            self.finished.emit(prompt)
        except Exception as e:
            self.error.emit(f"{traceback.format_exc()}\n\nError: {e}")


class GenerateEvalDataAutoWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, helper_llm, prompt_template, requirements):
        super().__init__()
        self.helper_llm = helper_llm
        self.prompt_template = prompt_template
        self.requirements = requirements

    def run(self):
        try:
            _require_callable(self.helper_llm, "Helper 模型")
            self.progress.emit("正在生成评测数据...")
            data = generate_eval_data_auto(self.helper_llm, self.prompt_template, self.requirements)
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class GenerateEvalDataSeedWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, helper_llm, prompt_template, requirements, seeds_json):
        super().__init__()
        self.helper_llm = helper_llm
        self.prompt_template = prompt_template
        self.requirements = requirements
        self.seeds_json = seeds_json

    def run(self):
        try:
            _require_callable(self.helper_llm, "Helper 模型")
            self.progress.emit("正在扩充评测数据...")
            data = generate_eval_data_from_seeds(
                self.helper_llm, self.prompt_template, self.requirements, self.seeds_json
            )
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class RunEvalWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    sample_done = pyqtSignal(int, int)

    def __init__(self, target_llm, prompt_template, eval_data,
                 scenario_name, version, result_path, max_workers,
                 helper_llm=None, use_llm_judge=False):
        super().__init__()
        self.target_llm = target_llm
        self.prompt_template = prompt_template
        self.eval_data = eval_data
        self.scenario_name = scenario_name
        self.version = version
        self.result_path = result_path
        self.max_workers = max_workers
        self.helper_llm = helper_llm
        self.use_llm_judge = use_llm_judge
        self.cancelled = False

    def run(self):
        import io
        import contextlib

        try:
            _require_callable(self.target_llm, "Target 模型")
            self.progress.emit(f"开始评测 (共 {len(self.eval_data)} 个样本, 并发数: {self.max_workers})...")

            def on_progress(done, total):
                self.sample_done.emit(done, total)

            def on_stop():
                return self.cancelled

            # Capture stdout from eval_runner (contains per-sample errors)
            stdout_capture = io.StringIO()
            with contextlib.redirect_stdout(stdout_capture):
                results = run_evaluation(
                    self.target_llm, self.prompt_template, self.eval_data,
                    self.scenario_name, self.version, self.result_path,
                    self.max_workers,
                    helper_llm=self.helper_llm,
                    use_llm_judge=self.use_llm_judge,
                    progress_callback=on_progress,
                    stop_flag=on_stop,
                )

            # Emit captured output as progress
            captured = stdout_capture.getvalue()
            for line in captured.split("\n"):
                line = line.strip()
                if line:
                    self.progress.emit(line)

            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))
            traceback.print_exc()


class AnalyzeErrorsWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, results, eval_data):
        super().__init__()
        self.results = results
        self.eval_data = eval_data

    def run(self):
        try:
            analysis = analyze_errors(self.results, self.eval_data)
            self.finished.emit(analysis)
        except Exception as e:
            self.error.emit(str(e))


class SuggestImprovementsWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, helper_llm, prompt_template, error_analysis):
        super().__init__()
        self.helper_llm = helper_llm
        self.prompt_template = prompt_template
        self.error_analysis = error_analysis

    def run(self):
        try:
            _require_callable(self.helper_llm, "Helper 模型")
            suggestions = suggest_improvements(
                self.helper_llm, self.prompt_template, self.error_analysis
            )
            self.finished.emit(suggestions)
        except Exception as e:
            self.error.emit(str(e))


# ─── LLM Auto-Optimize Worker ────────────────────────────────────────

_META_AUTO_OPTIMIZE = """你是一个Prompt优化专家。请根据以下当前Prompt模板、评测错误分析和优化建议，生成一个改进后的新Prompt模板。

# 当前Prompt模板
{current_prompt}

# 评测错误分析
{error_analysis}

# 优化建议
{suggestions}

# 绝对不可违反的规则
1. 【占位符红线】原模板中的所有双括号字段占位符（例如 {{{{today_training_focus}}}}）必须原样保留，不得移除、不得添加引号、不得替换为枚举值。
   ✅ 正确的做法: today_training_focus: {{{{today_training_focus}}}} 表示今日训练焦点
   ❌ 错误的做法: today_training_focus: 今日训练焦点（删除占位符）
   ❌ 错误的做法: today_training_focus: {{{{"today_training_focus"}}}}（加引号）

2. 【JSON示例】OUTPUT REQUIREMENTS 中如果包含 JSON 示例，使用普通 JSON 花括号即可。
   ✅ 正确的做法（JSON 示例）: {{ "field": "value" }}
   ❌ 错误的做法（把 JSON 字段当占位符）: {{{{field}}}}
   只有真实输入字段才使用 {{{{field_name}}}}。

3. 【修复原则】针对错误分析中指出的根因，逐一修复对应的问题。严格遵循优化建议中的具体改进方案，但以「手动优化建议」为准。

4. 【结构一致】保持原模板的整体板块结构（ROLE / CONTEXT / TASK / GENERATION RULES / RESTRICTIONS / OUTPUT REQUIREMENTS 等）。

5. 【输出格式完整】OUTPUT REQUIREMENTS 必须给出完整字段定义表和 JSON 示例。

6. 【避免过约束】不要为了修复一个问题而引入新的歧义或过度约束。

# 优化建议优先顺序
手动优化建议（Manual Suggestions）> LLM 优化建议（LLM Suggestions）
当两者冲突时，以手动优化建议为准。

# 输出格式
直接输出改进后的Prompt模板，用```template```包裹：
```template
...你的模板内容...
```"""

_META_AUTO_OPTIMIZE = """你是一个 Prompt 优化专家。请根据当前 Prompt、评测错误分析和优化建议，生成一个改进后的新 Prompt 模板。

# 当前 Prompt
{current_prompt}

# 评测错误分析
{error_analysis}

# 优化建议
{suggestions}

# 必须遵守
1. 保持生产部署格式，所有输入变量只能写成 Go template 占位符：{{{{.field_name}}}} 或 {{{{.field.path}}}}。
2. 不要生成 {{{{field_name}}}} 或 {{field_name}} 这种省略前导点的中间格式。
3. 不要新增、猜测或恢复未在字段白名单中的 Context 字段。
4. JSON 示例里的普通花括号不是占位符，只有真实输入字段才使用 Go template 占位符。

# 输出格式
直接输出改进后的 Prompt 模板，用 ```template``` 包裹。
"""


class AutoOptimizeWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, helper_llm, prompt_template, error_details, suggestions,
                 field_schema=None):
        super().__init__()
        self.helper_llm = helper_llm
        self.prompt_template = prompt_template
        self.error_details = error_details
        self.suggestions = suggestions
        self.field_schema = field_schema or {}

    def run(self):
        try:
            _require_callable(self.helper_llm, "Helper 模型")
            allowed_fields = [
                f.get("name") for f in (self.field_schema.get("input_fields") or [])
                if f.get("name")
            ]
            field_guard = ""
            if allowed_fields:
                field_guard = (
                    "\n\n# Context 字段白名单（必须严格遵守）\n"
                    "新版 Prompt 中只能使用以下已勾选字段作为 {{field_name}} 占位符：\n"
                    + ", ".join(f"`{name}`" for name in allowed_fields)
                    + "\n不要新增、猜测或恢复任何未列出的 Context 字段。"
                )
                field_guard = (
                    "\n\n# Context 字段白名单（必须严格遵守）\n"
                    "新版 Prompt 中只能使用以下已勾选字段作为 {{.field_name}} / {{.field.path}} 上线占位符：\n"
                    + ", ".join(f"`{name}`" for name in allowed_fields)
                    + "\n不要新增、猜测或恢复任何未列出的 Context 字段；不要省略 Go template 前导点。"
                )
            meta_prompt = _META_AUTO_OPTIMIZE.format(
                current_prompt=self.prompt_template,
                error_analysis=self.error_details,
                suggestions=self.suggestions + field_guard,
            )
            response = self.helper_llm(meta_prompt)
            if response is None:
                self.error.emit("Helper 模型未返回有效响应。")
                return
            # Extract template block
            import re
            match = re.search(r"```template\s*(.*?)\s*```", response, re.S)
            if match:
                result = match.group(1).strip()
            else:
                match = re.search(r"```\s*(.*?)\s*```", response, re.S)
                if match:
                    content = match.group(1)
                    if not content.strip().startswith(("import ", "def ", "class ")):
                        result = content.strip()
                    else:
                        result = response.strip()
                else:
                    result = response.strip()

            allowed = set(allowed_fields)
            result = normalize_placeholders_to_double_braces(result, allowed)
            ok, illegal = verify_placeholders_against_schema(result, self.field_schema)
            if not ok:
                self.error.emit(
                    "LLM 优化结果包含未勾选 Context 字段: " + ", ".join(illegal)
                )
                return
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ─── Template Conversion Utility ──────────────────────────────────────────

_PYTHON_TO_GO_CONVERSION_PROMPT = """你是一个模板语法转换专家。请将以下双括号字段模板转换为 Go 模板语法。

# 转换规则

## 变量占位符
- 系统字段占位符 `{{{{variable_name}}}}` → Go `{{{{.variable_name}}}}`
- 变量名仅包含字母、数字、下划线

## JSON 示例中的花括号
- JSON 示例里的普通 `{{` 和 `}}` 保持不变
- 只有形如 `{{{{field_name}}}}` 的字段占位符需要转换为 Go 模板变量

## 特殊情况
- 已经符合 `{{{{.var}}}}` 格式的内容保持不变
- 不要修改模板中非占位符的文本内容

# 输入（双括号字段模板）
{input_template}

# 输出格式
直接输出转换后的 Go 模板，用 ```gotemplate ``` 包裹："""


def convert_python_to_go_template(python_template: str) -> str:
    """Convert system double-brace template syntax to Go template syntax.

    Pure-python fallback for simple cases. For complex templates the LLM
    worker (ConvertTemplateWorker) should be used instead.
    """
    import re

    name_re = r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*'
    go_tpl = re.sub(r'\{\{\s*(' + name_re + r')\s*\}\}', r'{{.\1}}', python_template)
    # Legacy fallback for older single-brace templates.
    go_tpl = re.sub(r'(?<!\{)\{(' + name_re + r')\}(?!\})', r'{{.\1}}', go_tpl)
    return go_tpl


# ─── Deploy / LLM Gateway Workers ───────────────────────────────────────

class ConvertTemplateWorker(QThread):
    """Use helper LLM to convert system template to Go template."""
    finished = pyqtSignal(str, str)  # go_template, original_python
    error = pyqtSignal(str)

    def __init__(self, helper_llm, python_template):
        super().__init__()
        self.helper_llm = helper_llm
        self.python_template = python_template

    def run(self):
        try:
            _require_callable(self.helper_llm, "Helper 模型")
            meta_prompt = _PYTHON_TO_GO_CONVERSION_PROMPT.format(
                input_template=self.python_template
            )
            response = self.helper_llm(meta_prompt)
            if response is None:
                self.error.emit("Helper 模型未返回有效响应。")
                return

            import re
            # Try gotemplate codeblock first
            match = re.search(r"```gotemplate\s*(.*?)\s*```", response, re.S)
            if match:
                result = match.group(1).strip()
            else:
                # Fallback: any codeblock
                match = re.search(r"```\s*(.*?)\s*```", response, re.S)
                if match:
                    result = match.group(1).strip()
                else:
                    result = response.strip()

            # Remove leading/trailing quotes if LLM wrapped the template
            result = result.strip("'\"")
            result = convert_python_to_go_template(result)

            self.finished.emit(result, self.python_template)
        except Exception as e:
            self.error.emit(str(e))


class GatewayValidateWorker(QThread):
    """Validate a Go template against the LLM gateway template-validate API."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, base_url, api_key, template_content, expected_vars=None):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.template_content = template_content
        self.expected_vars = expected_vars or []

    def run(self):
        try:
            from urllib import request, error

            payload = {
                "template_content": self.template_content,
                "expected_vars": self.expected_vars,
            }
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = request.Request(
                url=f"{self.base_url}/api/v1/template/validate",
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            try:
                with request.urlopen(req, timeout=30) as resp:
                    raw = resp.read()
                    data = json.loads(raw.decode("utf-8")) if raw else {}
                    data["_http_status"] = resp.status
                    data["_success"] = True
            except error.HTTPError as exc:
                raw = exc.read()
                try:
                    data = json.loads(raw.decode("utf-8")) if raw else {}
                except json.JSONDecodeError:
                    data = {"raw": raw.decode("utf-8", errors="replace")}
                data["_http_status"] = exc.code
                data["_success"] = False

            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class GatewayDeployWorker(QThread):
    """Create or update a template on the LLM gateway."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, base_url, api_key, namespace, name, content,
                 description="", is_active=True, template_id=None):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.namespace = namespace
        self.name = name
        self.content = content
        self.description = description
        self.is_active = is_active
        self.template_id = template_id  # None = create, str = update

    def run(self):
        try:
            from urllib import request, error

            if self.template_id:
                # Update existing template
                payload = {
                    "namespace": self.namespace,
                    "template_id": self.template_id,
                    "name": self.name,
                    "content": self.content,
                    "description": self.description,
                    "is_active": self.is_active,
                    "is_active_set": True,
                }
                path = "/api/v1/template/update"
            else:
                # Create new template
                payload = {
                    "namespace": self.namespace,
                    "name": self.name,
                    "content": self.content,
                    "description": self.description,
                    "is_active": self.is_active,
                }
                path = "/api/v1/template/create"

            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = request.Request(
                url=f"{self.base_url}{path}",
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            try:
                with request.urlopen(req, timeout=30) as resp:
                    raw = resp.read()
                    data = json.loads(raw.decode("utf-8")) if raw else {}
                    data["_http_status"] = resp.status
                    data["_success"] = True
            except error.HTTPError as exc:
                raw = exc.read()
                try:
                    data = json.loads(raw.decode("utf-8")) if raw else {}
                except json.JSONDecodeError:
                    data = {"raw": raw.decode("utf-8", errors="replace")}
                data["_http_status"] = exc.code
                data["_success"] = False

            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))
