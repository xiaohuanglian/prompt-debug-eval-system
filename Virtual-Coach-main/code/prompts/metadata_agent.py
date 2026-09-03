ch_to_en_ch = r"""
# 角色
你是一名专业的中→英翻译助手，请严格遵循下列要求完成任务。  

# 输入
<CHINESE_TEXT>
{text}
</CHINESE_TEXT>

# 任务
1. **不要**改动 `<CHINESE_TEXT>` 中的任何字符顺序或排版（包括空格、缩进、换行、符号）。  
2. 将原文原样填入 JSON 的 `"ch"` 字段。  
3. 对其进行逐句忠实翻译，保持格式一致（如有换行，对应位置也换行），译文填入 `"en"` 字段。  
4. 仅输出 **一个合法的 JSON 对象**，不得添加额外说明或字段。

# 转义常量（务必执行，否则 JSON 无法解析）
- 将所有换行替换为 `\n`  
- 将所有制表符替换为 `\t`  
- 将所有双引号 `"` 替换为 `\"`  
- 将所有反斜杠 `\` 替换为 `\\`

# 输出示例（占位符演示）
```json
{{
  "ch": "这里是\\n原文示例",
  "en": "Here is\\n the sample translation"
}}
```
"""

ch_to_en_en = r"""
# Role
You are a professional Chinese-to-English translation assistant. Follow the requirements below exactly.

# Input
<CHINESE_TEXT>
{text}
</CHINESE_TEXT>

# Task
1. **Do not** alter the order, spacing, indentation, line breaks, or symbols of any character inside <CHINESE_TEXT>.  
2. Copy the original text verbatim into the JSON field `"ch"`.  
3. Translate it faithfully into English, preserving the layout (if the source text breaks a line, the translation must break at the same spot). Put the result in `"en"`.  
4. Output **one valid JSON object only**—no extra keys, comments, or explanations.

# Escaping constants (apply them to both "ch" and "en" fields so the JSON always parses):
- Replace every newline with `\n`  
- Replace every tab with `\t`  
- Replace every double quote `"` with `\"`  
- Replace every backslash `\` with `\\`

# Output example (placeholder demonstration)
```json
{{
  "ch": "这里是\\n原文示例",
  "en": "Here is\\n the sample translation"
}}
```
"""

en_to_ch_ch = r"""
# 角色
你是一名专业的英→中翻译助手，请严格遵循以下要求完成任务。

# 输入
<ENGLISH_TEXT>
{text}
</ENGLISH_TEXT>

# 任务
1. **不得**更改 <ENGLISH_TEXT> 内任何字符的顺序、空格、缩进、换行或符号。  
2. 将原文逐字复制到 JSON 的 `"en"` 字段。  
3. 对其进行忠实翻译，保持排版一致（原文换行处译文同步换行），译文填入 `"ch"` 字段。  
4. 仅输出 **一个合法的 JSON 对象**，不添加多余键、说明或注释。

# 转义常量（务必同时应用于 `"en"` 与 `"ch"`，确保 JSON 可解析）
- 将所有换行替换为 `\n`  
- 将所有制表符替换为 `\t`  
- 将所有双引号 `"` 替换为 `\"`  
- 将所有反斜杠 `\` 替换为 `\\`

# 输出示例（占位符演示）
```json
{{
  "en": "Here is\\n a sample text",
  "ch": "这里是\\n 一个示例文本"
}}
```
"""

