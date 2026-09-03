# LLM RAG 自动生成工作流

这是一个算法开发。简单来讲，已经封装了每一个功能作为节点json，整个工作流由多个节点json构成。这样可以通过运行工作流的json配置文件，完成复杂功能。

目前整理了每一个节点的定义md、实现py，工作流的定义md等信息

```
├── define/             # 工作流和节点的定义文档
│   ├── workflow/       # 工作流定义文档
│   │   ├── base.md     # 工作流基础格式定义
│   │   ├── service_s03.md  # 组内动作调整指导工作流
│   │   └── between_set.md  # 组间休息分析和决策工作流
│   ├── node/           # 节点定义文档
│   │   ├── base.md     # 节点基础格式定义
│   │   ├── receive.md  # 接收节点定义
│   │   ├── judge.md    # 判断节点定义
│   │   ├── llm.md      # LLM节点定义
│   │   ├── tts.md      # TTS节点定义
│   │   ├── asr.md      # ASR节点定义
│   │   └── ...         # 其他节点类型定义
│   └── action/         # 动作定义文档
│       ├── add.md      # 添加节点操作
│       └── modify.md    # 修改节点操作
```

算法需要针对用户的自然语言输入，也许会提供标准可以参考的工作流，自动输出适配这个输入需求的工作流。

简单抽象，现状：需要利用大模型和一个知识库来完成需求处理

命令行输入：原始文件（如有）+需求

输出：思考过程+最终结果（并保存到json文件）

逻辑：

1.加载整个知识RAG库和原始文件

2.大模型根据需求和basic知识判断是否能够完成需求，如果可以则得到基本结果输出

3.如果不能完成需求，选择要加载的具体知识，加载后进一步判断是否能够完成需求，如果可以则得到基本结果输出，否则重复进行本步骤直到最大阈值

4.用户对基本输出进行校正，可以直接给出校正方法，或者让模型基于新需求再次调整，从2开始

注意：

1. 基本输出在输出前需要参考标准工作流进行格式的形式化验证
2. 应该在运行过程中，在命令行输出上述过程的输入、运行过程、输出，也就是运行日志
3. 后续需求可以由外部实现对工作流的自动验证时输出的bug作为直接需求注入


下面是一套**可直接落地**的“LLM + RAG 自动生成工作流 JSON”的总体方案（含数据结构、循环控制、验证与日志、以及后续“外部验证 bug 注入”的接口），按这个拆模块实现就能跑起来。

---

## **1）核心目标与关键约束**

**目标**：命令行输入「需求 + 原始文件（可选）」→ 输出

* **可读的推理摘要（decision trace）**：说明为什么选这些节点、怎么连、依据了哪些知识
* **最终工作流 JSON** **：保存到指定路径**

**关键约束**

1. 输出前必须做**形式化验证**（schema + 规则校验，必要时参考标准工作流模板）
2. 运行过程必须输出**可复现实验级日志**（输入、RAG 命中、每轮决策、验证结果、最终输出）
3. 后续可把**外部验证工具的 bug 报告**作为“新需求”注入，走同一套流程迭代修复
4. 提到“思考过程”：建议输出的是**“可读推理摘要”**而不是逐 token 的内部推理（不需要也不稳定），格式化成可审计的决策记录即可。

---

## **2）知识库（RAG）怎么建：把 md 变成“可检索的规范”**

现在有：

