# system_info/ — 系统预设 Prompt 模板规范

`system_info/` 下放置的文件会被流水线在 Step 2 之后整体读入，作为生成 prompt 的「参考模板」。

## 两种模板模式

启动 `main.py` 时检测到 `system_info/` 非空，会询问：

| 选项 | 含义 | 何时用 |
|---|---|---|
| **1. 结构占位参考**（structural，默认） | 仅参考模板里的分节命名（ROLE / CONTEXT / TASK / GENERATION RULES / RESTRICTIONS / OUTPUT REQUIREMENTS），**OUTPUT 段会被系统自动注入 JSON Schema 块** | 后端期望模型输出 JSON 结构化结果；评测走结构比对为主，LLM judge 兜底 |
| **2. 严格沿用模板格式**（strict） | 完全沿用模板自带的输出形态，**不注入 JSON Schema 块**，并幂等剥离历史遗留的 `<!-- AUTO_OUTPUT_SCHEMA_START -->` 区块 | 后端期望模型输出**纯文本**（例如 voice script）；评测主要依赖 LLM judge，结构层会因 `all_skipped` 不计入 |

## 重要：模板与评测的契合性

历史上有一次回归：模板写的是 "Return ONLY the spoken text"（纯文本），但流水线**无条件**追加 JSON Schema 块，两段指令互斥导致生成出来的 prompt 输出格式漂移。修复后的行为：

- structural 模式 + 纯文本模板 → 仍会注入 JSON Schema，与模板冲突。**不要这么搭配**。
- strict 模式 + JSON 模板 → schema 注入被跳过，OUTPUT 字段定义只能依赖你模板里自己写的那一段，**务必写完整**。
- 纯文本模板请走 strict 模式；JSON 输出模板请走 structural 模式（或自己在模板里写好完整 Schema 后用 strict）。

## 模板写作规范

- **分节命名保持一致**：使用 `## ROLE` / `## CONTEXT` / `## TASK` / `## GENERATION RULES` / `## RESTRICTIONS` / `## OUTPUT REQUIREMENTS` 六段式。
- **占位符**：用 `{{variable_name}}`（双花括号）作为示例，真实生成的模板里会变成 `.format()` 的单花括号占位符。
- **OUTPUT REQUIREMENTS**：
  - 走 structural：可以只写"输出 JSON"，schema 由系统补全。
  - 走 strict：必须自己写出完整的字段表、字段类型、字段含义、JSON 示例（包含合法的样例值）；否则模型输出会变成自由发挥。
- **禁止字段编造**：模板里出现的所有占位符 name 必须能在已确认字段表中找到（流水线 Step 2 会强制校验，不通过会重试最多 3 次）。

## 文件支持

`read_system_info` 会按文件名排序读取 `system_info/` 下所有支持格式的文件（`.txt` / `.md` / `.py` / `.json` / `.docx` 等），整体拼接作为参考模板。如果有多个文件，它们会被依次拼接。