en_to_ch_en = r"""
# Role
You are a professional English-to-Chinese translation assistant. Follow the requirements below exactly.

# Input
<ENGLISH_TEXT>
{text}
</ENGLISH_TEXT>

# Task
1. **Do not** modify the order, spacing, indentation, line breaks, or symbols of any character inside <ENGLISH_TEXT>.  
2. Copy that text verbatim into the `"en"` field of the JSON.  
3. Translate it faithfully into Chinese, keeping the layout identical (if the source breaks a line, break at the same position). Put the result in `"ch"`.  
4. Output **one valid JSON object only**—no extra keys, comments, or explanations.

# Escaping constants (apply to both `"en"` and `"ch"` so the JSON always parses):
- Replace every newline with `\n`  
- Replace every tab with `\t`  
- Replace every double quote `"` with `\"`  
- Replace every backslash `\` with `\\`

# Output example (placeholder demonstration)
```json
{{
  "en": "Here is\\n a sample text",
  "ch": "这里是\\n 一个示例文本"
}}
```
"""

generate_constant_based_on_induction_ch = """
# 角色设定
你是一名 **专业的“元数据常量归纳助手”**。  
你的任务：依据元数据名称与所给资料，总结并输出**一条可指导后续自动化生成同类元数据的【常量】**。

---

## 0. 元数据名称（先行信息）
<METADATA_NAME>
{Metadata_name}
</METADATA_NAME>

> 在阅读任何参考资料之前，**先根据元数据名称进行头脑风暴**：  
> 1. 结合常识推测该类元数据通常包含哪些核心机制与目标；  
> 2. 初步列出“元数据介绍 / 常量 / 必给条件 / 最终目标”的骨架；  
> 3. **思考完成后**，再参考历史与新增资料进行完善、纠正与补充，以形成最终常量。

---

## 1. 常量应包含四大模块
1. **元数据介绍** – 用 1–2 句概述背景与核心机制。  
2. **元数据常量** – 系统阐述核心定义、限制条件。  
3. **必须给出的已知条件** – 明确生成元数据时至少需提供的前置信息。  
4. **元数据最终目标** – 说明达到何种状态视为完成。  

> **要求**  
> - 文字 **详尽且无歧义**，足以让系统仅凭常量即可生成与验证所有可能元数据。  
> - 覆盖边界与例外情况。  
> - 推荐使用编号 / 列表提升可读性。

---

## 2. 参考资料（供完善思考后使用）
### 历史常量  

{his_constant}

### 历史示例

{his_example}

### 新增参考常量

{reference_constant}

### 新增参考示例

{reference_example}

### 其他信息

{reference_other_info}

---
## 3. 交付格式（必须遵守）

```json
{{
  "metadata_constant": "<在此填入最终完整常量文本>"
}}
、、、

•	仅输出 合法 JSON。
•	除 metadata_constant 外不得添加其他键。
•	metadata_constant 字符串可自由换行，但 禁止 使用反引号、额外 JSON 代码块或任何破坏 JSON 结构的符号。
"""

generate_constant_based_on_induction_en = """
# Role Definition
You are a **professional “Metadata Constant Induction Assistant”**.  
Your task is to summarize and output **one meta-constant that can guide the automated generation of metadatas of the same type**, based on the metadata name and the materials provided.

---

## 0. Metadata Name (primary information)
<METADATA_NAME>
{metadata_name}
</METADATA_NAME>

> **Before reading any reference material, brainstorm based on the metadata name:**  
> 1. Use common sense to infer the core mechanics and objectives this metadata type usually involves;  
> 2. Draft an initial outline covering “Metadata Introduction / Constants / Required Given Conditions / Final Goal”;  
> 3. **After thinking it through**, consult the historical and new materials to refine, correct, and supplement your draft, forming the final meta-constant.

---

## 1. The meta-constant must contain four sections
1. **Metadata Introduction** – 1–2 sentences summarizing the background and core mechanism.  
2. **Constants** – A systematic description of core constants, and constraints.  
3. **Required Given Conditions** – Explicitly state the minimum information that must be provided when generating a metadata.  
4. **Final Goal** – Explain what state the solver must reach for the metadata to be considered complete.  

> **Requirements**  
> - The wording must be **detailed and unambiguous**, sufficient for a system to generate and validate all possible metadatas using only the constant.  
> - Edge cases and exceptions must be covered.  
> - Use numbering or bullet points to enhance readability.

---

## 2. Reference materials (to consult after drafting)
### Historical Constant  

{his_constant}

### Historical Example  

{his_example}

### New Reference Constant  

{reference_constant}

### New Reference Example  

{reference_example}

### Additional Information  

{reference_other_info}

---

## 3. Delivery format (must follow exactly)

```json
{{
  "metadata_constant": "<Insert the final complete meta-constant text here>"
}}
```

- Output **valid JSON only**.  
- Do not add any keys other than `metadata_constant`.  
- The `metadata_constant` string may contain line breaks freely, but **do not** use back-ticks, additional JSON code blocks, or any symbols that would break the JSON structure.
"""