* **define/node/*.md**：节点类型定义（输入/输出/参数/约束/示例）
* define/workflow/*.md**：工作流定义（基础格式、标准流程）**
* **define/action/*.md**：对工作流的操作（add/modify …）
* ***.py**：实现（可作为“可用能力”的证据）

 **建议：RAG 不直接把 md 当纯文本塞进去，而是先做一次结构化索引（离线一次即可）** **：**

### **2.1 文档切片（chunk）与元数据**

每个 chunk 统一存：

* **doc_type**: node | workflow | action | impl
* name**: 如 **llm**, **judge**, **service_s03
* **fields**: inputs/outputs/params/constraints/example_json（能解析出来就填）
* **tags**: [“asr”,“tts”,“control-flow”,“validation”,…]
* source_path**: 原文件路径**
* **content**: 原文 + 提取后的结构摘要（两者都保留）

### **2.2 两级检索**

* **Level-0（全局）**：先只加载 base + 索引摘要（轻量，快）
  * workflow/base.md**, **node/base.md**, “节点目录摘要”**
* **Level-1（定向）**：当判断“信息不够/验证失败/置信度低”时，再按“需要的节点或规则”定向加载：
  * 例如需求提到“语音输入” → 检索 **asr.md**、相关示例、约束
  * 需求提到“判断/分支” → **judge.md**
  * 需求提到“修改现有 workflow” → **action/modify.md**

> 这样就能实现描述的第 2/3 步：先用 basic 知识试做，不够再定向补知识。

---

## **3）运行时管线：一套稳定的循环控制器**

整体是一个**状态机/循环控制器**（最多 N 轮）：

### **3.1 状态（RunState）**

至少包含：

* **request**: 用户需求文本 + 原始文件解析摘要（可选）
* **workspace**: 当前候选 workflow_json（可能为空）
* **retrieved_docs**: 每轮检索到的文档清单（含路径/片段/分数）
* **trace**: 可读推理摘要（结构化记录）
* **validation**: 最新验证结果（schema errors / rule errors）
* iteration**: 当前轮次**
* **stop_reason**: success | max_iter | user_abort

### **3.2 每轮流程（Iterate）**

1. **输入归一化**
   * 提取：目标、输入输出约束、必须节点、禁止节点、性能/实时性、容错、是否参考某标准工作流
2. **基于当前知识生成候选 workflow_json** **（LLM Planner）**
3. **形式化验证**（Validator）
   * 过：进入最终化（Finalize）
   * 不过：进入“缺口诊断”（Gap Analysis）
4. **缺口诊断 → 决定下一轮要检索什么** **（LLM 或规则）**

* 例：缺 node spec、缺字段、参数不合法、拓扑不通、与 base 格式冲突、与标准模板偏差过大

1. **定向检索补知识 → 下一轮**

---

## **4）最重要的一层：验证（Validation）必须是“硬的”**

只靠 LLM “自检”会漂。建议验证拆三层：

### **4.1 Schema 验证（硬约束）**

* 用 JSON Schema 或 Pydantic 定义**workflow/base.md 对应的字段结构**
* 节点结构也 schema 化（node/base.md）
* 这一步负责：字段缺失/类型错误/枚举不合法

### **4.2 规则验证（图与语义约束）**

典型规则：

* node.type 必须存在于 node registry（由 RAG 提取 + 运行时注册）
* 节点输入输出的引用要存在（变量名/端口）
* DAG / 环：是否允许环？允许就要有条件与最大次数
* 分支/合流结构必须满足 **judge** 定义
* 是否必须包含 receive / output 节点等（如果 base 规定）
* 与标准工作流的“必要骨架”对齐（比如 service_s03 必须包含某些节点序列）

### **4.3 参考标准工作流的“模板匹配”**

当用户明确说“参考 service_s03”或“类似 between_set”，可以做：

* 先检索到模板 JSON 示例（或从 md 中抽取）
* **用规则检查：****必须段落存在 + 可选段落按需裁剪**
* 让 LLM 只在模板允许的槽位里填参数/增删节点（更稳）

---

## **5）“思考过程”怎么输出才可控：用 Decision Trace**

想在命令行打印“思考过程”，我建议输出的是**结构化决策记录**（可审计、可复现），例如：

* **需求解析摘要**：识别到的意图、关键约束、必须能力
* **本轮使用的知识**：命中哪些 doc（文件名/节点类型）
* **节点选择理由**：每个节点对应需求哪一条
* **拓扑说明**：主链路、分支条件、错误处理
* **验证结果**：通过/失败；失败原因列表；下一轮计划加载的知识

这类 trace 不依赖“模型内部推理细节”，但足够让人理解和调试。

---

## **6）日志（Logging）：同时满足“人读 + 机器可解析”**

建议同时输出两份：

1. **控制台日志（人读）**：分段打印、带颜色（可选）
2. **结构化日志（JSONL）**：每条记录一个事件，方便回放与统计

### **6.1 事件建议**

* **RUN_START**：输入、文件摘要、run_id、参数（max_iter 等）
* **RETRIEVE**：query、filters、top_k、命中列表（path/score）
* **PLAN**：模型版本、提示摘要、输出 hash、简短摘要
* VALIDATE_SCHEMA / VALIDATE_RULE**：errors/warnings**
* **GAP_ANALYSIS**：缺口分类、下一轮检索计划
* **FINALIZE**：输出路径、workflow hash、校验通过项
* **RUN_END**：stop_reason、总耗时、轮次数、成本估计（可选）

---

## **7）用户校正（Human-in-the-loop）：两种入口都要支持**

说“用户对基本输出进行校正，可以直接给出校正方法，或者让模型基于新需求再次调整”，建议支持两种交互模式：

### **7.1 Patch 模式（最快、最确定）**

用户给：

* JSON Patch（RFC6902）或自定义的简单 patch DSL
  **例：**replace nodes[3].params.temperature = 0.2

系统做：

* 应用 patch → 重新验证 → 通过则落盘

### **7.2 需求重写模式（更自然）**

用户给：

* “把 ASR 换成离线模型；judge 的阈值改成 0.7；增加失败重试 2 次”
  系统做：
* 把“旧 workflow + 新需求 + 现有知识”喂给 planner
* 必须要求输出“变更说明 + 新 JSON”
* 再走验证

> 两种模式都走同一个 Validator，保证不会越改越坏。

---

## **8）外部验证 bug 注入：把 bug 报告当“新需求”处理**

提到后续外部自动验证会输出 bug，建议定义统一的 **BugReport → Requirement** 转换器：

BugReport（建议结构）：

* **error_type**: schema | rule | runtime | semantic
* location**: json_path（如 **$.nodes[5].params.xxx**）**
* message**: 原始报错**
* **hint**: 可选（验证器给的建议）
* **severity**: error | warn

注入策略：

* 把 bug 报告生成一段“修复需求”（可附带 json_path）
* 在 planner 提示里明确：**尽量最小修改（minimal diff）**，避免大重写
* 修复后必须输出 **change_log**（改了哪些节点、为何）

---

## **9）Planner（LLM）提示词与输出契约：强约束才能稳**

建议把 LLM 的输出固定成一个“计划包”：

 **LLM 输出 JSON（不是最终 workflow）** **：**

* confidence**: 0-1**
* need_more_knowledge**: bool**
* **knowledge_queries**: [ {query, filters, reason} ]
* **workflow_draft**: {…}**  **// 候选 workflow JSON
* **decision_trace**: {…}**  **// 可读推理摘要（结构化）
* assumptions**: […]**
* **open_questions**: […]（可选，如果允许交互式澄清）

运行时逻辑：

* **如果 **need_more_knowledge=true** 或 **confidence<阈值** 或验证失败 → 进入定向检索**
* 否则尝试 finalize

---

## **10）一个最小可行实现（MVP）拆分清单**

可以按以下模块分工实现（每个模块都可单测）：

1. **kb/indexer**：md → chunks（含结构抽取）→ 向量索引
2. **kb/retriever**：Level-0/Level-1 检索 + filters
3. **planner**：LLM 调用与输出解析（强 schema）
4. **validator/schema**：JSON Schema 或 Pydantic
5. **validator/rules**：拓扑/节点存在性/引用一致性/模板对齐
6. **runner/controller**：循环控制、max_iter、stop_reason
7. **logger**：console + JSONL
8. **cli**：参数解析、文件加载、输出落盘、交互模式（可选）

---