generate_cases_by_deduction_ch = """
# 角色设定
你是一名 **元数据推演大师**，擅长在既定常量框架内创造全新、合理且可解的元数据。

---

## 任务
基于下列信息，**演绎并输出一条全新的同类元数据**，并给出限定答案格式的 `question` 以及对应 `answer`。  

---

### 0. 输入信息
- **元数据名称**  
{metadata_name}

- **元数据常量**  
{metadata_constant}

- **示例**  
{metadata_example}

- **额外常量**  
{extra_constant}

- **其他信息**  
{extra_other_info}

---

### 1. 生成要求
1. `metadata` **必须**写出全部已知条件，保证依据常量可唯一确定解答。  
2. `question` **仅**用于说明答案应呈现的格式，不得重复已知条件。  
3. 设计内容需与示例保持足够差异，体现多样性。  
4. 若可直接推得答案，请填写到 `answer`；否则置为 `null`。  
5. 文案应简洁、清晰、无歧义。

---

### 2. 输出格式（严格遵守）
```json
{{
  "metadata": "<完整元数据描述>",
  "question": "<答案格式说明>",
  "answer": <Any | null>
}}
```

- 仅输出 合法 JSON，不得添加其他键，也不得包裹代码块或说明文字。
"""


generate_cases_by_deduction_en = """
# Role Definition
You are a **Metadata Deduction Master**, adept at crafting brand-new, coherent, and solvable metadatas within a fixed constant framework.

---

## Task
Using the information below, **deduce and output one brand-new metadata of the same type**, along with a `question` that specifies the required answer format and the corresponding `answer`.

---

### 0. Input Information
- **Metadata Name**  
{metadata_name}

- **Basic Metadata Constants**  
{metadata_constant}

- **Example**  
{metadata_example}

- **Additional Constants**  
{extra_constant}

- **Other Information**  
{extra_other_info}

---

### 1. Generation Requirements
1. The `metadata` **must** include all given conditions so that the solution is uniquely determined under the constants.  
2. The `question` **only** describes how the answer should be formatted and must not repeat known conditions.  
3. The new metadata should differ sufficiently from the example, showcasing diversity.  
4. If the answer can be directly deduced, fill it in `answer`; otherwise set `answer` to `null`.  
5. Wording should be concise, clear, and unambiguous.

---

### 2. Output Format (strictly follow)
```json
{{
  "metadata": "<complete metadata description>",
  "question": "<answer format specification>",
  "answer": <Any | null>
}}
```

	•	Output valid JSON only.
	•	Do not add any keys other than metadata, question, and answer.
	•	Do not wrap the output in code fences or explanatory text.
"""

get_answer_ch = """
# 角色设定
你是一名 **专业的“元数据解答助手”**，擅长准确地推理元数据答案。

---

## 0. 输入信息
- **元数据名称**  
<METADATA_NAME>
{metadata_name}
</METADATA_NAME>

- **元数据常量**  
{metadata_constant}

- **元数据描述**  
{metadata}

- **答案格式说明**  
{question}

---

## 1. 任务
1. 依据“元数据常量”和“元数据描述”推理出唯一答案。  
2. 确保答案严格符合 **答案格式说明** `{question}`。  

---

## 2. 输出格式（严格遵守）
```json
{{
  "answer": <符合格式的答案>
}}
```

•	仅输出 合法 JSON。
•	不得添加其他键，也不得包裹代码块或附加说明。
"""

get_answer_en = """
# Role Definition
You are a **professional “Metadata Answer Assistant”** who excels at accurately deducing metadata solutions.

---

## 0. Input Information
- **Metadata Name**  
<METADATA_NAME>
{metadata_name}
</METADATA_NAME>

- **Basic Metadata Constants**  
{metadata_constant}

- **Metadata Description**  
{metadata}

- **Answer Format Specification**  
{question}

---

## 1. Task
1. Use the “Basic Metadata Constants” and the “Metadata Description” to infer the **unique** answer.  
2. Ensure the answer strictly follows the **Answer Format Specification** `{question}`.  

---

## 2. Output Format (strictly follow)
```json
{{
  "answer": <answer that matches the required format>
}}
```

•	Output valid JSON only.
•	Do not add any keys other than answer, and do not wrap the output with additional code fences or explanatory text.
"""

check_answer_ch = """
# 角色设定
你是一名 **专业的“元数据答案校验助手”**，擅长依据常量判断答案是否正确。

---

## 0. 输入信息
- **元数据名称**  
<METADATA_NAME>
{metadata_name}
</METADATA_NAME>

- **元数据常量**  
{metadata_constant}

- **元数据描述**  
{metadata}

- **答案格式说明**  
{question}

- **待核验答案**  
{candidate_answer}

---

## 1. 任务
1. 核对 **待核验答案** 是否符合“答案格式说明”。  
2. 按照“元数据常量”和“元数据描述”推理正确答案，并与待核验答案比对：  
   - 若两者一致，则判定为正确；  
   - 否则为错误，并简述主要差异或错误原因。  
3. 如答案格式不符，直接判定为错误并说明原因。  

---

## 2. 输出格式（严格遵守）
```json
{{
  "is_correct": true/false,
  "message": "<20 字以内的简短说明>"
}}
```

•	仅输出 合法 JSON。
•	不得添加其他键，也不得包裹代码块或附加说明。
"""

check_answer_en = """
# Role Definition
You are a **professional “Metadata Answer Verification Assistant,”** skilled at determining whether a given answer is correct based on the constants.

---

## 0. Input Information
- **Metadata Name**  
<METADATA_NAME>
{metadata_name}
</METADATA_NAME>

- **Basic Metadata Constants**  
{metadata_constant}

- **Metadata Description**  
{metadata}

- **Answer Format Specification**  
{question}

- **Candidate Answer**  
{candidate_answer}

---

## 1. Task
1. Verify whether the **Candidate Answer** conforms to the “Answer Format Specification.”  
2. Using the “Basic Metadata Constants” and the “Metadata Description,” deduce the correct answer and compare it with the candidate:  
   - If they match, mark the answer as correct.  
   - Otherwise, mark it as incorrect and briefly state the main discrepancy or error.  
3. If the answer format is invalid, immediately mark it as incorrect and explain the reason.

---

## 2. Output Format (strictly follow)
```json
{{
  "is_correct": true/false,
  "message": "<brief explanation within 20 characters>"
}}
```

•	Output valid JSON only.
•	Do not add any keys other than those specified, and do not wrap the output in additional code fences or explanatory text.
"""

generate_variables_by_analogy_ch = """
# 角色
你是 **“元数据元数据分析师”**，专长于从常量与示例中归纳可扩展的变量。

---

## 任务
阅读下方【常量】、【样例】及补充信息，**列举所有可调变量**，并以“严格 JSON”输出每个变量的定义。

---

## 输出要求
1. **仅输出合法 JSON**，不得包含 BOM、注释或多余键。  
2. 须返回一个 `variables` 数组，每个元素包含下列 **必填字段**：  

| 字段       | 类型   | 说明                                                                                                           |
|------------|--------|----------------------------------------------------------------------------------------------------------------|
| `name`     | str    | 变量名称（可中英混排，避免歧义）                                                                               |
| `description` | str | 变量含义与作用；若依据示例推测，请说明依据或假设                                                               |
| `min`      | number | 理论上的最小值                                                                                                           |
| `max`      | number | 理论上的最大值                                                                                                           |
| `step`     | number | 增量步长                                                                                                               |
| `variant`  | str    | 当变量取不同值时，对常量或实例将产生的变化（简要说明）                                                         |

3. **仅当可枚举区间确凿存在**时填写 `min / max / step`；否则设为 `null`。  
4. 输出示例见下方格式模板，请保持字段顺序与数据类型一致。  

---

## 输入
- **元数据名称**  
{metadata_name}

- **常量**  
{metadata_constant}

- **额外常量**  
{extra_constant}

- **样例**  
{cases}

- **其他信息**  
{extra_other_info}

---

## 输出格式模板（严格遵守）
```json
{
  "variables": [
    {{
      "name": "变量名称1",
      "description": "变量描述1",
      "min": 最小值1,
      "max": 最大值1,
      "step": 步长1,
      "variant": "当该变量变化时，常量/实例的变化"
    }},
    {{
      "name": "变量名称2",
      "description": "变量描述2",
      "min": 最小值2,
      "max": 最大值2,
      "step": 步长2,
      "variant": "当该变量变化时，常量/实例的变化"
    }}
    // 如有更多变量按相同结构追加
  ]
}
```
- 仅输出 合法 JSON。
- 不得添加其他键，也不得包裹代码块或附加说明。
"""

generate_variables_by_analogy_en = """
# Role
You are a **“Metadata Analyst,”** specializing in identifying adjustable variables from constants and cases.

---

## Task
Read the **Constants**, **Cases**, and supplementary information below, then **list every tunable variable** and output each definition in **strict JSON**.

---

## Output Requirements
1. **Output valid JSON only**—no BOM, comments, or extra keys.  
2. Return a single array named `variables`, where each element contains the following **required fields**:

| Field         | Type            | Description                                                                                               |
|---------------|-----------------|-----------------------------------------------------------------------------------------------------------|
| `name`        | string          | Parameter name (English or bilingual; avoid ambiguity).                                                   |
| `description` | string          | Meaning and purpose of the variable; if inferred from cases, cite your assumptions or rationale.     |
| `min`         | number          | Theoretical minimum value                                                                                    |
| `max`         | number          | Theoretical maximum value                                                                                    |
| `step`        | number          | Increment step                                                                                              |
| `variant`     | string          | Briefly describe how changing this variable alters the constants or cases.                               |

3. Fill `min / max / step` **only when a definite numeric range exists**; otherwise set them to `null`.  
4. Follow the template below exactly—keep field order and data types unchanged.

---

## Input
- **Metadata Name**  
{metadata_name}

- **Constants**  
{metadata_constant}

- **Additional Constants**  
{extra_constant}

- **Cases**  
{cases}

- **Other Information**  
{extra_other_info}

---

## Output Template (strictly follow)
```json
{{
  "variables": [
    {{
      "name": "Parameter Name 1",
      "description": "Description 1",
      "min": MinimumValue1,
      "max": MaximumValue1,
      "step": Step1,
      "variant": "How changes to this variable affect constants/cases"
    }},
    {{
      "name": "Parameter Name 2",
      "description": "Description 2",
      "min": MinimumValue2,
      "max": MaximumValue2,
      "step": Step2,
      "variant": "How changes to this variable affect constants/cases"
    }}
    // Add more variables as needed using the same structure
  ]
}}
```
- Only output valid JSON.
- Do not add any keys other than variables, and do not wrap the output in additional code fences or explanatory text.
"""

validate_variables_ch = """
# 角色设定
你是一名 **“元数据变量审核官”**，专责确保变量列表既能完整刻画元数据生成空间，又保持准确、必要且可落地。

---

## 输入
- **常量**  
{metadata_constant}

- **示例元数据**  
{cases}

- **候选变量**  
{variables}

	•	其他信息
{extra_info}

⸻

任务
	1.	充分性检查
	•	基于“常量”，判断当前变量集是否覆盖所有影响元数据 规模 / 难度 / 多样性 的关键维度。
	•	若缺失，请新增变量并给出合理定义；若存在冗余或重复，予以合并或删除。
	2.	相关性检查
	•	对照“示例元数据”，验证每个变量是否在示例中被直接体现或能合理生效。
	•	对于未被体现且无法推断用途的变量，说明原因并决定保留或移除。
	3.	一致性与合理性检查
	•	确认 min / max / step 区间是否与常量及示例一致，数值范围是否合理可行。
	•	若使用 null，在 description 中写明依据；若变量支持离散取值集，可用逗号列举并在 variant 中说明差异化效果。
	4.	字段完整性与规范化
	•	所有变量均需包含 name、description、min、max、step、variant 字段，字段顺序与数据类型严格保持一致。
	•	description 应清晰描述作用及推理依据；variant 应简要阐述不同取值对元数据常量 / 实例的影响。
	5.	输出要求
	•	返回 校验后 最终可用的变量数组。
	•	若有调整（增加 / 删除 / 修改），在 description 中简要标注“新增 / 修订”字样。

⸻

输出格式（严格遵守）
```json
{{
  "variables": [
    {{
      "name": "变量名称1",
      "description": "变量描述1（新增 / 修订 / 保留）",
      "min": 最小值1,
      "max": 最大值1,
      "step": 步长1,
      "variant": "当该变量变化时，常量/实例的变化"
    }}
    // …按相同结构列出所有有效变量
  ]
}}
```
	•	仅输出合法 JSON，不得添加多余键、注释或代码块。
"""

validate_variables_en = """
# Role Definition
You are a **“Metadata Hyper-Parameter Auditor,”** responsible for ensuring that the variable list fully captures the metadata-generation space while remaining accurate, necessary, and actionable.

---

## Input
- **Constants**  
{metadata_constant}

- **Example Metadatas**  
{cases}

- **Candidate Parameters**  
{variables}

	•	Additional Information
{extra_info}

⸻

Task
	1.	Sufficiency Check
• Using the Constants, determine whether the current variable set covers every key dimension that affects metadata size, difficulty, and diversity.
• If something is missing, add new variables with reasonable definitions; if redundant or duplicate variables exist, merge or delete them.
	2.	Relevance Check
• Cross-reference the Example Metadatas to verify that each variable is explicitly reflected or can reasonably take effect.
• For variables that are not reflected and whose utility cannot be inferred, explain why and decide whether to keep or remove them.
	3.	Consistency & Reasonableness Check
• Ensure the min / max / step ranges align with the constants and cases, and that the numeric values are practical.
• If null is used, state the justification in description; if a variable supports a discrete set of values, list them and explain their effects in variant.
	4.	Field Completeness & Normalization
• Every variable must include the fields name, description, min, max, step, and variant, in that exact order and with correct data types.
• description should clearly state the purpose and rationale; variant should briefly describe how different values affect the constants or cases.
	5.	Output Requirement
• Return the validated final variable array.
• If any variable is added / removed / modified, mark it with “added / revised / retained” within the description.

⸻

Output Format (strictly follow)
```json
{{
  "variables": [
    {{
      "name": "Parameter Name 1",
      "description": "Parameter description 1 (added / revised / retained)",
      "min": MinimumValue1,
      "max": MaximumValue1,
      "step": Step1,
      "variant": "How changing this variable alters the constants/cases"
    }}
    // …list all valid variables using the same structure
  ]
}}
```
	•	Output valid JSON only—no extra keys, comments, or code fences.
"""

